"""
ChatGPT Analysis Service
Sends chart data and context to ChatGPT for analysis
"""
import requests
import json
from typing import Dict, List


class ChatGPTService:
    def __init__(self, api_key: str, model: str = "gpt-4", image_detail: str = "high", text_model: str = "gpt-4o"):
        """
        Initialize ChatGPT service

        Args:
            api_key: OpenAI API key
            model: Vision model for chart image analysis (default: gpt-4)
            image_detail: Image resolution detail level - "low", "high", or "auto" (default: high)
            text_model: Text-only model for field analysis and name rewriting (default: gpt-4o)
        """
        self.api_key = api_key
        self.model = model
        self.text_model = text_model
        self.image_detail = image_detail
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
Role & Objective
You are a Raw Data Structure Extractor. Your goal is to map visual charts to their corresponding metadata fields and identify their visual labels.

Input Data:
1. Metadata (Cleaned Context):
{chart_context}

2. Chart Image: (Refer to the attached image. Scan ALL sub-charts.)

STRICT EXECUTION LOGIC:

IGNORE ANY CHART WITH title: "no title" or logo.

Logic 1: Zero-Translation & Visual Verification
- Absolute Rule: The "field" key must match the Metadata keys EXACTLY.
- Visual Priority: If Metadata has similar fields (e.g., "Order Date" and "Ship Date") and the Chart Axis says "Ship Date", select "Ship Date".

Logic 2: Universal Axis Decomposition
- If an axis is a formula (e.g., "INDEX * Capacity"), decompose it into distinct fields (e.g., "INDEX", "Capacity").
- You must extract the display name for EACH decomposed field individually if possible.

Logic 3: The "All-Chart" Aggregation
- Scan every distinct chart in the image. Merge findings into the respective lists.

Logic 4: Dimension vs. Measure Sorting
- Dimensions: Category, Time, Location, or Index fields (Axis or Legend).
- Measures: Value/Metric fields.

Logic 5: Visual Label Mapping
- For EVERY extracted field (in Vertical, Horizontal, Dimensions, Measures), look for its specific visible text label on the chart.
- **Explicit Label:** If the Y-Axis title says "Total Revenue" for the field [Sales], the display_name is "Total Revenue".
- **No Label:** If the axis only shows values (e.g., 2020, 2021) but NO title text "Year", the display_name is null.
- **Implicit/Hidden:** If the field is used for sorting or calculation but not written on screen, display_name is null.

Logic 6: Strict Deduplication
- Remove duplicates based on the "field" key within each list.
- Ensure each raw field appears only ONCE in its respective list.

Output Format:
Return ONLY a single, valid JSON object. No Markdown.

