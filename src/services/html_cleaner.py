"""
Step 3: HTML Cleaning
Processes raw HTML to extract article metadata and chart information
"""
import re
from typing import Dict, List, Any


class HTMLCleaner:
    def __init__(self):
        self.JUNK_ENDINGS = [
            "SunWiz License Terms", "Ownership Rights", "Quick Summary",
            "You MAY:", "Copyright", "Disclaimer", "Commentary by AI",
            "Interpreting this data", "Applying this data", "Key Insights",
            "Analysis:", "Recommendations:", "Next Steps:"
        ]
        self.JUNK_LINE_INDICATORS = [
            "Key Insights", "Recommendations", "Customers Stopped",
            "|", "---", "Dec 2024", "Jan 2025"
        ]
        self.START_TRIGGERS = [
            "This chart shows", "This graph shows", "The chart displays",
            "This visual highlights", "Here we see", "The data indicates",
            "Th is chart shows", "This map shows"
        ]

    def clean_and_extract(self, raw_html: str, base_url: str = 'https://rocket.sunwiz.com.au/sites/default/') -> Dict[str, Any]:
        """
        Clean HTML and extract article metadata and chart information

        Args:
            raw_html: Raw HTML content from Joomla
            base_url: Base URL for resolving relative image paths

        Returns:
            Dictionary containing article metadata and chart information
        """
        if base_url.endswith('/'):
            base_url = base_url[:-1]

        # Phase 1: Heavy Cleaning
        text = self._heavy_clean(raw_html, base_url)

        # Phase 2: Logic Extraction
        result = self._extract_logic(text)

        return result

    def _image_to_anchor(self, match, base_url: str) -> str:
        """Convert image tags to chart anchor format"""
        full_tag = match.group(0)
        src = match.group(1)

        # Extract View ID
        view_match = re.search(r'view="([^"]+)"', full_tag)
        view_id = view_match.group(1) if view_match else "Unknown_View"

        # Extract Title (Human Name)
        title_match = re.search(r'title="([^"]+)"', full_tag)
        human_name = title_match.group(1) if title_match else "Unknown_Title"

        # Extract Tabs Name
        tabs_match = re.search(r'tabs="([^"]+)"', full_tag)
        tabs_name = tabs_match.group(1) if tabs_match else "Unknown_Tabs"

        if src.startswith('data:'):
            return ''

        if src.startswith('http'):
            url = src
        elif src.startswith('/'):
            url = f'{base_url}{src}'
        else:
            url = f'{base_url}/{src}'

        return f'\n\n[[CHART_ANCHOR|{view_id}|{url}|{human_name}|{tabs_name}]]\n\n'

    def _heavy_clean(self, html_content: str, base_url: str) -> str:
        """Phase 1: Heavy cleaning of HTML"""
        # Remove script and style tags
        text = re.sub(r'<(script|style).*?>.*?</\1>', '', html_content, flags=re.DOTALL)

        # Remove GPT prompts
        text = re.sub(r'GPT PROMPT.*?END GPT \(with replace\)', '', text, flags=re.DOTALL | re.IGNORECASE)

        # Convert hr tags to section dividers
        text = re.sub(r'<hr.*?>', '\n\n[[SECTION_DIVIDER]]\n\n', text, flags=re.IGNORECASE)

        # Convert images to anchors
        text = re.sub(
            r'<img[^>]+src="([^">]+)"[^>]*>',
            lambda m: self._image_to_anchor(m, base_url),
            text
        )

        # Convert block elements to newlines
        text = re.sub(r'<(div|p|br|h[1-6]|li)[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'</(div|p|h[1-6]|li)>', '\n', text, flags=re.IGNORECASE)

        # Remove remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Replace HTML entities
        text = text.replace('&nbsp;', ' ').replace('&amp;', '&')

        # Clean up whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text).strip()

        return text

    def _extract_logic(self, text: str) -> Dict[str, Any]:
        """Phase 2: Extract logical structure and metadata"""
        anchor_pattern = r'\[\[CHART_ANCHOR\|(.*?)\|(.*?)\|(.*?)\|(.*?)\]\]'
        sections = text.split('[[SECTION_DIVIDER]]')

        slider_data = {}
        extracted_category = ""
        extracted_technology = ""
        slider_name_is_valid = False

        article_title = "Analysis Report"
        final_charts = []

        valid_image_count = 0
        slider_view_id = None

        for section_idx, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue

            all_matches = list(re.finditer(anchor_pattern, section))

            if not all_matches:
                if section_idx == 0:
                    article_title = section
                continue

            for i, match in enumerate(all_matches):
                view_id = match.group(1)
                image_url = match.group(2)
                human_name_backup = match.group(3)
                tabs_name = match.group(4)

                if view_id == "Unknown_View" or "blobid" in image_url:
                    continue

                if slider_view_id and view_id == slider_view_id:
                    continue

                valid_image_count += 1

                # Case A: Extract Slider (First valid image)
                if valid_image_count == 1:
                    slider_view_id = view_id

                    raw_slider_name = human_name_backup.strip()

                    if raw_slider_name and raw_slider_name != "Unknown_Title" and "Unknown" not in raw_slider_name:
                        slider_name_is_valid = True
                        clean_name = raw_slider_name
                        if ":" in raw_slider_name:
                            clean_name = raw_slider_name.split(":", 1)[1].strip()
                        else:
                            clean_name = raw_slider_name.replace("Slide Header", "").strip()

                        words = clean_name.split()
                        if len(words) >= 1:
                            extracted_category = words[0]
                        if len(words) >= 2:
                            extracted_technology = " ".join(words[1:])
                    else:
                        slider_name_is_valid = False

                    slider_data = {
                        "view_id": view_id,
                        "image_url": image_url,
                        "human_name": human_name_backup,
                        "tabs_name": tabs_name,
                        "category": extracted_category,
                        "technology": extracted_technology
                    }

                    start_pos = 0 if i == 0 else all_matches[i-1].end()
                    raw_header = section[start_pos:match.start()].strip()
                    if raw_header:
                        lines = [l.strip() for l in raw_header.split('\n')
                                if l.strip() and "[[CHART_ANCHOR" not in l]
                        if lines:
                            article_title = lines[-1]

                    continue

                # Case B: Extract Regular Chart

                # A. Title
                start_pos = 0 if i == 0 else all_matches[i-1].end()
                text_before = section[start_pos:match.start()].strip()
                title = human_name_backup
                if text_before:
                    lines = [l.strip() for l in text_before.split('\n')
                            if l.strip() and "[[CHART_ANCHOR" not in l]
                    if lines:
                        title = lines[-1]

                # B. Shows (Raw extraction)
                end_pos = all_matches[i+1].start() if (i + 1 < len(all_matches)) else len(section)
                raw_shows = section[match.end():end_pos].strip()
                if "[[CHART_ANCHOR" in raw_shows:
                    raw_shows = raw_shows.split('[[CHART_ANCHOR')[0].strip()

                # C. Shows Intelligent Cleaning
                shows = self._clean_shows(raw_shows)

                final_charts.append({
                    "view_id": view_id,
                    "title": title,
                    "image_url": image_url,
                    "tabs_name": tabs_name,
                    "shows": shows
                })

        return {
            'article_title': article_title,
            'slider_image': slider_data,
            'category': extracted_category,
            'technology': extracted_technology,
            'charts': final_charts  # Return list of chart dictionaries for easier looping
        }

    def _clean_shows(self, raw_shows: str) -> str:
        """Intelligently clean the 'shows' description"""
        shows = "No description provided."

        if not raw_shows:
            return shows

        clean_lines = []
        for line in raw_shows.split('\n'):
            line = line.strip()
            if line.startswith('>') or line.startswith('->'):
                line = line.lstrip('->').strip()
            if not line:
                continue

            is_dirty_line = False
            for indicator in self.JUNK_LINE_INDICATORS:
                if indicator in line:
                    is_dirty_line = True
                    break
            if not is_dirty_line:
                clean_lines.append(line)

        cleaned_text_block = "\n".join(clean_lines)

        # Find start trigger
        start_index = -1
        found_trigger = False
        for trigger in self.START_TRIGGERS:
            idx = cleaned_text_block.lower().find(trigger.lower())
            if idx != -1:
                if start_index == -1 or idx < start_index:
                    start_index = idx
                    found_trigger = True

        if found_trigger:
            cleaned_text_block = cleaned_text_block[start_index:]

        # Cut off at junk endings
        final_text = cleaned_text_block
        cutoff_index = len(final_text)
        for keyword in self.JUNK_ENDINGS:
            idx = final_text.lower().find(keyword.lower())
            if idx != -1 and idx < cutoff_index:
                cutoff_index = idx

        final_text = final_text[:cutoff_index].strip()
        shows = re.sub(r'\s+', ' ', final_text).strip()

        if not shows or len(shows) < 5:
            shows = "No description provided."

        return shows
