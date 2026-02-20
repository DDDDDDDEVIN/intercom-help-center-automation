"""
Step 4 & 5: Tableau Authentication and Token/Site ID Extraction
Handles Tableau sign-in and extracts authentication tokens
"""
import requests
import xml.etree.ElementTree as ET
from typing import Dict, Tuple


class TableauService:
    def __init__(self, server_url: str, username: str, password: str, site_name: str = ""):
        self.server_url = server_url.rstrip('/')
        self.username = username
        self.password = password
        self.site_name = site_name
        self.auth_token = None
        self.site_id = None

    def sign_in(self) -> Dict[str, str]:
        """
        Step 4: Sign in to Tableau Server

        Returns:
            Dictionary containing XML response string
        """
        url = f"{self.server_url}/api/3.19/auth/signin"

        # Build sign-in request XML
        payload = f"""
        <tsRequest>
            <credentials name="{self.username}" password="{self.password}">
                <site contentUrl="{self.site_name}" />
            </credentials>
        </tsRequest>
        """.strip()

        headers = {
            'Content-Type': 'application/xml',
            'Accept': 'application/xml'
        }

        try:
            response = requests.post(url, data=payload, headers=headers, timeout=60)
            response.raise_for_status()

            xml_string = response.text

            # Extract token and site ID
            self.extract_credentials(xml_string)

            return {
                'xml_string': xml_string,
                'auth_token': self.auth_token,
                'site_id': self.site_id
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to sign in to Tableau: {str(e)}")

    def extract_credentials(self, xml_string: str) -> Tuple[str, str]:
        """
        Step 5: Extract authentication token and site ID from XML response

        Args:
            xml_string: XML response from Tableau sign-in API

        Returns:
            Tuple of (auth_token, site_id)
        """
        try:
            # Parse the XML
            root = ET.fromstring(xml_string)

            # Define namespaces (Key point for Tableau API)
            ns = {'t': 'http://tableau.com/api'}

            # Find the credentials tag and extract the token
            creds = root.find('.//t:credentials', ns)
            token = creds.get('token') if creds is not None else "Token Not Found"

            # Find the site tag and extract the id
            site = root.find('.//t:site', ns)
            site_id = site.get('id') if site is not None else "SiteID Not Found"

            # Store for later use
            self.auth_token = token
            self.site_id = site_id

            return token, site_id

        except Exception as e:
            raise Exception(f"Failed to extract credentials from XML: {str(e)}")

    def get_headers(self) -> Dict[str, str]:
        """Get headers for authenticated Tableau API requests"""
        if not self.auth_token:
            raise Exception("Not authenticated. Call sign_in() first.")

        return {
            'X-Tableau-Auth': self.auth_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def search_workbooks(self, view_name: str) -> Dict[str, list]:
        """
        Search for views by name and extract workbook information

        API Endpoint: /api/3.20/sites/{site_id}/views?filter=viewUrlName:eq:{view_name}

        Args:
            view_name: The view name to search for (tabs_name from chart)

        Returns:
            Dictionary containing lists of project_ids and workbook_ids
        """
        if not self.auth_token or not self.site_id:
            raise Exception("Not authenticated. Call sign_in() first.")

        url = f"{self.server_url}/api/3.20/sites/{self.site_id}/views?filter=name:eq:{view_name}"

        # Use XML headers for consistency with sign_in
        headers = {
            'X-Tableau-Auth': self.auth_token,
            'Accept': 'application/json'
        }

        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()

            # Parse JSON response
            data = response.json()

            project_ids = []
            workbook_ids = []

            # Extract workbook and project IDs from views
            views = data.get('views', {}).get('view', [])

            for view in views:
                workbook = view.get('workbook', {})
                workbook_id = workbook.get('id')

                project = view.get('project', {})
                project_id = project.get('id')

                if workbook_id and project_id:
                    workbook_ids.append(workbook_id)
                    project_ids.append(project_id)

            return {
                'project_ids': project_ids,
                'workbook_ids': workbook_ids
            }

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search workbooks: {str(e)}")

    def select_workbook_id(self, project_ids: list, workbook_ids: list, target_project_id: str) -> Dict:
        """
        Select the correct workbook ID based on target project ID

        Args:
            project_ids: List of project IDs from search
            workbook_ids: List of workbook IDs from search
            target_project_id: The Global Project ID to match

        Returns:
            Dictionary with status and selected workbook_id
        """
        # Helper function to ensure input is a list
        def to_list(val):
            if isinstance(val, list):
                return val
            if isinstance(val, str):
                if "," in val:
                    return [x.strip() for x in val.split(',')]
                else:
                    return [val.strip()]
            return []

        p_list = to_list(project_ids)
        w_list = to_list(workbook_ids)

        found_workbook_id = None
        match_index = -1

        # Core logic: Loop over Project ID, find index
        for index, pid in enumerate(p_list):
            if pid == target_project_id:
                match_index = index
                # Safety check: ensure workbook list also has this index
                if index < len(w_list):
                    found_workbook_id = w_list[index]
                break

        if found_workbook_id:
            return {
                "status": "success",
                "match_found": True,
                "target_project_id": target_project_id,
                "matched_index": match_index,
                "workbook_id": found_workbook_id
            }
        else:
            return {
                "status": "error",
                "message": "Global Project ID not found in the list",
                "scanned_ids": p_list
            }
