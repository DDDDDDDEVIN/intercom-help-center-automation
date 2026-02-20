"""
Duplicate Check Service using Google Sheets
Checks if a chart already exists in Google Sheets to prevent duplicates
"""
import requests
from typing import Dict, List


class GoogleSheetsService:
    def __init__(self, sheet_api_url: str):
        """
        Initialize Google Sheets service

        Args:
            sheet_api_url: Google Apps Script Web App URL (must end with /exec)
        """
        self.sheet_api_url = sheet_api_url

    def check_duplicate(self, lookup_name: str, sheet_name: str = 'Sheet1') -> Dict:
        """
        Check if a value exists in the first column of a Google Sheet

        Args:
            lookup_name: The value to search for
            sheet_name: The name of the sheet to search in

        Returns:
            Dictionary with 'exists' boolean and metadata
        """
        # Safety Check 1: Input validation
        lookup_value = lookup_name.strip()
        target_sheet = sheet_name.strip()

        if not lookup_value:
            raise Exception("❌ Check Failed: Input 'lookup_name' is empty. Cannot verify duplicate.")

        # Prepare request
        params = {
            "sheet_name": target_sheet
        }

        try:
            # Send request
            response = requests.get(
                self.sheet_api_url,
                params=params,
                allow_redirects=True,
                timeout=60
            )

            # Safety Check 2: HTTP request failed
            if response.status_code != 200:
                raise Exception(
                    f"❌ API Connection Failed: Status Code {response.status_code}. "
                    f"Response: {response.text}"
                )

            # Parse data
            all_rows = response.json()

            # Safety Check 3: Google Script returned logical error
            if isinstance(all_rows, dict) and "error" in all_rows:
                raise Exception(f"❌ Google Sheet Script Error: {all_rows['error']}")

        except requests.exceptions.RequestException as e:
            # Safety Check 4: Catch all other exceptions
            raise Exception(f"❌ System Error during Check: {str(e)}")

        # Core duplicate checking logic
        is_found = False
        found_human_name = ''
        found_url = ''

        # Iterate through each row, check first column (row[0])
        for row in all_rows:
            # Ensure this row has data
            if isinstance(row, list) and len(row) > 0:
                # Convert to string for comparison (strip whitespace)
                if str(row[0]).strip() == lookup_value:
                    is_found = True
                    # Extract human_name (column 1) and URL (column 2) if available
                    if len(row) > 1:
                        found_human_name = str(row[1]).strip()
                    if len(row) > 2:
                        found_url = str(row[2]).strip()
                    break

        # Return result
        return {
            'exists': is_found,
            'lookup_value': lookup_value,
            'checked_sheet': target_sheet,
            'human_name': found_human_name,
            'intercom_url': found_url
        }

    def lookup_article_by_title(self, article_title: str, sheet_name: str = 'article_library') -> Dict:
        """
        Lookup article in Google Sheets by title and return Intercom ID

        Args:
            article_title: The article title to search for (matches original_name column)
            sheet_name: The sheet name to search in (default: 'article_library')

        Returns:
            Dictionary with exists, intercom_id, intercom_url, and html
            Format: {
                'exists': bool,
                'intercom_id': str,
                'intercom_url': str,
                'html': str
            }
        """
        # Use existing check_duplicate to verify existence
        result = self.check_duplicate(lookup_name=article_title, sheet_name=sheet_name)

        if result['exists']:
            # Fetch full row to get intercom_id (column 3) and html (column 4)
            params = {"sheet_name": sheet_name}

            try:
                response = requests.get(
                    self.sheet_api_url,
                    params=params,
                    allow_redirects=True,
                    timeout=60
                )

                if response.status_code == 200:
                    all_rows = response.json()

                    # Find the matching row
                    for row in all_rows:
                        if len(row) > 0 and str(row[0]).strip() == article_title.strip():
                            return {
                                'exists': True,
                                'intercom_id': str(row[3]).strip() if len(row) > 3 else '',
                                'intercom_url': str(row[2]).strip() if len(row) > 2 else '',
                                'html': row[4] if len(row) > 4 else ''
                            }
            except requests.exceptions.RequestException:
                pass

        return {
            'exists': False,
            'intercom_id': '',
            'intercom_url': '',
            'html': ''
        }

    def log_processed_item(
        self,
        original_name: str,
        human_name: str,
        intercom_url: str,
        intercom_id: str,
        html: str,
        sheet_name: str = 'data_dictionary'
    ) -> Dict:
        """
        Log a processed item to Google Sheets with 5 columns

        Args:
            original_name: The original name before any formatting
            human_name: The human-readable name (after formatting)
            intercom_url: The Intercom article URL
            intercom_id: The Intercom article ID
            html: The complete HTML content
            sheet_name: The sheet name to write to

        Returns:
            Dictionary with save status
        """
        # Prepare payload for Google Sheet
        payload = {
            "sheet_name": sheet_name,
            "original_name": original_name.strip(),
            "human_name": human_name.strip(),
            "intercom_url": intercom_url.strip(),
            "intercom_id": str(intercom_id).strip(),
            "HTML": html
        }

        try:
            # Send POST request
            response = requests.post(
                self.sheet_api_url,
                json=payload,
                allow_redirects=True,
                timeout=60
            )

            if response.status_code == 200:
                return {
                    'status': 'success',
                    'message': f'Saved to {sheet_name}: {original_name}',
                    'saved_data': payload
                }
            else:
                return {
                    'status': 'error',
                    'message': f'API Error: {response.status_code}',
                    'response': response.text
                }

        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f"Failed to log to Google Sheets: {str(e)}"
            }

    def delete_row_by_value(
        self,
        value_to_match: str,
        column_index: int = 1,
        sheet_name: str = 'Sheet1'
    ) -> Dict:
        """
        Delete row(s) from Google Sheets by matching a value in a specific column

        Args:
            value_to_match: The value to search for
            column_index: Column index to search in (1-based, default 1 for column A)
            sheet_name: The sheet name to delete from

        Returns:
            Dictionary with deletion status
        """
        # Prepare payload
        payload = {
            "action": "delete",
            "sheet_name": sheet_name,
            "column_index": column_index,
            "value_to_match": value_to_match.strip()
        }

        try:
            # Send POST request
            response = requests.post(
                self.sheet_api_url,
                json=payload,
                allow_redirects=True,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()

                if result.get('status') == 'success':
                    return {
                        'status': 'success',
                        'message': f"Deleted {result.get('rows_deleted', 0)} row(s) from {sheet_name}",
                        'rows_deleted': result.get('rows_deleted', 0)
                    }
                else:
                    return {
                        'status': 'error',
                        'message': result.get('message', 'Unknown error')
                    }
            else:
                return {
                    'status': 'error',
                    'message': f'API Error: {response.status_code}',
                    'response': response.text
                }

        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': f"Failed to delete from Google Sheets: {str(e)}"
            }

    def batch_lookup(self, search_list: List[str], sheet_name: str = 'data_dictionary') -> Dict:
        """
        Batch lookup multiple items in Google Sheets (single API call)

        Args:
            search_list: List of field names to look up
            sheet_name: Sheet name to search in

        Returns:
            Dictionary with url_list and human_name_list (parallel arrays)
        """
        # Parse input list
        if isinstance(search_list, str):
            try:
                import json
                search_list = json.loads(search_list)
            except:
                search_list = [x.strip() for x in search_list.split(',') if x.strip()]

        # Get all rows from sheet (single API call)
        params = {"sheet_name": sheet_name}

        try:
            response = requests.get(
                self.sheet_api_url,
                params=params,
                allow_redirects=True,
                timeout=60
            )

            if response.status_code != 200:
                return {
                    'status': 'error',
                    'message': 'Sheet API Error',
                    'url_list': [],
                    'human_name_list': []
                }

            all_rows = response.json()

        except requests.exceptions.RequestException as e:
            return {
                'status': 'error',
                'message': str(e),
                'url_list': [],
                'human_name_list': []
            }

        # Build lookup map (O(1) lookup speed)
        # Assuming sheet columns: [original_name, human_name, intercom_url, intercom_id, HTML]
        lookup_map = {}

        for row in all_rows:
            if len(row) >= 3:
                t_name = str(row[0]).strip()  # original_name (Key)
                h_name = str(row[1]).strip()  # human_name
                i_url = str(row[2]).strip()   # intercom_url

                lookup_map[t_name] = {
                    'human_name': h_name,
                    'url': i_url
                }

                # Store additional fields if available
                if len(row) >= 4:
                    lookup_map[t_name]['intercom_id'] = str(row[3]).strip()
                if len(row) >= 5:
                    lookup_map[t_name]['html'] = row[4]

        # Match each item in search list
        found_urls = []
        found_humans = []
        missing_items = []

        for item in search_list:
            clean_key = str(item).strip()

            if clean_key in lookup_map:
                record = lookup_map[clean_key]
                found_urls.append(record['url'])
                found_humans.append(record['human_name'])
            else:
                # If not found, add empty string to maintain list alignment
                found_urls.append("")
                found_humans.append("")
                missing_items.append(clean_key)

        return {
            'status': 'success',
            'url_list': found_urls,
            'human_name_list': found_humans,
            'total_count': len(search_list),
            'found_count': len(search_list) - len(missing_items),
            'missing_items': missing_items
        }

    def get_related_charts_for_field(self, field_name: str, sheet_name: str = 'chart_library') -> Dict:
        """
        Find all charts that reference this data field by searching chart HTML

        Args:
            field_name: The field name to search for
            sheet_name: Chart library sheet name

        Returns:
            {'status': 'success', 'related_charts': [{'title': str, 'url': str}], 'total_count': int}
        """
        params = {"sheet_name": sheet_name}

        try:
            response = requests.get(
                self.sheet_api_url,
                params=params,
                allow_redirects=True,
                timeout=60
            )

            if response.status_code != 200:
                return {'status': 'error', 'related_charts': []}

            all_rows = response.json()
            related_charts = []

            # Search HTML column (index 4) for field name references
            for row in all_rows:
                if len(row) >= 5:
                    html_content = str(row[4])
                    # Check if field appears in HTML (in links or text)
                    if field_name in html_content:
                        chart_title = str(row[1]).strip()  # human_name
                        chart_url = str(row[2]).strip()    # intercom_url
                        related_charts.append({
                            'title': chart_title,
                            'url': chart_url
                        })

            return {
                'status': 'success',
                'related_charts': related_charts,
                'total_count': len(related_charts)
            }

        except requests.exceptions.RequestException:
            return {'status': 'error', 'related_charts': []}

    def get_related_articles_for_chart(self, chart_title: str, sheet_name: str = 'article_library') -> Dict:
        """
        Find all articles that reference this chart

        Args:
            chart_title: The chart title to search for
            sheet_name: Article library sheet name

        Returns:
            {'status': 'success', 'related_articles': [{'title': str, 'url': str}], 'total_count': int}
        """
        params = {"sheet_name": sheet_name}

        try:
            response = requests.get(
                self.sheet_api_url,
                params=params,
                allow_redirects=True,
                timeout=60
            )

            if response.status_code != 200:
                return {'status': 'error', 'related_articles': []}

            all_rows = response.json()
            related_articles = []

            # Search HTML column (index 4) for chart title references
            for row in all_rows:
                if len(row) >= 5:
                    html_content = str(row[4])
                    if chart_title in html_content:
                        article_title = str(row[1]).strip()
                        article_url = str(row[2]).strip()
                        related_articles.append({
                            'title': article_title,
                            'url': article_url
                        })

            return {
                'status': 'success',
                'related_articles': related_articles,
                'total_count': len(related_articles)
            }

        except requests.exceptions.RequestException:
            return {'status': 'error', 'related_articles': []}
