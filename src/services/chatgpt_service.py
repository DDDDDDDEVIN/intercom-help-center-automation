"""
ChatGPT Analysis Service
Sends chart data and context to ChatGPT for analysis
"""
import requests
import json
from typing import Dict, List


class ChatGPTService:
    def __init__(self, api_key: str, model: str = "gpt-4"):
        """
        Initialize ChatGPT service

        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4)
        """
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def analyze_chart(
        self,
        chart_image_url: str,
        chart_context: str,
        prompt: str = None
    ) -> Dict:
        """
        Analyze a chart using ChatGPT with image and context to extract field names

        Args:
            chart_image_url: URL to the chart image
            chart_context: Extracted XML context about the chart
            prompt: Optional custom prompt (uses default field extraction prompt if not provided)

        Returns:
            Dictionary containing analysis result with field structure
        """
        if prompt is None:
            prompt = f"""
Role & Objective You are a Raw Data Structure Extractor. Your ONLY goal is to map the visual charts to their corresponding metadata fields. DO NOT rename, translate, or simplify any field names. Output exactly what is provided in the Cleaned Metadata.

Input Data 1. Metadata (Cleaned Context):

{chart_context}

2. Chart Image: (Refer to the attached image. Scan ALL sub-charts.)

STRICT EXECUTION LOGIC

IGNORE ANY CHART WITH title: no title or logo

Logic 1: Zero-Translation Policy (Verbatim Extraction)

Absolute Rule: Do NOT rename fields.

If Metadata says INDEX, output "INDEX".

If Metadata says Date First Seen, output "Date First Seen".

If Metadata says Capacity recent month, output "Capacity recent month".

Goal: We need the raw data keys for a downstream dictionary lookup. Do not try to make them "human-readable".

Logic 2: Universal Axis Decomposition (The "Formula" Fix)

Context: Tableau axes often combine multiple fields (e.g., Field A * Field B or Field A / Field B).

Instruction: Look at the X and Y axes in the Metadata for every chart visible in the image.

Action:

If the axis is a single field (e.g., Date), extract "Date".

If the axis is a formula/combination (e.g., INDEX * Capacity or Region / State):

Decompose it. Extract ALL distinct field names involved.

Example: Input INDEX * Capacity → Output "INDEX, Capacity".
Example: Input INDEX / Capacity → Output "INDEX, Capacity".

Do NOT guess if it is Rank or Volume. Just return the field names found in the metadata string.

Logic 3: The "All-Chart" Aggregation (Union)

Scan every distinct chart in the image (Top-left, Bottom-left, Right, etc.).

Extract X and Y axes for each chart.

Merge them into a single unique list.

Example: If Chart A uses "Segment" and Chart B uses "State", the output Vertical must include both "Segment, State".

Logic 4: Dimension vs. Measure Sorting

Dimensions: Any field found on an Axis or Legend that represents a Category, Time, Location, or Index.
Do not include any fields that not included in axes or legend.

Measures: Any field found on an Axis that represents a Value/Metric.
Do not include any fields that not included in axes or legend.

Note: If a field is used to split colors (Legend), add it to Dimensions.
Ignore any filters found in the XML that apply to all.
Example: If XML lists "State" but the chart shows "All States" (single aggregate line), IGNORE "State".

Output Format Return ONLY a single, valid JSON object. No Markdown.

JSON Structure: {{"Vertical": "Comma-separated list of ALL raw fields found on Y-Axes", "Horizontal": "Comma-separated list of ALL raw fields found on X-Axes (Decompose formulas!)", "Dimensions": ["List of raw dimension names"], "Measures": ["List of raw measure names"]}}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a Raw Data Structure Extractor for Tableau charts. Extract field names exactly as they appear in metadata without any translation or simplification."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": chart_image_url
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 2000
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            data = response.json()
            analysis = data['choices'][0]['message']['content'].strip()

            # Strip markdown code block markers if present
            if analysis.startswith('```'):
                lines = analysis.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                analysis = '\n'.join(lines).strip()

            return {
                "status": "success",
                "analysis": analysis
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"ChatGPT API request failed: {str(e)}"
            }

    def extract_field_names(self, gpt_response: str) -> Dict:
        """
        Extract field names from GPT response

        Args:
            gpt_response: The raw response text from GPT (could be JSON or text)

        Returns:
            Dictionary with field_name list and total_count
        """
        # Parse target fields (handle JSON, List, or String format)
        target_field_list = []

        # Try to extract if it's JSON
        try:
            # Look for JSON-like structures in the response
            parsed = json.loads(gpt_response)
            if isinstance(parsed, list):
                target_field_list = parsed
            elif isinstance(parsed, dict):
                # Check if it's the new structured format with Dimensions/Measures
                if 'Dimensions' in parsed or 'Measures' in parsed:
                    # Extract from Dimensions array
                    if 'Dimensions' in parsed and isinstance(parsed['Dimensions'], list):
                        target_field_list.extend(parsed['Dimensions'])
                    # Extract from Measures array
                    if 'Measures' in parsed and isinstance(parsed['Measures'], list):
                        target_field_list.extend(parsed['Measures'])
                    # Also parse Vertical and Horizontal comma-separated strings
                    if 'Vertical' in parsed and parsed['Vertical']:
                        vertical_fields = [f.strip() for f in str(parsed['Vertical']).split(',')]
                        target_field_list.extend(vertical_fields)
                    if 'Horizontal' in parsed and parsed['Horizontal']:
                        horizontal_fields = [f.strip() for f in str(parsed['Horizontal']).split(',')]
                        target_field_list.extend(horizontal_fields)
                else:
                    # Old format: extract all values that are lists
                    for v in parsed.values():
                        if isinstance(v, list):
                            target_field_list.extend(v)
            else:
                # Not a list or dict, treat as comma-separated string
                target_field_list = str(gpt_response).split(',')
        except (json.JSONDecodeError, ValueError):
            # JSON parsing failed, treat as comma-separated string
            target_field_list = str(gpt_response).split(',')

        # Clean and deduplicate list
        clean_targets_map = {}

        for t in target_field_list:
            if t and str(t).lower() != 'none' and str(t).strip():
                clean_item = str(t).strip()
                # Generate normalized key for deduplication (remove spaces, hyphens, lowercase)
                norm_key = clean_item.lower().replace(" ", "").replace("-", "")

                # Add if not seen before
                if norm_key not in clean_targets_map:
                    clean_targets_map[norm_key] = clean_item

        # Generate output list
        final_name_list = list(clean_targets_map.values())

        return {
            "field_names": final_name_list,
            "total_count": len(final_name_list)
        }

    def analyze_data_field(
        self,
        field_name: str,
        field_context: str,
        prompt: str = None
    ) -> Dict:
        """
        Analyze a data field using ChatGPT with detailed context

        Args:
            field_name: The name of the data field
            field_context: Extracted XML context about the field
            prompt: Custom prompt for analysis (optional)

        Returns:
            Dictionary containing analysis result with JSON structure
        """
        if prompt is None:
            prompt = f"""
