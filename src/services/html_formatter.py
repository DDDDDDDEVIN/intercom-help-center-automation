"""
HTML Formatter Service
Formats AI analysis into HTML for Intercom Help Center
"""
import json
from typing import Dict, List


class HTMLFormatter:
    def __init__(self):
        """Initialize HTML Formatter"""
        self.spacer = '<p>&nbsp;</p>'  # Intercom spacer

    def format_data_field_html(self, field_name: str, ai_json: str, related_charts_names: List[str] = None, related_charts_urls: List[str] = None) -> str:
        """
        Format data field analysis into HTML with optional related charts

        Args:
            field_name: The field name
            ai_json: AI analysis in JSON format
            related_charts_names: Optional list of chart titles that use this field
            related_charts_urls: Optional list of corresponding Intercom URLs

        Returns:
            Formatted HTML string
        """
        # Parse JSON
        clean_json_str = ai_json.replace("```json", "").replace("```", "").strip()

        try:
            data = json.loads(clean_json_str)
        except Exception as e:
            data = {
                "definition": "Error parsing definition.",
                "calculation_explanation": "None",
                "pseudo_formula": "None",
                "considerations": f"Raw data error: {str(e)}"
            }

        # Extract fields
        definition = data.get('definition', '')
        calc_exp = data.get('calculation_explanation', '')
        formula = data.get('pseudo_formula', 'None')
        considerations = data.get('considerations', 'None')

        # Build HTML
        html_parts = []

        # Term (as first line, no H2 header)
        html_parts.append(f'<p><strong>Term:</strong> {field_name}</p>')
        html_parts.append(self.spacer)

        # Definition
        html_parts.append('<p><strong>Definition:</strong></p>')
        html_parts.append(f'<p>{definition}</p>')
        html_parts.append(self.spacer)

        # Calculation
        html_parts.append('<p><strong>Calculation:</strong></p>')
        html_parts.append(f'<p>{calc_exp}</p>')

        # If formula exists and is not 'none' or same as field name, add it in italics
        if formula and formula.lower() != 'none' and formula != field_name:
            html_parts.append(self.spacer)
            html_parts.append(f'<p><em>{formula}</em></p>')

        html_parts.append(self.spacer)

        # Considerations
        if considerations and considerations.lower() != 'none':
            html_parts.append('<p><strong>Considerations:</strong></p>')
            html_parts.append(f'<p>{considerations}</p>')
            html_parts.append(self.spacer)

        # Related Charts section
        if related_charts_names and related_charts_urls:
            if len(related_charts_names) == len(related_charts_urls):
                html_parts.append('<p><strong>Related Charts:</strong><ul>')
                for name, url in zip(related_charts_names, related_charts_urls):
                    if name and url:
                        html_parts.append(f'<li><a href="{url}" target="_blank">{name}</a></li>')
                    elif name:
                        html_parts.append(f'<li>{name}</li>')

                html_parts.append('</ul></p>')
                html_parts.append(self.spacer)

        # Divider
        html_parts.append('<hr>')

        return "".join(html_parts)

    def format_chart_html(
        self,
        chart_title: str,
        chart_analysis: str,
        chart_shows: str = None
    ) -> str:
        """
        Format chart analysis into HTML

        Args:
            chart_title: The chart title
            chart_analysis: AI analysis of the chart
            chart_shows: Optional description of what the chart shows

        Returns:
            Formatted HTML string
        """
        html_parts = []

        # Chart Title
        html_parts.append(f'<h2>{chart_title}</h2>')
        html_parts.append(self.spacer)

        # Chart Description
        if chart_shows:
            html_parts.append('<p><strong>Overview:</strong></p>')
            html_parts.append(f'<p>{chart_shows}</p>')
            html_parts.append(self.spacer)

        # Analysis
        html_parts.append('<p><strong>Analysis:</strong></p>')
        html_parts.append(f'<p>{chart_analysis}</p>')
        html_parts.append(self.spacer)

        # Divider
        html_parts.append('<hr>')

        return "".join(html_parts)

    def format_chart_complete_html(
        self,
        chart_title: str,
        chart_shows: str,
        chart_analysis: str,
        field_human_names: List[str],
        field_urls: List[str],
        chart_image_url: str = None
    ) -> str:
        """
        Format complete chart HTML including field links

        Args:
            chart_title: The chart title
            chart_shows: Description of what the chart shows
            chart_analysis: AI analysis of the chart
            field_human_names: List of human-readable field names
            field_urls: List of corresponding Intercom URLs
            chart_image_url: Optional chart image URL

        Returns:
            Formatted HTML string
        """
        html_parts = []

        # Chart Title
        html_parts.append(f'<h2>{chart_title}</h2>')
        html_parts.append(self.spacer)

        # Chart Image (if provided)
        if chart_image_url:
            html_parts.append(f'<img src="{chart_image_url}" alt="{chart_title}" style="max-width:100%; height:auto;">')
            html_parts.append(self.spacer)

        # Chart Description
        html_parts.append('<p><strong>Overview:</strong></p>')
        html_parts.append(f'<p>{chart_shows}</p>')
        html_parts.append(self.spacer)

        # Analysis
        html_parts.append('<p><strong>Analysis:</strong></p>')
        html_parts.append(f'<p>{chart_analysis}</p>')
        html_parts.append(self.spacer)

        # Data Fields Section
        if field_human_names and any(field_human_names):
            html_parts.append('<p><strong>Data Fields Used:</strong></p>')
            html_parts.append('<ul>')

            for human_name, url in zip(field_human_names, field_urls):
                if human_name and url:
                    html_parts.append(f'<li><a href="{url}" target="_blank">{human_name}</a></li>')
                elif human_name:
                    html_parts.append(f'<li>{human_name}</li>')

            html_parts.append('</ul>')
            html_parts.append(self.spacer)

        # Divider
        html_parts.append('<hr>')

        return "".join(html_parts)

    def format_article_html(
        self,
        article_title: str,
        category: str,
        technology: str,
        chart_summaries: List[Dict]
    ) -> str:
        """
        Format complete article HTML aggregating all charts

        Args:
            article_title: The article title
            category: Article category
            technology: Article technology
            chart_summaries: List of dicts with chart info and intercom_url

        Returns:
            Formatted HTML string
        """
        html_parts = []

        # Article Header
        html_parts.append(f'<h1>{article_title}</h1>')
        html_parts.append(self.spacer)

        # Metadata
        html_parts.append('<p><strong>Category:</strong> ' + category + '</p>')
        html_parts.append('<p><strong>Technology:</strong> ' + technology + '</p>')
        html_parts.append(self.spacer)

        # Charts Section
        html_parts.append('<h2>Charts</h2>')
        html_parts.append(self.spacer)

        if chart_summaries:
            html_parts.append('<ol>')

            for chart_summary in chart_summaries:
                chart_title = chart_summary.get('title', 'Untitled Chart')
                chart_url = chart_summary.get('intercom_url', '')

                if chart_url:
                    html_parts.append(f'<li><a href="{chart_url}" target="_blank">{chart_title}</a></li>')
                else:
                    html_parts.append(f'<li>{chart_title}</li>')

            html_parts.append('</ol>')
            html_parts.append(self.spacer)
        else:
            html_parts.append('<p>No charts available.</p>')
            html_parts.append(self.spacer)

        return "".join(html_parts)

    def format_chart_with_json_html(
        self,
        chart_name: str,
        image_url: str,
        category: str,
        country: str,
        shows_text: str,
        best_used_for: str,
        considerations: str,
        accuracy: str,
        chart_json: Dict,
        field_mapping: Dict[str, Dict[str, str]],
        related_charts_names: List[str] = None,
        related_charts_urls: List[str] = None,
        related_articles_names: List[str] = None,
        related_articles_urls: List[str] = None
    ) -> str:
        """
        Format chart HTML with detailed JSON structure and linked fields

        Args:
            chart_name: Chart title
            image_url: Chart image URL
            category: Chart category
            country: Availability/Country
            shows_text: Description of what chart shows
            best_used_for: Best use cases
            considerations: Important considerations
            accuracy: Accuracy notes (deprecated, not displayed)
            chart_json: JSON with Vertical, Horizontal, Dimensions, Measures
            field_mapping: Dict mapping tableau_name to {human, url}
            related_charts_names: List of related chart names (optional)
            related_charts_urls: List of related chart URLs (optional)

        Returns:
            Formatted HTML string
        """
        html_parts = []

        def clean_field_and_link(val):
            """Helper to process field names and create links.
            Items may be plain strings or {'field': str, 'display_name': str|None} dicts.
            Label priority: display_name > field_mapping human name > raw field name.
            Link comes from field_mapping when available.
            Deduplicates by label before rendering.
            """
            if not val:
                return ""

            items = val if isinstance(val, list) else str(val).split(',')

            seen_labels = set()
            processed_items = []
            for item in items:
                if isinstance(item, dict):
                    field_key = item.get('field', '').strip()
                    display_name = item.get('display_name')
                else:
                    field_key = str(item).strip()
                    display_name = None

                # Resolve label and link
                if field_key and field_key in field_mapping:
                    record = field_mapping[field_key]
                    label = display_name if display_name else record.get('human', field_key)
                    link = record.get('url', '')
                    html_item = f'<a href="{link}">{label}</a>' if link else label
                else:
                    label = display_name if display_name else field_key
                    html_item = label

                # Skip blanks, "None" strings, and duplicates
                if not label or label.lower() == 'none' or label in seen_labels:
                    continue
                seen_labels.add(label)
                processed_items.append(html_item)

            return ", ".join(processed_items)

        # Extract and process fields from chart JSON
        vertical = clean_field_and_link(chart_json.get('Vertical'))
        horizontal = clean_field_and_link(chart_json.get('Horizontal'))
        dims_str = clean_field_and_link(chart_json.get('Dimensions'))
        measures_str = clean_field_and_link(chart_json.get('Measures'))

        # Title (24px Bold)
        html_parts.append(f'<p><span style="font-size: 24px;"><strong>{chart_name}</strong></span></p>')
        html_parts.append(self.spacer)

        # Chart Image
        if image_url:
            html_parts.append('<p><strong>Chart Image:</strong></p>')
            html_parts.append(f'<p><img src="{image_url}" alt="{chart_name}" style="max-width: 100%; height: auto; border: 1px solid #e0e0e0; border-radius: 4px;"></p>')
            html_parts.append(self.spacer)

        # Category
        html_parts.append(f'<p><strong>Category:</strong> {category}</p>')
        html_parts.append(self.spacer)

        # Availability
        html_parts.append(f'<p><strong>Availability:</strong> {country}</p>')
        html_parts.append(self.spacer)

        # Shows
        html_parts.append('<p><strong>Shows:</strong></p>')
        html_parts.append(f'<p>{shows_text}</p>')
        html_parts.append(self.spacer)

        # Best Used For
        html_parts.append('<p><strong>Best used for:</strong></p>')
        html_parts.append(f'<p>{best_used_for}</p>')
        html_parts.append(self.spacer)

        # Considerations (moved after Best Used For)
        html_parts.append('<p><strong>Considerations:</strong></p>')
        html_parts.append(f'<p>{considerations}</p>')
        html_parts.append(self.spacer)

        # Axes
        html_parts.append('<p><strong>Axes:</strong></p>')
        html_parts.append('<ul>')
        html_parts.append(f'<li><strong>Vertical:</strong> {vertical}</li>')
        html_parts.append(f'<li><strong>Horizontal:</strong> {horizontal}</li>')
        html_parts.append('</ul>')
        html_parts.append(self.spacer)

        # Dimensions
        html_parts.append(f'<p><strong>Dimensions:</strong> {dims_str}</p>')
        html_parts.append(self.spacer)

        # Measures
        html_parts.append(f'<p><strong>Measures:</strong> {measures_str}</p>')
        html_parts.append(self.spacer)

        # Related Charts (new section)
        if related_charts_names and related_charts_urls:
            # Ensure both lists have same length
            if len(related_charts_names) == len(related_charts_urls):
                html_parts.append('<p><strong>Related Charts:</strong><ul>')

                for name, url in zip(related_charts_names, related_charts_urls):
                    if name and url:
                        html_parts.append(f'<li><a href="{url}" target="_blank">{name}</a></li>')
                    elif name:
                        html_parts.append(f'<li>{name}</li>')

                html_parts.append('</ul></p>')
                html_parts.append(self.spacer)

        # Related Articles (new section)
        if related_articles_names and related_articles_urls:
            # Ensure both lists have same length
            if len(related_articles_names) == len(related_articles_urls):
                html_parts.append('<p><strong>Related Articles:</strong><ul>')

                for name, url in zip(related_articles_names, related_articles_urls):
                    if name and url:
                        html_parts.append(f'<li><a href="{url}" target="_blank">{name}</a></li>')
                    elif name:
                        html_parts.append(f'<li>{name}</li>')

                html_parts.append('</ul></p>')
                html_parts.append(self.spacer)

        return "".join(html_parts)

    def format_article_with_charts_html(
        self,
        article_title: str,
        category: str,
        technology: str,
        charts_data: List[Dict]
    ) -> str:
        """
        Format article HTML with embedded chart images and descriptions

        Args:
            article_title: The article title
            category: Article category
            technology: Article technology
            charts_data: List of dicts with title, image_url, shows

        Returns:
            Formatted HTML string with charts embedded
        """
        html_parts = []

        # Clean title (remove parentheses content)
        clean_title = article_title.split('(')[0].strip()

        # Metadata Section
        if category:
            html_parts.append(f'<p><strong>Category:</strong> {category}</p>')
            html_parts.append(self.spacer)

        if technology:
            html_parts.append(f'<p><strong>Technology:</strong> {technology}</p>')
            html_parts.append(self.spacer)

        # Charts Loop
        for chart in charts_data:
            title = chart.get('title', '')
            image_url = chart.get('image_url', '')
            shows = chart.get('shows', 'No description provided.')
            intercom_url = chart.get('intercom_url', '')

            # Chart Title (bold with link if URL exists)
            if title:
                if intercom_url:
                    html_parts.append(f'<p><strong><a href="{intercom_url}">{title}</a></strong></p>')
                else:
                    html_parts.append(f'<p><strong>{title}</strong></p>')
                html_parts.append(self.spacer)

            # Image
            if image_url:
                img_tag = f'<img src="{image_url}" alt="{title}" style="max-width: 100%; height: auto;">'
                html_parts.append(f'<p>{img_tag}</p>')
                html_parts.append(self.spacer)

            # Shows Label
            html_parts.append('<p><strong>Shows:</strong></p>')

            # Shows Content
            html_parts.append(f'<p>{shows}</p>')

            # Spacing between charts
            html_parts.append(self.spacer)
            html_parts.append(self.spacer)

        return "".join(html_parts)

    def inject_related_charts_to_field_html(self, existing_html: str, related_charts_names: List[str], related_charts_urls: List[str]) -> str:
        """
        Inject or update Related Charts section in existing data field HTML

        Strategy:
        1. Check if "Related Charts:" section already exists
        2. If exists, replace it with updated list
        3. If not exists, insert before the <hr> divider at the end

        Args:
            existing_html: Existing data field HTML
            related_charts_names: List of chart titles
            related_charts_urls: List of chart URLs

        Returns:
            Updated HTML with Related Charts section
        """
        if not related_charts_names or not related_charts_urls:
            return existing_html

        # Build Related Charts HTML
        related_section = '<p><strong>Related Charts:</strong><ul>\n'
        for name, url in zip(related_charts_names, related_charts_urls):
            if name and url:
                related_section += f'<li><a href="{url}" target="_blank">{name}</a></li>\n'
            elif name:
                related_section += f'<li>{name}</li>\n'
        related_section += '</ul></p>\n<p>&nbsp;</p>\n'

        # Check if section already exists
        if '<strong>Related Charts:</strong>' in existing_html:
            # Replace existing section (find from "Related Charts" to next <hr> or end)
            import re
            pattern = r'<p><strong>Related Charts:</strong>.*?</p>\s*<p>&nbsp;</p>'
            updated_html = re.sub(pattern, related_section, existing_html, flags=re.DOTALL)
            return updated_html
        else:
            # Insert before final <hr> divider
            if '<hr>' in existing_html:
                return existing_html.replace('<hr>', related_section + '<hr>')
            else:
                # No divider, append to end
                return existing_html + '\n' + related_section

    def inject_related_articles_to_chart_html(self, existing_html: str, related_articles_names: List[str], related_articles_urls: List[str]) -> str:
        """
        Inject or update Related Articles section in existing chart HTML

        Strategy:
        1. Check if "Related Articles:" section already exists
        2. If exists, replace it with updated list
        3. If not exists, insert after "Related Charts:" section (if exists) or before final content

        Args:
            existing_html: Existing chart HTML
            related_articles_names: List of article titles
            related_articles_urls: List of article URLs

        Returns:
            Updated HTML with Related Articles section
        """
        if not related_articles_names or not related_articles_urls:
            return existing_html

        # Build Related Articles HTML
        related_section = '<p><strong>Related Articles:</strong><ul>\n'
        for name, url in zip(related_articles_names, related_articles_urls):
            if name and url:
                related_section += f'<li><a href="{url}" target="_blank">{name}</a></li>\n'
            elif name:
                related_section += f'<li>{name}</li>\n'
        related_section += '</ul></p>\n<p>&nbsp;</p>\n'

        # Check if section already exists
        if '<strong>Related Articles:</strong>' in existing_html:
            # Replace existing section
            import re
            pattern = r'<p><strong>Related Articles:</strong>.*?</p>\s*<p>&nbsp;</p>'
            updated_html = re.sub(pattern, related_section, existing_html, flags=re.DOTALL)
            return updated_html
        else:
            # Insert after Related Charts section if it exists, otherwise append to end
            if '<strong>Related Charts:</strong>' in existing_html:
                # Find end of Related Charts section and insert after
                import re
                # Insert after Related Charts section
                pattern = r'(<p><strong>Related Charts:</strong>.*?</p>\s*<p>&nbsp;</p>)'
                updated_html = re.sub(pattern, r'\1' + '\n' + related_section, existing_html, flags=re.DOTALL)
                return updated_html
            else:
                # Append to end of HTML
                return existing_html + '\n' + related_section
