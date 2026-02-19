"""
Data Field Analysis Service
Processes individual data fields with deep XML context extraction
"""
import requests
import zipfile
import io
import re
import json
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Dict, List, Tuple


class DataFieldAnalyzer:
    def __init__(self, base_url: str, site_id: str, auth_token: str):
        """
        Initialize Data Field Analyzer

        Args:
            base_url: Tableau server base URL
            site_id: Tableau site ID
            auth_token: Tableau authentication token
        """
        self.base_url = base_url.rstrip('/')
        self.site_id = site_id
        self.auth_token = auth_token
        self.api_version = "3.20"

    def extract_field_contexts(self, workbook_id: str, target_fields: List[str]) -> Dict:
        """
        Extract detailed context for each data field from workbook XML

        Args:
            workbook_id: The Tableau workbook ID
            target_fields: List of field names to analyze

        Returns:
            Dictionary with field_names and field_contexts lists
        """
        # Parse target fields list
        target_field_list = self._parse_target_fields(target_fields)

        # Clean and normalize target list
        clean_targets_map = self._clean_target_list(target_field_list)

        # Download XML
        workbook_xml = self._download_workbook_xml(workbook_id)

        # Parse XML and build knowledge base
        root = ET.fromstring(workbook_xml)
        id_to_human, field_map = self._build_knowledge_base(root)

        # Generate context for each field
        name_list = []
        context_list = []

        for top_norm_key, top_name in clean_targets_map.items():
            result_lines = self._generate_context_tree(
                top_norm_key,
                field_map,
                id_to_human,
                root,
                workbook_xml
            )
            full_context_text = "\n".join(result_lines)

            name_list.append(top_name)
            context_list.append(full_context_text)

        return {
            "field_names": name_list,
            "field_contexts": context_list,
            "total_count": len(name_list)
        }

    def _parse_target_fields(self, raw_targets) -> List[str]:
        """Parse target fields from various input formats"""
        target_field_list = []

        if isinstance(raw_targets, list):
            target_field_list = raw_targets
        elif isinstance(raw_targets, str):
            try:
                parsed = json.loads(raw_targets)
                if isinstance(parsed, list):
                    target_field_list = parsed
                elif isinstance(parsed, dict):
                    for v in parsed.values():
                        if isinstance(v, list):
                            target_field_list.extend(v)
                else:
                    target_field_list = raw_targets.split(',')
            except:
                target_field_list = raw_targets.split(',')

        return target_field_list

    @staticmethod
    def clean_tableau_field_name(text: str) -> str:
        """
        Clean Tableau field name by removing prefixes, suffixes, and decomposing formulas

        Args:
            text: Raw field name from Tableau/GPT

        Returns:
            Cleaned field name (or comma-separated list if formula decomposed)
        """
        if not text or text == "None":
            return "None"

        # A. Remove data type prefixes (yr:, mn:, dt:, etc.)
        text = re.sub(r'^[a-z]+:', '', text)

        # B. Remove SQL proxy prefixes like [sqlproxy.xxx].
        text = re.sub(r'\[[^\]]+\.[^\]]+\]\.', '', text)

        # C. Remove aggregation prefixes and suffixes
        text = re.sub(r'\b(sum|none|avg|min|max|attr|usr|tmn|pcto|mn):', '', text, flags=re.IGNORECASE)
        text = re.sub(r':(qk|nk|ok)', '', text, flags=re.IGNORECASE)
        text = re.sub(r':[0-9]+', '', text)

        # D. Remove wrapping symbols
        text = text.replace('[', '').replace(']', '').replace('"', '').replace('(', '').replace(')', '')

        # E. Decompose formulas: split on * or /
        # This converts "INDEX * Capacity" to "INDEX, Capacity"
        parts = re.split(r'[\*/]', text)

        clean_parts = []
        for p in parts:
            p = p.strip()
            if p and p not in clean_parts:
                clean_parts.append(p)

        return ", ".join(clean_parts)

    def _clean_target_list(self, target_field_list: List[str]) -> Dict[str, str]:
        """Clean and deduplicate target field list"""
        clean_targets_map = {}

        for t in target_field_list:
            if t and str(t).lower() != 'none':
                # Clean the field name using Tableau cleaning logic
                cleaned = self.clean_tableau_field_name(str(t).strip())

                # Handle comma-separated results from formula decomposition
                for clean_item in cleaned.split(','):
                    clean_item = clean_item.strip()
                    if clean_item:
                        norm_key = clean_item.lower().replace(" ", "").replace("-", "")
                        # Keep first occurrence
                        if norm_key not in clean_targets_map:
                            clean_targets_map[norm_key] = clean_item

        return clean_targets_map

    def _download_workbook_xml(self, workbook_id: str) -> str:
        """Download workbook XML content"""
        url = f"{self.base_url}/api/{self.api_version}/sites/{self.site_id}/workbooks/{workbook_id}/content"
        headers = {
            "X-Tableau-Auth": self.auth_token,
            "Accept": "*/*"
        }

        try:
            response = requests.get(url, headers=headers, stream=True, timeout=45)
            response.raise_for_status()

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

        except Exception as e:
            raise Exception(f"Failed to download workbook XML: {str(e)}")

    def _build_knowledge_base(self, root) -> Tuple[Dict, Dict]:
        """Build field knowledge base from XML"""
        id_to_human = {}
        field_map = {}

        for datasource in root.findall('.//datasource'):
            for col in datasource.findall('.//column'):
                name = col.get('name') or ""
                caption = col.get('caption') or ""
                role = col.get('role') or "dimension"
                datatype = col.get('type') or "string"

                # ID translation
                if name and caption:
                    id_to_human[name] = f"[{caption}]"
                    raw_id = name.replace('[', '').replace(']', '')
                    id_to_human[raw_id] = caption

                display_name = caption if caption else name
                if not display_name:
                    continue

                norm_key = display_name.replace('[', '').replace(']', '').lower().replace(" ", "").replace("-", "")

                info = {
                    "raw_name": display_name,
                    "norm_key": norm_key,
                    "role": role,
                    "datatype": datatype,
                    "is_calc": False,
                    "formula": None
                }

                calc = col.find('calculation')
                if calc is not None:
                    formula = calc.get('formula')
                    if formula:
                        info["is_calc"] = True
                        info["formula"] = formula

                field_map[norm_key] = info

        return id_to_human, field_map

    def _translate_formula(self, raw_formula: str, id_to_human: Dict) -> str:
        """Translate formula IDs to human-readable names"""
        if not raw_formula:
            return ""

        clean = " ".join(raw_formula.split())
        for raw_id, human_name in sorted(id_to_human.items(), key=lambda x: len(x[0]), reverse=True):
            if raw_id in clean:
                clean = clean.replace(raw_id, human_name)

        return clean

    def _scrape_filter_values(self, target_name_raw: str, workbook_xml: str) -> List[str]:
        """Scrape text filter values (Member Values)"""
        found_values = set()
        clean_name = target_name_raw.replace('[', '').replace(']', '')
        safe_name = re.escape(clean_name)
        pattern_str = fr"level='[^']*{safe_name}[^']*'.*?member='([^']*)'"
        matches = re.findall(pattern_str, workbook_xml, re.IGNORECASE | re.DOTALL)

        for m in matches:
            val = m.replace("&quot;", "").replace('"', '')
            val = urllib.parse.unquote(val)
            if val and val.lower() != "%null%":
                found_values.add(val)

        return sorted(list(found_values))

    def _scrape_range_limits(self, target_name_raw: str, root) -> str:
        """Scrape numeric range limits"""
        clean_name = target_name_raw.replace('[', '').replace(']', '')
        candidates = []

        for f in root.findall('.//filter'):
            col = f.get('column')
            if col and clean_name in col:
                min_val = f.get('min')
                max_val = f.get('max')

                if min_val is None:
                    child = f.find('min')
                    if child is not None:
                        min_val = child.text

                if max_val is None:
                    child = f.find('max')
                    if child is not None:
                        max_val = child.text

                if min_val or max_val:
                    candidates.append(f"Min: {min_val if min_val else '-Inf'}, Max: {max_val if max_val else 'Inf'}")

        if candidates:
            return candidates[0]
        return None

    def _generate_context_tree(
        self,
        norm_key: str,
        field_map: Dict,
        id_to_human: Dict,
        root,
        workbook_xml: str,
        current_depth: int = 0,
        visited: set = None
    ) -> List[str]:
        """Recursively generate context tree for a field"""
        if visited is None:
            visited = set()

        indent = "  " * current_depth
        prefix = "└─ " if current_depth > 0 else ""

        if current_depth > 5:
            return [f"{indent}{prefix}(Max depth reached)"]
        if norm_key in visited:
            return [f"{indent}{prefix}(Recursive reference loop)"]

        visited.add(norm_key)

        if norm_key not in field_map:
            return [f"{indent}{prefix}Field not found in metadata"]

        info = field_map[norm_key]
        lines = []

        if info["is_calc"]:
            human_formula = self._translate_formula(info["formula"], id_to_human)
            lines.append(f"{indent}{prefix}FIELD: [{info['raw_name']}] (Calculation)")
            lines.append(f"{indent}   Formula: {human_formula}")

            dependencies = re.findall(r"\[([^\]]+)\]", human_formula)
            if dependencies:
                unique_deps = sorted(list(set(dependencies)))
                for dep_name in unique_deps:
                    dep_norm = dep_name.lower().replace(" ", "").replace("-", "")
                    if dep_norm != norm_key:
                        lines.extend(
                            self._generate_context_tree(
                                dep_norm,
                                field_map,
                                id_to_human,
                                root,
                                workbook_xml,
                                current_depth + 1,
                                visited.copy()
                            )
                        )
        else:
            lines.append(f"{indent}{prefix}FIELD: [{info['raw_name']}] (Native {info['datatype']})")

            if info['role'] == 'measure' and info['datatype'] in ['integer', 'real']:
                range_info = self._scrape_range_limits(info['raw_name'], root)
                if range_info:
                    lines.append(f"{indent}   Filter Range Found: {range_info}")
                else:
                    lines.append(f"{indent}   Values: (Numeric Measure - No hardcoded filter range found)")
            else:
                vals = self._scrape_filter_values(info['raw_name'], workbook_xml)
                if vals:
                    preview = ", ".join(vals[:15]) + ("..." if len(vals) > 15 else "")
                    lines.append(f"{indent}   Categories: {preview}")
                else:
                    lines.append(f"{indent}   Values: (No explicit filter values)")

        return lines