**Role:** You are a Senior Data Analyst and Technical Writer specializing in Tableau dashboards.

**Task:** Analyze the provided field logic and extract documentation metadata into a strict JSON format.

**Input Data:**
- **Field Name:** {field_name}
- **Technical Context:**

{field_context}

Extraction Rules:

"definition": Write a clear, concise (1-sentence) business definition explaining what the field measures. Avoid technical jargon.

"calculation_explanation": Explain how it works in plain English.

If it's a native field, just say "Direct value from the database."

If it uses logic like IF, CASE, or FIXED, explain the business logic (e.g., "Groups brands with less than 1% market share into 'Minor Brands'").

"pseudo_formula": Create a simplified, human-readable formula.

Do NOT use complex Tableau syntax like FIXED, DATEDIFF, or DATETRUNC.

Use descriptive variable names.

Example: (Current Month Capacity - First Month Capacity) / First Month Capacity

If it is a simple Native Field, just return "None".

"considerations":

IF Categorical (Strings): Look for "Categories:" in the context. List them here (e.g., "Segments include: Resi, Commercial...").

IF Numeric (Measures): Look for "Filter Range Found:". If found, write the range (e.g., "Filtered to range: 0 to 500"). DO NOT list individual numbers or sample values for measures.

IF No Data: If neither categories nor ranges are found, return "None".

