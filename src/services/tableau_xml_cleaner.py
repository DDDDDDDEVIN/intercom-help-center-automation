"""
Tableau XML Cleaning Service
Downloads workbook XML and extracts chart data fields for analysis
"""
import requests
import zipfile
import io
import re
import xml.etree.ElementTree as ET
from typing import Dict


class TableauXMLCleaner:
    def __init__(self, base_url: str, site_id: str, auth_token: str):
        """
        Initialize Tableau XML Cleaner

        Args:
            base_url: Tableau server base URL
            site_id: Tableau site ID
            auth_token: Tableau authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.site_id = site_id
        self.auth_token = auth_token
        self.api_version = "3.20"

    def download_and_clean(self, workbook_id: str, target_view_name: str = '') -> Dict:
        """
        Download workbook XML and extract clean chart information

        Args:
            workbook_id: The Tableau workbook ID
            target_view_name: The view/sheet name to analyze

        Returns:
            Dictionary with status and analysis_context
        """
        url = f"{self.base_url}/api/{self.api_version}/sites/{self.site_id}/workbooks/{workbook_id}/content"
        headers = {
            "X-Tableau-Auth": self.auth_token,
            "Accept": "*/*"
        }

        try:
            response = requests.get(url, headers=headers, stream=True, timeout=45)
            response.raise_for_status()

            # Extract XML from ZIP or direct response
            workbook_xml = self._extract_xml_from_response(response)

            # Parse and clean XML
            root = ET.fromstring(workbook_xml)

            # Build field translation map
            field_map = self._build_field_map(root)

            # Find target worksheets
            targets = self._find_target_worksheets(root, target_view_name)

            # Extract and clean output
            final_output = self._extract_clean_output(targets, field_map)

            return {
                "status": "success",
                "analysis_context": "\n".join(final_output)
            }

        except Exception as e:
            return {
                "status": "error",
                "message": str(e)
            }

    def _extract_xml_from_response(self, response) -> str:
        """Extract XML content from ZIP or direct response"""
        workbook_xml = ""
        try:
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                twb_files = [f for f in z.namelist() if f.endswith('.twb')]
                if twb_files:
                    with z.open(twb_files[0]) as f:
                        workbook_xml = f.read().decode('utf-8')
        except zipfile.BadZipFile:
            workbook_xml = response.text

        return workbook_xml

    def _build_field_map(self, root) -> Dict[str, str]:
        """Build translation dictionary for field names"""
        field_map = {}
        for col in root.findall('.//column'):
            name = col.get('name')
            caption = col.get('caption')
            if name:
                clean_id = name.replace('[', '').replace(']', '')
                display = caption if caption else clean_id
                field_map[name] = display
                field_map[clean_id] = display

        return field_map

    def _find_target_worksheets(self, root, target_name: str) -> list:
        """Find target worksheets by name"""
        targets = []
        target_norm = target_name.lower().replace(" ", "") if target_name else ""

        # Search in worksheets
        for ws in root.findall('.//worksheet'):
            if target_norm and target_norm in ws.get('name', '').lower().replace(" ", ""):
                targets.append(ws)

        # If not found, search in dashboards
        if not targets:
            for dashboard in root.findall('.//dashboard'):
                if target_norm and target_norm in dashboard.get('name', '').lower().replace(" ", ""):
                    for zone in dashboard.findall('.//zone'):
                        ref = zone.get('name')
                        for ws in root.findall('.//worksheet'):
                            if ws.get('name') == ref:
                                targets.append(ws)
                    break

        return targets

    def _clean_tableau_text(self, text: str, field_map: Dict[str, str]) -> str:
        """
        Strongly clean and parse Tableau field text
        Extracts individual field names from complex expressions
        """
        if not text or text == "None":
            return "None"

        # A. Translate field names
        for fid, fname in field_map.items():
            if fid in text:
                text = text.replace(fid, fname)

        # B. Remove [sqlproxy...] prefixes
        text = re.sub(r'\[[^\]]+\.[^\]]+\]\.', '', text)

        # C. Clean prefixes and suffixes
        text = re.sub(r'\b(sum|none|avg|min|max|attr|usr|tmn|pcto|win|med|pcdf|mn):', '', text, flags=re.IGNORECASE)
        text = re.sub(r':(qk|nk|ok)', '', text)
        text = re.sub(r':[0-9]+', '', text)

        # D. Remove wrapping symbols
        text = text.replace('[', '').replace(']', '').replace('"', '').replace('(', '').replace(')', '')

        # E. Core breakdown: split by * or /
        # This converts "INDEX * Capacity" to ["INDEX", "Capacity"]
        # This converts "INDEX / Brand" to ["INDEX", "Brand"]
        parts = re.split(r'[\*/]', text)

        clean_parts = []
        for p in parts:
            p = p.strip()
            # Filter empty strings and deduplicate
            if p and p not in clean_parts:
                clean_parts.append(p)

        # Rejoin with comma
        return ", ".join(clean_parts)

    def _extract_clean_output(self, targets: list, field_map: Dict[str, str]) -> list:
        """Extract clean output from target worksheets"""
        final_output = []

        if targets:
            seen_sheets = set()
            for ws in targets:
                sheet_name = ws.get('name')
                if sheet_name in seen_sheets:
                    continue
                seen_sheets.add(sheet_name)

                # Extract title
                title = "No Title"
                title_node = ws.find('.//title//run')
                if title_node is not None and title_node.text:
                    title = title_node.text

                # Extract table structure
                table = ws.find('table')
                rows_clean = "None"
                cols_clean = "None"

                if table is not None:
                    r_node = table.find('rows')
                    if r_node is not None:
                        rows_raw = "".join(r_node.itertext()).strip()
                        rows_clean = self._clean_tableau_text(rows_raw, field_map)

                    c_node = table.find('cols')
                    if c_node is not None:
                        cols_raw = "".join(c_node.itertext()).strip()
                        cols_clean = self._clean_tableau_text(cols_raw, field_map)

                # Extract filters
                filters = set()
                for f in ws.findall('.//filter'):
                    col = f.get('column')
                    if col:
                        clean_f = self._clean_tableau_text(col, field_map)
                        if "Action" not in clean_f and "Measure Names" not in clean_f:
                            filters.add(clean_f)

                summary = f"""
=== Chart: {sheet_name} ===
Title: {title}
Y-Axis: {rows_clean}
X-Axis: {cols_clean}
Filters: {', '.join(list(filters)[:5])}
"""
                final_output.append(summary)
        else:
            final_output.append("No matching charts found.")

        return final_output