JSON Structure:
{{
  "Vertical": [
    {{ "field": "Raw Field Name (Y-Axis)", "display_name": "Visual Axis Title or null" }}
  ],
  "Horizontal": [
    {{ "field": "Raw Field Name (X-Axis)", "display_name": "Visual Axis Title or null" }}
  ],
  "Dimensions": [
    {{ "field": "Raw Field Name", "display_name": "Visual Label or null" }}
  ],
  "Measures": [
    {{ "field": "Raw Field Name", "display_name": "Visual Label or null" }}
  ]
}}
"""
        print(f"[GPT] Model: {self.model}, API key set: {bool(self.api_key)}, Key prefix: {self.api_key[:10] if self.api_key else 'EMPTY'}")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": prompt
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "The metadata is {chart_context}, the chart image is attatched"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": chart_image_url,
                                "detail": self.image_detail  # Configurable resolution: low/high/auto
                            }
                        }
                    ]
                }
            ],
            "max_completion_tokens": 20000
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=300
            )
            response.raise_for_status()

            data = response.json()
            analysis = (data['choices'][0]['message']['content'] or '').strip()

            # DEBUG: Print raw GPT response
            print(f"\n[GPT analyze_chart response]\n{'-'*60}\n{analysis}\n{'-'*60}\n")

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
            Dictionary with field_names list, display_name_map, and total_count.
            display_name_map: {field_name: display_name_or_None}
            If display_name is provided and not null, use it directly as human name.
            If display_name is null, caller should use rewrite_field_name instead.
        """
        # Collect raw items as {"field": str, "display_name": str|None}
        raw_items = []

        def _parse_display_name(value):
            """Return None if the display_name is null/None/empty, else the string."""
            if value is None or str(value).strip().lower() in ('null', 'none', ''):
                return None
            return str(value).strip()

        try:
            parsed = json.loads(gpt_response)
            if isinstance(parsed, dict):
                for key in ['Vertical', 'Horizontal', 'Dimensions', 'Measures']:
                    section = parsed.get(key, [])
                    if isinstance(section, list):
                        for item in section:
                            if isinstance(item, dict) and 'field' in item:
                                raw_items.append({
                                    'field': str(item['field']).strip(),
                                    'display_name': _parse_display_name(item.get('display_name'))
                                })
                            elif isinstance(item, str) and item.strip():
                                raw_items.append({'field': item.strip(), 'display_name': None})
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and 'field' in item:
                        raw_items.append({
                            'field': str(item['field']).strip(),
                            'display_name': _parse_display_name(item.get('display_name'))
                        })
                    elif isinstance(item, str) and item.strip():
                        raw_items.append({'field': item.strip(), 'display_name': None})
            else:
                for f in str(gpt_response).split(','):
                    if f.strip():
                        raw_items.append({'field': f.strip(), 'display_name': None})
        except (json.JSONDecodeError, ValueError):
            for f in str(gpt_response).split(','):
                if f.strip():
                    raw_items.append({'field': f.strip(), 'display_name': None})

        # Deduplicate by normalized field name
        seen = {}
        for item in raw_items:
            field = item['field']
            if not field or field.lower() == 'none':
                continue
            norm_key = field.lower().replace(' ', '').replace('-', '').replace('_', '')
            if norm_key not in seen:
                seen[norm_key] = item

        final_items = list(seen.values())
        field_names = [item['field'] for item in final_items]
        display_name_map = {item['field']: item['display_name'] for item in final_items}

        return {
            "field_names": field_names,
            "display_name_map": display_name_map,
            "total_count": len(field_names)
        }

    def analyze_data_field(
        self,
        field_name: str,
        field_context: str,
        human_name: str = "",
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
- **Technical ID:** {field_name} 
- **Target Display Name:** {human_name}
- **Technical Context:**

{field_context}

**Global Naming Rule:** If a "**Target Display Name**" is provided above, you MUST use it as the subject of your sentences in the "definition" and "calculation_explanation". Do NOT use the "Technical ID" (e.g., Calculation_12345) in the output text.

Extraction Rules:

"definition": Write a clear, concise (1-sentence) business definition explaining what the **Target Display Name** measures. Avoid technical jargon.

"calculation_explanation": Explain how it works in plain English.
- Use the **Target Display Name** when referring to the field itself.
- If it's a native field, just say "Direct value from the database."
- If it uses logic like IF, CASE, or FIXED, explain the business logic (e.g., "Groups brands with less than 1% market share into 'Minor Brands'").

"pseudo_formula": Create a simplified, human-readable formula.
- Do NOT use complex Tableau syntax like FIXED, DATEDIFF, or DATETRUNC.
- Use descriptive variable names (or Human-Readable names of referenced fields).
- Example: (Current Month Capacity - First Month Capacity) / First Month Capacity
- If it is a simple Native Field, just return "None".

"considerations":
- IF Categorical (Strings): Look for "Categories:" in the context.
  - **Meaningfulness Check:** Do the values represent descriptive business concepts (e.g., "East", "Furniture", "Completed")?
    - YES: List them (e.g., "Segments include: Resi, Commercial...").
    - NO: If the values appear to be raw IDs, numeric codes (e.g., "119", "120", "843"), or unique keys (UUIDs), return "None".
- IF Numeric (Measures): Look for "Filter Range Found:". If found, write the range (e.g., "Filtered to range: 0 to 500").
- IF No Data: If neither meaningful categories nor ranges are found, return "None".

Output Format: Return ONLY a valid JSON object. Do not wrap it in markdown code blocks (like ```json).

{{ "definition": "String content...", "calculation_explanation": "String content...", "pseudo_formula": "String content...", "considerations": "String content..." }}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.text_model,
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
            "max_completion_tokens": 1500
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=300
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

**Renaming Rules:**

1. **Fix Grammar & Formatting:**
   - Convert snake_case, camelCase, or all-caps to Title Case.
   - Remove technical noise: underscores (_), random IDs (e.g., 10239), or copy artifacts (e.g., "(copy 2)").
   - *Example:* "profit_ratio_adj" -> "Adjusted Profit Ratio"

2. **Analyze Logic for Context (Critical):**
   - **Calculated Fields:** If the name is generic like "Calculation_12345", you MUST read the logic in the context to name it (e.g., if logic is `SUM(Sales)/SUM(Profit)`, name it "Profit Ratio").
   - **Boolean/Flags:** If the logic returns True/False or 1/0, prefix with "Is", "Has", or "Was" (e.g., "Recent Month Flag" -> "Is Recent Month").
   - **Groupings:** If the logic groups values (e.g., IF < 0.01 THEN 'Other'), name it based on the entity (e.g., "Brand Category" or "Market Segment").
   - **Ranking:** If the logic uses INDEX() or RANK(), name it "Rank" or "Index".

3. **Handle Units Smartly:**
   - Move units to parentheses at the end for clarity, unless they are standard acronyms like YTD/YoY.
   - *Example:* "PV kW-DC Segment" -> "PV Segment (kW-DC)"
   - *Example:* "Revenue (USD)" is better than "USD Revenue".

4. **Brevity & Professionalism:**
   - Keep it under 5 words.
   - Remove redundant words like "Field", "Column", or "Var".
   - *Example:* "Capacity recent month" -> "Recent Month Capacity"

**Output Format:** Return ONLY a valid JSON object. Do not wrap it in markdown code blocks.

{{ "human_name": "String result..." }}
"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.text_model,
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
            "max_completion_tokens": 150
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=300
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