Output Format: Return ONLY a valid JSON object. Do not wrap it in markdown code blocks (like ```json).

{{ "definition": "String content...", "calculation_explanation": "String content...", "pseudo_formula": "String content...", "considerations": "String content..." }}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a Senior Data Analyst and Technical Writer specializing in Tableau dashboards. Extract field documentation in strict JSON format without markdown wrappers."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 1500
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            data = response.json()
            analysis = data['choices'][0]['message']['content'].strip()

            # Strip markdown code block markers if present
            if analysis.startswith('```'):
                lines = analysis.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                analysis = '\n'.join(lines).strip()

            return {
                "status": "success",
                "analysis": analysis
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"ChatGPT API request failed: {str(e)}"
            }

    def rewrite_field_name(
        self,
        field_name: str,
        field_context: str = None
    ) -> Dict:
        """
        Generate a human-readable name for a data field

        Args:
            field_name: The original field name
            field_context: Optional context about the field

        Returns:
            Dictionary with rewritten name
        """
        prompt = f"""
**Role:** You are a UX Writer and Data Steward for a Business Intelligence platform.

**Task:** Rename the technical Tableau field name into a clean, professional, "Human-Readable" Business Name.

**Input Data:**
- **Original Name:** {field_name}

- **Technical Context:**

{field_context if field_context else "No additional context provided."}

Renaming Rules:

Fix Grammar & Formatting:

Convert snake_case or camelCase to Title Case.

Remove technical noise like underscores (_), IDs (e.g., 10239), or parentheses (e.g., (copy 2)).

Example: profit_ratio_adj -> "Profit Ratio (Adjusted)"

Analyze Logic for Context:

Look at the formula in the context.

If the field is a boolean filter (True/False) or a flag, prefix with "Is" or "Has" if appropriate (e.g., Is Recent Month).

If the field groups small values (e.g., logic contains IF < 0.01), name it based on the grouping (e.g., "Brand Category" or "Market Segment").

If the logic uses INDEX() or RANK(), name it "Rank".

Keep Technical Units (Smartly):

Do NOT remove essential units like "kW", "MW", "YTD", "YoY".

Example: PV kW-DC Segment -> "PV Segment (kW-DC)" (Better formatting) or keep as is if it's already good.

Brevity:

Keep it under 5 words.

Capacity recent month -> "Recent Month Capacity"

Output Format: Return ONLY a valid JSON object.

{{ "human_name": "String result..." }}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a UX Writer and Data Steward for a Business Intelligence platform. Generate clean, professional business names for technical field names. Return JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 150
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            content = data['choices'][0]['message']['content'].strip()

            # Strip markdown code block markers if present
            if content.startswith('```'):
                # Remove ```json or ``` at start and ``` at end
                lines = content.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]  # Remove first line
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]  # Remove last line
                content = '\n'.join(lines).strip()

            # Parse JSON response
            try:
                parsed = json.loads(content)
                rewritten_name = parsed.get('human_name', content)
            except (json.JSONDecodeError, ValueError):
                # Fallback: if not JSON, use the raw content
                rewritten_name = content

            return {
                "status": "success",
                "human_name": rewritten_name
            }

        except requests.exceptions.RequestException as e:
            return {
                "status": "error",
                "message": f"ChatGPT API request failed: {str(e)}"
            }
