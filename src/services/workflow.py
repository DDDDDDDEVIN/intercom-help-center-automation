"""
Workflow Orchestrator
Coordinates the execution of all steps in the automation
"""
from typing import Dict, Any, List
from .joomla_service import JoomlaService
from .html_cleaner import HTMLCleaner
from .tableau_service import TableauService
from .google_sheets_service import GoogleSheetsService
from .tableau_xml_cleaner import TableauXMLCleaner
from .chatgpt_service import ChatGPTService
from .data_field_analyzer import DataFieldAnalyzer
from .html_formatter import HTMLFormatter
from .intercom_service import IntercomService
from .relationship_service import RelationshipService
from .logger import Logger


class WorkflowOrchestrator:
    def __init__(
        self,
        joomla_base_url: str,
        joomla_api_endpoint: str,
        joomla_api_token: str,
        tableau_server_url: str,
        tableau_username: str,
        tableau_password: str,
        tableau_site_name: str,
        tableau_global_project_id: str,
        google_sheets_api_url: str,
        openai_api_key: str,
        openai_model: str,
        intercom_api_token: str,
        intercom_collection_id: str,
        google_sheets_data_dict_sheet: str = 'data_dictionary',
        google_sheets_chart_library_sheet: str = 'chart_library',
        google_sheets_article_library_sheet: str = 'article_library',
        intercom_author_id: str = None,
        intercom_data_dict_collection_id: str = None,
        intercom_chart_collection_id: str = None,
        intercom_article_collection_id: str = None,
        openai_image_detail: str = 'high',
        openai_text_model: str = 'gpt-4o'
    ):
        self.joomla_service = JoomlaService(
            base_url=joomla_base_url,
            api_endpoint=joomla_api_endpoint,
            api_token=joomla_api_token
        )
        self.html_cleaner = HTMLCleaner()
        self.tableau_service = TableauService(
            server_url=tableau_server_url,
            username=tableau_username,
            password=tableau_password,
            site_name=tableau_site_name
        )
        self.google_sheets_service = GoogleSheetsService(
            sheet_api_url=google_sheets_api_url
        )
        self.chatgpt_service = ChatGPTService(
            api_key=openai_api_key,
            model=openai_model,
            image_detail=openai_image_detail,
            text_model=openai_text_model
        )
        self.html_formatter = HTMLFormatter()
        self.intercom_service = IntercomService(
            api_token=intercom_api_token,
            collection_id=intercom_collection_id,
            data_dict_collection_id=intercom_data_dict_collection_id,
            chart_collection_id=intercom_chart_collection_id,
            article_collection_id=intercom_article_collection_id
        )
        self.relationship_service = RelationshipService(
            google_sheets_service=self.google_sheets_service,
            html_formatter=self.html_formatter,
            intercom_service=self.intercom_service
        )

        # Configuration
        self.tableau_global_project_id = tableau_global_project_id
        self.google_sheets_data_dict_sheet = google_sheets_data_dict_sheet
        self.google_sheets_chart_library_sheet = google_sheets_chart_library_sheet
        self.google_sheets_article_library_sheet = google_sheets_article_library_sheet
        self.intercom_api_token = intercom_api_token
        self.intercom_collection_id = intercom_collection_id
        self.intercom_author_id = intercom_author_id

        # Initialize logger
        self.logger = Logger(log_dir='logs', log_level='INFO')

    @staticmethod
    def _smart_chart_title(text: str) -> str:
        """
        Apply smart title case formatting to chart titles

        Args:
            text: Original chart title

        Returns:
            Formatted chart title with proper capitalization
        """
        import re

        if not text:
            return ""

        # Whitelist: Key must be all lowercase, Value is the final format
        special_cases = {
            "pv": "PV",
            "ess": "ESS",
            "kw": "kW",
            "kwh": "kWh",
            "mw": "MW",
            "gw": "GW",
            "dc": "DC",
            "ac": "AC",
            "bess": "BESS",
            "ev": "EV",
            "roi": "ROI",
            "yoy": "YoY",
            "qoq": "QoQ",
            "lcoe": "LCOE"
        }

        # Small words (keep lowercase unless at the beginning)
        small_words = {
            'a', 'an', 'the', 'and', 'but', 'or', 'nor', 'at', 'by',
            'for', 'from', 'in', 'into', 'of', 'off', 'on', 'onto',
            'out', 'over', 'up', 'with', 'to', 'as', 'per'
        }

        # Split while preserving spaces, hyphens, and slashes
        tokens = re.split(r'(\s+|-|/)', text)

        processed_tokens = []
        first_word_found = False

        for token in tokens:
            # If it's a separator (space, hyphen, slash), keep as-is
            if not token.strip() or token in ['-', '/']:
                processed_tokens.append(token)
                continue

            # Process words
            lower_token = token.lower()

            # A. Check whitelist (highest priority)
            if lower_token in special_cases:
                processed_tokens.append(special_cases[lower_token])
                first_word_found = True

            # B. Check if it's a small word (and not the first word)
            elif first_word_found and lower_token in small_words:
                processed_tokens.append(lower_token)

            # C. Normal word (capitalize first letter)
            else:
                processed_tokens.append(token.capitalize())
                first_word_found = True

        return "".join(processed_tokens)

    def _clean_chart_json_fields(self, chart_json: Dict) -> Dict:
        """
        Clean all field names in chart JSON structure by removing Tableau prefixes

        Args:
            chart_json: Chart JSON with Vertical, Horizontal, Dimensions, Measures

        Returns:
            Chart JSON with cleaned field names
        """
        cleaned = chart_json.copy()

        def _parse_display_name(dn):
            if dn and str(dn).strip().lower() not in ('null', 'none', ''):
                return str(dn).strip()
            return None

        def _normalize_item(item) -> dict:
            """Normalize to {'field': original_str, 'display_name': str|None}.
            Keep field name UNCHANGED so it matches field_mapping keys.
            display_name is used for rendering; field is used for URL lookup."""
            if isinstance(item, dict):
                return {
                    'field': str(item.get('field', '')).strip(),
                    'display_name': _parse_display_name(item.get('display_name'))
                }
            return {'field': str(item).strip(), 'display_name': None}

        # Normalize all 4 keys to list of {'field', 'display_name'} dicts
        # then deduplicate by label (display_name if set, else field)
        for key in ('Vertical', 'Horizontal', 'Dimensions', 'Measures'):
            val = cleaned.get(key)
            if not val:
                continue
            if isinstance(val, list):
                raw = [_normalize_item(item) for item in val if item]
            else:
                raw = [{'field': f.strip(), 'display_name': None} for f in str(val).split(',') if f.strip()]

            # Deduplicate by label; filter blanks and "None" strings
            seen_labels = set()
            result = []
            for item in raw:
                label = item['display_name'] or item['field']
                if not label or label.lower() == 'none':
                    continue
                if label not in seen_labels:
                    seen_labels.add(label)
                    result.append(item)
            cleaned[key] = result

        return cleaned

    def execute(self, article_id: str) -> Dict[str, Any]:
        """
        Execute the complete workflow for a given article ID

        Full workflow:
        1. Receive article ID via webhook (handled in app.py)
        2. Download article from Joomla
        3. Clean HTML and extract metadata
        4. Sign in to Tableau
        5. Extract auth token and site ID
        6-13. Loop through each chart and process

        Args:
            article_id: The Joomla article ID to process

        Returns:
            Dictionary containing workflow results
        """
        print(f"\n{'='*60}")
        print(f"Starting workflow for article ID: {article_id}")
        print(f"{'='*60}\n")

        # Log workflow start
        self.logger.log_workflow_start(article_id)

        try:
            # Step 2: Download Article from Joomla
            print("[Step 2] Downloading article from Joomla...")
            self.logger.log_step("Download Article", "started", article_id=article_id)
            article_data = self.joomla_service.download_article(article_id)
            print(f"✓ Article downloaded successfully (HTML length: {len(article_data['raw_html'])} chars)")
            self.logger.log_step("Download Article", "completed",
                                article_id=article_id,
                                html_length=len(article_data['raw_html']))

            # Step 3: Clean HTML and extract metadata
            print("\n[Step 3] Cleaning HTML and extracting metadata...")
            cleaned_data = self.html_cleaner.clean_and_extract(
                raw_html=article_data['raw_html'],
                base_url=article_data['base_url']
            )
            # Override with title from Joomla API response and remove brackets at the end
            article_title = article_data['article_title']
            # Remove content in brackets at the end (e.g., "Title (something)" -> "Title")
            article_title = article_title.split('(')[0].strip()
            cleaned_data['article_title'] = article_title
            print(f"✓ Article Title: {cleaned_data['article_title']}")
            print(f"✓ Category: {cleaned_data['category']}")
            print(f"✓ Technology: {cleaned_data['technology']}")
            print(f"✓ Charts found: {len(cleaned_data['charts'])}")

            # Step 4 & 5: Sign in to Tableau and extract credentials
            print("\n[Step 4-5] Authenticating with Tableau...")
            tableau_auth = self.tableau_service.sign_in()
            print(f"✓ Auth Token: {tableau_auth['auth_token'][:20]}...")
            print(f"✓ Site ID: {tableau_auth['site_id']}")

            # Initialize XML cleaner with auth credentials
            xml_cleaner = TableauXMLCleaner(
                base_url=self.tableau_service.server_url,
                site_id=tableau_auth['site_id'],
                auth_token=tableau_auth['auth_token']
            )

            # Step 6-13: Process each chart
            processed_charts = []
            skipped_charts = []

            print(f"\n{'='*60}")
            print("Processing Charts...")
            print(f"{'='*60}\n")

            for idx, chart in enumerate(cleaned_data['charts'], 1):
                # Store original name before case change
                original_chart_name = chart['title']

                # Apply smart title case formatting to chart title
                chart['title'] = self._smart_chart_title(chart['title'])

                print(f"\n[Chart {idx}/{len(cleaned_data['charts'])}] {chart['title']}")
                print("-" * 50)

                try:
                    result = self._process_single_chart(
                        chart,
                        xml_cleaner,
                        cleaned_data['category'],
                        original_chart_name
                    )

                    if result['status'] == 'skipped':
                        skipped_charts.append(result)  # Store full result for relationship updates
                        print(f"⊘ Skipped: {result['reason']}")
                    else:
                        processed_charts.append(result)
                        print(f"✓ Processed successfully")

                except Exception as e:
                    print(f"✗ Error processing chart: {str(e)}")
                    skipped_charts.append({
                        'status': 'skipped',
                        'chart': chart,
                        'chart_name': chart['title'],
                        'original_chart_name': original_chart_name,
                        'reason': f"Error: {str(e)}"
                    })

            # Create Article HTML with embedded charts
            article_intercom_url = None
            print(f"\n{'='*60}")
            print("Creating article with embedded charts...")
            print(f"{'='*60}\n")

            if processed_charts:
                # Extract charts_data for embedded display
                charts_for_article = []
                for chart_result in processed_charts:
                    if chart_result['status'] == 'success':
                        charts_for_article.append({
                            'title': chart_result['chart']['title'],
                            'image_url': chart_result['chart']['image_url'],
                            'shows': chart_result['chart']['shows'],
                            'intercom_url': chart_result.get('chart_intercom_url', '')
                        })

                if charts_for_article:
                    # Create article HTML with embedded charts
                    article_html = self.html_formatter.format_article_with_charts_html(
                        article_title=cleaned_data['article_title'],
                        category=cleaned_data['category'],
                        technology=cleaned_data['technology'],
                        charts_data=charts_for_article
                    )

                    # Publish to ARTICLE collection
                    article_result = self.intercom_service.create_article(
                        title=cleaned_data['article_title'],
                        body_html=article_html,
                        collection_id=self.intercom_service.article_collection_id,
                        author_id=self.intercom_author_id,
                        state='published'
                    )

                    if article_result['status'] == 'success':
                        article_intercom_url = article_result['article_url']
                        print(f"✓ Article published: {article_intercom_url}")

                        # Log to article_library
                        log_result = self.google_sheets_service.log_processed_item(
                            original_name=cleaned_data['article_title'],
                            human_name=cleaned_data['article_title'],
                            intercom_url=article_intercom_url,
                            intercom_id=article_result['article_id'],
                            html=article_html,
                            sheet_name=self.google_sheets_article_library_sheet
                        )
                        print(f"✓ Article logged to Google Sheets")

                        # === STEP: Update Relationships ===
                        # Now that ALL articles are published with URLs, update relationships

                        # 1. Build field → charts mapping
                        field_to_charts_map = self.relationship_service.build_field_to_charts_map(
                            processed_charts=processed_charts,
                            chart_library_sheet=self.google_sheets_chart_library_sheet
                        )

                        # 2. Update data fields with Related Charts
                        self.relationship_service.update_data_fields_with_relationships(
                            field_to_charts_map=field_to_charts_map,
                            processed_charts=processed_charts,
                            data_dict_sheet=self.google_sheets_data_dict_sheet
                        )

                        # 3. Build chart → articles mapping
                        chart_to_articles_map = self.relationship_service.build_chart_to_articles_map(
                            processed_charts=processed_charts,
                            article_title=cleaned_data['article_title'],
                            article_url=article_intercom_url,
                            article_library_sheet=self.google_sheets_article_library_sheet
                        )

                        # 4. Update charts with Related Articles
                        self.relationship_service.update_charts_with_relationships(
                            chart_to_articles_map=chart_to_articles_map,
                            processed_charts=processed_charts,
                            chart_library_sheet=self.google_sheets_chart_library_sheet,
                            skipped_charts=skipped_charts
                        )

                    else:
                        print(f"✗ Failed to publish article: {article_result.get('message', 'Unknown error')}")

            # Prepare final result
            result = {
                'article_id': article_id,
                'article_title': cleaned_data['article_title'],
                'category': cleaned_data['category'],
                'technology': cleaned_data['technology'],
                'slider_image': cleaned_data['slider_image'],
                'total_charts': len(cleaned_data['charts']),
                'processed_charts': len(processed_charts),
                'skipped_charts': len(skipped_charts),
                'charts_data': processed_charts,
                'skipped_data': skipped_charts,
                'article_intercom_url': article_intercom_url
            }

            print(f"\n{'='*60}")
            print(f"Workflow completed!")
            print(f"Total charts: {len(cleaned_data['charts'])}")
            print(f"Processed: {len(processed_charts)}")
            print(f"Skipped: {len(skipped_charts)}")
            if article_intercom_url:
                print(f"Article URL: {article_intercom_url}")
            print(f"{'='*60}\n")

            # Log workflow completion
            self.logger.log_workflow_complete(article_id, result)

            return result

        except Exception as e:
            # Log workflow error
            self.logger.log_workflow_error(article_id, e)
            print(f"\n✗ Workflow failed: {str(e)}")
            raise

    def execute_update(self, article_id: str, preview_mode: bool = False) -> Dict[str, Any]:
        """
        Execute update workflow for existing article

        Workflow:
        1. Download article from Joomla to get title
        2. Lookup in Google Sheets by title to get intercom_id and old HTML
        3. If not found → error
        4. Regenerate content (same as execute())
        5. If preview_mode=True: Return old and new HTML for comparison
        6. If preview_mode=False: Update Intercom article and log to Sheets

        Args:
            article_id: The Joomla article ID to update
            preview_mode: If True, generate new HTML but don't update Intercom (for comparison)

        Returns:
            Dictionary containing workflow results
            If preview_mode=True, includes 'old_html' and 'new_html' for comparison
        """
        mode_text = "PREVIEW" if preview_mode else "UPDATE"
        print(f"\n{'='*60}")
        print(f"Starting {mode_text} workflow for article ID: {article_id}")
        print(f"{'='*60}\n")

        try:
            # Step 1: Download from Joomla to get title
            print("[Step 1] Downloading article from Joomla...")
            article_data = self.joomla_service.download_article(article_id)
            article_title = article_data['article_title'].split('(')[0].strip()
            print(f"✓ Article title: {article_title}")

            # Step 2: Lookup in Google Sheets
            print("\n[Step 2] Looking up article in Google Sheets...")
            lookup_result = self.google_sheets_service.lookup_article_by_title(
                article_title=article_title,
                sheet_name=self.google_sheets_article_library_sheet
            )

            if not lookup_result['exists']:
                raise Exception(
                    f"Article '{article_title}' not found in Google Sheets. "
                    "Cannot update - use 'Publish' to create it first."
                )

            intercom_article_id = lookup_result['intercom_id']
            old_html = lookup_result.get('html', '')

            # Fallback: if HTML not in Google Sheets (old rows), fetch from Intercom directly
            if not old_html and intercom_article_id:
                print(f"  HTML not in Google Sheets, fetching from Intercom...")
                intercom_result = self.intercom_service.get_article(intercom_article_id)
                old_html = intercom_result.get('html', '')

            print(f"✓ Found - Intercom ID: {intercom_article_id}")

            # Steps 3-4: Clean HTML and process charts (reuse existing logic)
            print("\n[Step 3] Cleaning HTML and processing charts...")
            cleaned_data = self.html_cleaner.clean_and_extract(
                raw_html=article_data['raw_html'],
                base_url=article_data['base_url']
            )
            cleaned_data['article_title'] = article_title

            # Authenticate with Tableau
            tableau_auth = self.tableau_service.sign_in()
            xml_cleaner = TableauXMLCleaner(
                base_url=self.tableau_service.server_url,
                site_id=tableau_auth['site_id'],
                auth_token=tableau_auth['auth_token']
            )

            # Process charts (same as execute())
            processed_charts = []
            skipped_charts = []
            all_comparisons = []  # Collect all comparisons in preview mode

            for idx, chart in enumerate(cleaned_data['charts'], 1):
                original_chart_name = chart['title']
                chart['title'] = self._smart_chart_title(chart['title'])

                print(f"\n[Chart {idx}/{len(cleaned_data['charts'])}] {chart['title']}")

                try:
                    result = self._process_single_chart(
                        chart, xml_cleaner, cleaned_data['category'],
                        original_chart_name,
                        check_duplicates=False,  # Don't skip duplicates in update mode
                        preview_mode=preview_mode  # Pass through preview mode
                    )
                    if result['status'] == 'skipped':
                        skipped_charts.append(result)  # Store full result for relationship updates
                        print(f"⊘ Skipped: {result['reason']}")
                    elif result['status'] == 'preview':
                        # In preview mode, collect all comparisons from this chart
                        all_comparisons.extend(result.get('comparisons', []))
                        print(f"✓ Generated {result.get('total_comparisons', 0)} comparison(s)")
                    else:
                        processed_charts.append(result)
                        print(f"✓ Processed successfully")
                except Exception as e:
                    print(f"✗ Error: {str(e)}")
                    skipped_charts.append({'chart': chart, 'reason': str(e)})

            # Generate updated article HTML
            # In preview mode, use actual chart data from comparisons
            if preview_mode:
                # Extract chart data from comparisons (they include image_url and shows)
                charts_for_article = [
                    {
                        'title': comp['article_title'],
                        'image_url': comp.get('image_url', ''),
                        'shows': comp.get('shows', ''),
                        'intercom_url': comp.get('intercom_url', '#')
                    }
                    for comp in all_comparisons if comp.get('article_type') == 'chart'
                ]
            else:
                charts_for_article = [
                    {
                        'title': r['chart']['title'],
                        'image_url': r['chart']['image_url'],
                        'shows': r['chart']['shows'],
                        'intercom_url': r.get('chart_intercom_url', '')
                    }
                    for r in processed_charts if r['status'] == 'success'
                ]

            if charts_for_article or preview_mode:
                article_html = self.html_formatter.format_article_with_charts_html(
                    article_title=cleaned_data['article_title'],
                    category=cleaned_data['category'],
                    technology=cleaned_data['technology'],
                    charts_data=charts_for_article
                )

                # If preview mode, add main article comparison and return all comparisons
                if preview_mode:
                    # Add main article comparison to the list
                    all_comparisons.append({
                        'status': 'preview',
                        'article_type': 'main_article',
                        'article_title': cleaned_data['article_title'],
                        'old_html': old_html,
                        'new_html': article_html,
                        'intercom_article_id': intercom_article_id,
                        'collection_id': None,  # Main articles don't have collection
                        'message': 'Preview generated - awaiting confirmation'
                    })

                    print(f"\n[Preview] Generated {len(all_comparisons)} total comparison(s)")
                    print(f"{'='*60}")
                    print(f"✓ Preview completed - returning all comparisons")
                    print(f"{'='*60}\n")

                    return {
                        'status': 'preview',
                        'article_id': article_id,
                        'comparisons': all_comparisons,
                        'total_comparisons': len(all_comparisons),
                        'message': 'Preview generated - awaiting confirmation'
                    }

                # Step 6: Update Intercom article (only if not preview mode)
                print(f"\n[Update] Updating Intercom article...")
                update_result = self.intercom_service.update_article(
                    article_id=intercom_article_id,
                    title=cleaned_data['article_title'],
                    body_html=article_html,
                    state='published'
                )

                if update_result['status'] != 'success':
                    raise Exception(f"Intercom update failed: {update_result.get('message')}")

                article_intercom_url = update_result['article_url']
                print(f"✓ Updated: {article_intercom_url}")

                # Step 7: Log to Google Sheets (append new row with updated HTML)
                self.google_sheets_service.log_processed_item(
                    original_name=cleaned_data['article_title'],
                    human_name=cleaned_data['article_title'],
                    intercom_url=article_intercom_url,
                    intercom_id=intercom_article_id,
                    html=article_html,
                    sheet_name=self.google_sheets_article_library_sheet
                )

                # === STEP: Update Relationships ===
                # Now that ALL articles are published with URLs, update relationships

                # 1. Build field → charts mapping
                field_to_charts_map = self.relationship_service.build_field_to_charts_map(
                    processed_charts=processed_charts,
                    chart_library_sheet=self.google_sheets_chart_library_sheet
                )

                # 2. Update data fields with Related Charts
                self.relationship_service.update_data_fields_with_relationships(
                    field_to_charts_map=field_to_charts_map,
                    processed_charts=processed_charts,
                    data_dict_sheet=self.google_sheets_data_dict_sheet
                )

                # 3. Build chart → articles mapping
                chart_to_articles_map = self.relationship_service.build_chart_to_articles_map(
                    processed_charts=processed_charts,
                    article_title=cleaned_data['article_title'],
                    article_url=article_intercom_url,
                    article_library_sheet=self.google_sheets_article_library_sheet
                )

                # 4. Update charts with Related Articles
                self.relationship_service.update_charts_with_relationships(
                    chart_to_articles_map=chart_to_articles_map,
                    processed_charts=processed_charts,
                    chart_library_sheet=self.google_sheets_chart_library_sheet,
                    skipped_charts=skipped_charts
                )

                print(f"\n{'='*60}")
                print(f"✓ Update completed successfully")
                print(f"{'='*60}\n")

                return {
                    'status': 'success',
                    'article_id': article_id,
                    'article_title': cleaned_data['article_title'],
                    'intercom_article_id': intercom_article_id,
                    'intercom_url': article_intercom_url,
                    'total_charts': len(cleaned_data['charts']),
                    'processed_charts': len(processed_charts),
                    'skipped_charts': len(skipped_charts),
                    'message': 'Article updated successfully'
                }

            raise Exception("No charts processed, cannot update article")

        except Exception as e:
            print(f"\n✗ Update failed: {str(e)}")
            raise

    def _process_single_chart(self, chart: Dict, xml_cleaner: TableauXMLCleaner, category: str, original_chart_name: str, check_duplicates: bool = True, preview_mode: bool = False) -> Dict[str, Any]:
        """
        Process a single chart through all steps

        Steps:
        1. Check for duplicates in Google Sheets (optional)
        2. Search for workbook in Tableau
        3. Select correct workbook ID
        4. Download and clean XML
        5. Analyze with ChatGPT
        6. Extract field names from analysis
        7. Process data fields
        8. If preview_mode: Return comparison data for chart AND all data fields
        9. Else: Publish chart to Intercom

        Args:
            chart: Chart dictionary with view_id, title, image_url, tabs_name, shows
            xml_cleaner: Initialized TableauXMLCleaner instance
            category: Article category
            original_chart_name: Original chart name before formatting
            check_duplicates: Whether to check for duplicates (False for updates)
            preview_mode: If True, generate HTML but don't publish (for comparison)

        Returns:
            Dictionary with processing results
            If preview_mode=True, includes 'comparisons' list with chart and all data field comparisons
        """
        # Step 1: Duplicate Check (skip if check_duplicates=False)
        existing_chart_data = {}
        if check_duplicates:
            print(f"  [1/6] Checking for duplicates...")

            # In preview mode, we need full data including HTML, so use lookup_article_by_title
            if preview_mode:
                lookup_result = self.google_sheets_service.lookup_article_by_title(
                    article_title=original_chart_name,
                    sheet_name=self.google_sheets_chart_library_sheet
                )
                if lookup_result['exists']:
                    existing_chart_data = lookup_result
                    print(f"  ✓ Found existing (preview mode)")
                else:
                    print(f"  ✓ No existing chart found")
            else:
                # In non-preview mode, just check for duplicates (don't need HTML)
                duplicate_check = self.google_sheets_service.check_duplicate(
                    lookup_name=original_chart_name,
                    sheet_name=self.google_sheets_chart_library_sheet
                )
                if duplicate_check['exists']:
                    return {
                        'status': 'skipped',
                        'reason': 'Duplicate found in Google Sheets',
                        'chart': chart,
                        'chart_name': chart['title'],
                        'original_chart_name': original_chart_name
                    }
                print(f"  ✓ No duplicate found")
        else:
            print(f"  [1/6] Skipping duplicate check (update mode)")
            # In update/preview mode, look up existing chart by ORIGINAL name (not formatted)
            lookup_result = self.google_sheets_service.lookup_article_by_title(
                article_title=original_chart_name,  # Use original name, not formatted title
                sheet_name=self.google_sheets_chart_library_sheet
            )
            if lookup_result['exists']:
                existing_chart_data = lookup_result
                print(f"  ✓ Found existing chart in Google Sheets")

        # Step 2: Search for workbook
        print(f"  [2/6] Searching for workbook: {chart['tabs_name']}")
        workbook_search = self.tableau_service.search_workbooks(chart['tabs_name'])

        if not workbook_search['workbook_ids']:
            return {
                'status': 'skipped',
                'reason': 'No workbook found',
                'chart': chart
            }
        print(f"  ✓ Found {len(workbook_search['workbook_ids'])} workbook(s)")

        # Step 3: Select workbook ID
        print(f"  [3/6] Selecting workbook ID...")
        selection = self.tableau_service.select_workbook_id(
            project_ids=workbook_search['project_ids'],
            workbook_ids=workbook_search['workbook_ids'],
            target_project_id=self.tableau_global_project_id
        )

        if selection['status'] != 'success':
            return {
                'status': 'skipped',
                'reason': 'Global Project ID not found',
                'chart': chart
            }

        workbook_id = selection['workbook_id']
        print(f"  ✓ Selected workbook ID: {workbook_id[:20]}...")

        # Step 4: Download and clean XML
        print(f"  [4/6] Downloading and cleaning XML...")

        xml_result = xml_cleaner.download_and_clean(
            workbook_id=workbook_id,
            target_view_name=chart['tabs_name']
        )

        if xml_result['status'] != 'success':
            return {
                'status': 'skipped',
                'reason': f"XML cleaning failed: {xml_result.get('message', 'Unknown error')}",
                'chart': chart
            }
        print(f"  ✓ XML cleaned successfully")

        # Step 5: Analyze with ChatGPT and extract field names
        print(f"  [5/6] Analyzing with ChatGPT...")
        print(f"\n[DEBUG] Chart XML context sent to GPT:\n{'-'*60}\n{xml_result['analysis_context']}\n{'-'*60}\n")

        analysis_result = self.chatgpt_service.analyze_chart(
            chart_image_url=chart['image_url'],
            chart_context=xml_result['analysis_context']
        )

        if analysis_result['status'] != 'success':
            return {
                'status': 'skipped',
                'reason': f"ChatGPT analysis failed: {analysis_result.get('message', 'Unknown error')}",
                'chart': chart
            }
        print(f"  ✓ Analysis completed")

        # Step 6: Extract field names from response
        print(f"  [6/6] Extracting field names...")
        field_extraction = self.chatgpt_service.extract_field_names(
            analysis_result['analysis']
        )
        print(f"  ✓ Extracted {field_extraction['total_count']} field(s)")

        # Step 7: Process data fields (nested loop)
        processed_fields = []
        skipped_fields = []

        if field_extraction['total_count'] > 0:
            print(f"\n  {'='*45}")
            print(f"  Processing Data Fields for Chart: {chart['title']}")
            print(f"  {'='*45}")

            # Initialize data field analyzer
            field_analyzer = DataFieldAnalyzer(
                base_url=self.tableau_service.server_url,
                site_id=self.tableau_service.site_id,
                auth_token=self.tableau_service.auth_token
            )

            try:
                # Extract field contexts
                field_contexts_result = field_analyzer.extract_field_contexts(
                    workbook_id=workbook_id,
                    target_fields=field_extraction['field_names']
                )

                # Build display name map from GPT analysis
                display_name_map = field_extraction.get('display_name_map', {})

                # Also build a normalized version for lookup (handles name transformations by DataFieldAnalyzer)
                # e.g. "[Field Name]" cleaned to "Field Name" still maps back to its display_name
                normalized_display_name_map = {
                    k.replace('[', '').replace(']', '').lower().replace(' ', '').replace('-', ''): v
                    for k, v in display_name_map.items()
                }

                # Process each field (field names are already cleaned by DataFieldAnalyzer)
                for idx, (field_name, field_context) in enumerate(
                    zip(
                        field_contexts_result['field_names'],
                        field_contexts_result['field_contexts']
                    ),
                    1
                ):
                    print(f"\n    [Field {idx}/{field_contexts_result['total_count']}] {field_name}")

                    # Resolve display_name: try exact key first, then normalized key
                    norm_key = field_name.lower().replace(' ', '').replace('-', '')
                    resolved_display_name = (
                        display_name_map.get(field_name)
                        or normalized_display_name_map.get(norm_key)
                    )

                    try:
                        field_result = self._process_single_data_field(
                            field_name=field_name,
                            field_context=field_context,
                            chart_title=chart['title'],
                            check_duplicates=check_duplicates,  # Pass through from parent
                            preview_mode=preview_mode,  # Pass through preview mode
                            display_name=resolved_display_name  # Use GPT display_name if available
                        )

                        if field_result['status'] == 'skipped':
                            skipped_fields.append({
                                'field_name': field_name,
                                'reason': field_result['reason'],
                                'human_name': field_result.get('human_name', field_name),
                                'intercom_url': field_result.get('intercom_url', '')
                            })
                            print(f"    ⊘ Skipped: {field_result['reason']}")
                        else:
                            processed_fields.append(field_result)
                            print(f"    ✓ Published to Intercom")

                    except Exception as e:
                        print(f"    ✗ Error: {str(e)}")
                        skipped_fields.append({
                            'field_name': field_name,
                            'reason': f"Error: {str(e)}"
                        })

            except Exception as e:
                print(f"  ✗ Failed to extract field contexts: {str(e)}")

        # Step 8: Create detailed Chart HTML with JSON data
        chart_intercom_url = None
        chart_article_id = None
        chart_html = ''  # Initialize to prevent UnboundLocalError if no fields exist
        chart_json = {   # Initialize to prevent UnboundLocalError if no fields exist
            'Vertical': '',
            'Horizontal': '',
            'Dimensions': [],
            'Measures': []
        }
        field_mapping = {}  # Initialize to prevent NameError if no fields are extracted
        # Create chart if there are any fields (processed or skipped)
        if processed_fields or skipped_fields:
            print(f"\n  [7/7] Creating detailed chart article...")

            field_mapping = {}

            # Process newly created fields
            if processed_fields:
                # Collect successfully processed field names
                processed_field_names = [f['field_name'] for f in processed_fields]

                # Batch lookup to get mapping
                lookup_result = self.google_sheets_service.batch_lookup(
                    search_list=processed_field_names,
                    sheet_name=self.google_sheets_data_dict_sheet
                )

                if lookup_result['status'] == 'success':
                    # Build field mapping dict from processed fields
                    for tableau_name, human_name, url in zip(
                        processed_field_names,
                        lookup_result['human_name_list'],
                        lookup_result['url_list']
                    ):
                        field_mapping[tableau_name] = {
                            'human': human_name,
                            'url': url
                        }

            # Add URLs from skipped fields (duplicates) to field_mapping
            for skipped in skipped_fields:
                if skipped.get('intercom_url'):  # Only add if URL exists
                    field_mapping[skipped['field_name']] = {
                        'human': skipped.get('human_name', skipped['field_name']),
                        'url': skipped['intercom_url']
                    }

            # Parse chart JSON from GPT analysis
            try:
                import json
                chart_json = json.loads(analysis_result['analysis'])
            except (json.JSONDecodeError, ValueError):
                # Fallback to empty structure if parsing fails
                chart_json = {
                    'Vertical': '',
                    'Horizontal': '',
                    'Dimensions': [],
                    'Measures': []
                }

            # Clean field names in chart JSON (remove Tableau prefixes)
            chart_json = self._clean_chart_json_fields(chart_json)

            # Query existing relationships for preview mode
            related_articles_names = None
            related_articles_urls = None
            if preview_mode:
                related_articles_result = self.google_sheets_service.get_related_articles_for_chart(
                    chart_title=chart['title'],
                    sheet_name=self.google_sheets_article_library_sheet
                )
                if related_articles_result['status'] == 'success' and related_articles_result.get('related_articles'):
                    related_articles = related_articles_result['related_articles']
                    related_articles_names = [a['title'] for a in related_articles]
                    related_articles_urls = [a['url'] for a in related_articles]

            # Create detailed chart HTML
            chart_html = self.html_formatter.format_chart_with_json_html(
                chart_name=chart['title'],
                image_url=chart['image_url'],
                category=category,
                country='Global',
                shows_text=chart['shows'],
                best_used_for='TBC',
                considerations='TBC',
                accuracy='TBC',  # Kept for backward compatibility but not displayed
                chart_json=chart_json,
                field_mapping=field_mapping,
                related_charts_names=None,  # Blank for now
                related_charts_urls=None,
                related_articles_names=related_articles_names,
                related_articles_urls=related_articles_urls
            )

            # If preview mode, collect all comparisons (data fields + chart) and return
            if preview_mode:
                print(f"  [7/7] Preview mode - collecting all comparisons")

                # Collect all data field comparisons
                comparisons = []
                for field_result in processed_fields:
                    if field_result.get('status') == 'preview':
                        comparisons.append(field_result)

                # Add chart comparison (include image_url and shows for main article preview)
                old_chart_html = existing_chart_data.get('html', '')
                chart_intercom_id = existing_chart_data.get('intercom_id', '')

                # Fallback: if HTML not in Google Sheets, fetch from Intercom directly
                if not old_chart_html and chart_intercom_id:
                    intercom_result = self.intercom_service.get_article(chart_intercom_id)
                    old_chart_html = intercom_result.get('html', '')

                comparisons.append({
                    'status': 'preview',
                    'article_type': 'chart',
                    'article_title': chart['title'],
                    'original_chart_name': original_chart_name,
                    'old_html': old_chart_html,
                    'new_html': chart_html,
                    'intercom_article_id': chart_intercom_id,
                    'collection_id': self.intercom_service.chart_collection_id,
                    'image_url': chart['image_url'],  # Preserve for main article HTML
                    'shows': chart['shows'],  # Preserve for main article HTML
                    'intercom_url': existing_chart_data.get('intercom_url', '#'),  # Use existing URL if available
                    'message': 'Preview generated - awaiting confirmation'
                })

                return {
                    'status': 'preview',
                    'comparisons': comparisons,
                    'chart': chart,
                    'total_comparisons': len(comparisons)
                }

            # Publish to CHART collection
            chart_article_result = self.intercom_service.create_article(
                title=chart['title'],
                body_html=chart_html,
                collection_id=self.intercom_service.chart_collection_id,
                author_id=self.intercom_author_id,
                state='published'
            )

            if chart_article_result['status'] == 'success':
                chart_intercom_url = chart_article_result['article_url']
                chart_article_id = chart_article_result['article_id']
                print(f"  ✓ Chart article published: {chart_intercom_url}")

                # Log to chart_library
                self.google_sheets_service.log_processed_item(
                    original_name=original_chart_name,
                    human_name=chart['title'],
                    intercom_url=chart_intercom_url,
                    intercom_id=chart_article_id,
                    html=chart_html,
                    sheet_name=self.google_sheets_chart_library_sheet
                )
                print(f"  ✓ Chart logged to Google Sheets")
            else:
                print(f"  ✗ Failed to publish chart: {chart_article_result.get('message', 'Unknown error')}")

        # Fallback: in preview mode with 0 fields, still return comparison for the chart
        # (the if processed_fields or skipped_fields block above was skipped entirely)
        if preview_mode:
            old_chart_html = existing_chart_data.get('html', '')
            chart_intercom_id = existing_chart_data.get('intercom_id', '')
            if not old_chart_html and chart_intercom_id:
                intercom_result = self.intercom_service.get_article(chart_intercom_id)
                old_chart_html = intercom_result.get('html', '')
            return {
                'status': 'preview',
                'comparisons': [{
                    'status': 'preview',
                    'article_type': 'chart',
                    'article_title': chart['title'],
                    'original_chart_name': original_chart_name,
                    'old_html': old_chart_html,
                    'new_html': chart_html,
                    'intercom_article_id': chart_intercom_id,
                    'collection_id': self.intercom_service.chart_collection_id,
                    'image_url': chart['image_url'],
                    'shows': chart['shows'],
                    'intercom_url': existing_chart_data.get('intercom_url', '#'),
                    'message': 'Preview generated - awaiting confirmation'
                }],
                'chart': chart,
                'total_comparisons': 1
            }

        return {
            'status': 'success',
            'chart': chart,
            'original_chart_name': original_chart_name,
            'workbook_id': workbook_id,
            'xml_context': xml_result['analysis_context'],
            'gpt_analysis': analysis_result['analysis'],
            'extracted_fields': field_extraction['field_names'],
            'processed_fields': len(processed_fields),
            'skipped_fields': len(skipped_fields),
            'fields_data': processed_fields,
            'fields_skipped': skipped_fields,
            'chart_intercom_url': chart_intercom_url,
            'chart_article_id': chart_article_id,
            'chart_html': chart_html,  # Include HTML for relationship injection
            'chart_json': chart_json,
            'field_mapping': field_mapping,
            'category': category
        }

    def _process_single_data_field(
        self,
        field_name: str,
        field_context: str,
        chart_title: str,
        check_duplicates: bool = True,
        preview_mode: bool = False,
        display_name: str = None
    ) -> Dict[str, Any]:
        """
        Process a single data field through all steps

        Steps:
        1. Check for duplicates in Google Sheets (data_dictionary) (optional)
        2. Analyze field with ChatGPT
        3. Rewrite field name with ChatGPT
        4. Format HTML
        5. If preview_mode: Return comparison data (old HTML vs new HTML)
        6. Else: Publish to Intercom and log to Google Sheets

        Args:
            field_name: The field name
            field_context: Extracted XML context
            chart_title: Parent chart title (for context)
            check_duplicates: Whether to check for duplicates (False for updates)
            preview_mode: If True, generate HTML but don't publish (for comparison)

        Returns:
            Dictionary with processing results
            If preview_mode=True, includes 'old_html', 'new_html', 'article_type': 'data_field'
        """
        # Step 1: Duplicate Check (skip if check_duplicates=False)
        existing_data = {}
        if check_duplicates:
            print(f"      [1/6] Checking duplicates...")

            # In preview mode, we need full data including HTML, so use lookup_article_by_title
            if preview_mode:
                lookup_result = self.google_sheets_service.lookup_article_by_title(
                    article_title=field_name,
                    sheet_name=self.google_sheets_data_dict_sheet
                )
                if lookup_result['exists']:
                    existing_data = lookup_result
                    print(f"      ✓ Found existing (preview mode)")
                else:
                    print(f"      ✓ No existing data field found")
            else:
                # In non-preview mode, just check for duplicates (don't need HTML)
                duplicate_check = self.google_sheets_service.check_duplicate(
                    lookup_name=field_name,
                    sheet_name=self.google_sheets_data_dict_sheet
                )
                if duplicate_check['exists']:
                    return {
                        'status': 'skipped',
                        'reason': 'Duplicate in data_dictionary',
                        'field_name': field_name,
                        'human_name': duplicate_check.get('human_name', field_name),
                        'intercom_url': duplicate_check.get('intercom_url', '')
                    }
                print(f"      ✓ No duplicate found")
        else:
            print(f"      [1/6] Skipping duplicate check (update mode)")
            # In update/preview mode, look up existing article
            lookup_result = self.google_sheets_service.lookup_article_by_title(
                article_title=field_name,
                sheet_name=self.google_sheets_data_dict_sheet
            )
            if lookup_result['exists']:
                existing_data = lookup_result
                print(f"      ✓ Found existing data field in Google Sheets")

        # Step 2: Rewrite field name (or use GPT-provided display_name)
        print(f"      [2/6] Rewriting field name...")
        human_name = field_name  # Fallback to original
        if display_name:
            human_name = display_name
            print(f"      ✓ Using display name from chart analysis: {human_name}")
        else:
            name_rewrite = self.chatgpt_service.rewrite_field_name(
                field_name=field_name,
                field_context=field_context
            )
            if name_rewrite['status'] == 'success' and name_rewrite.get('human_name'):
                human_name = name_rewrite['human_name']

        # Step 3: Analyze field with ChatGPT (human_name now always available)
        print(f"      [3/6] Analyzing field...")
        print(f"\n[DEBUG] Field context sent to GPT for '{field_name}':\n{'-'*60}\n{field_context}\n{'-'*60}\n")
        field_analysis = self.chatgpt_service.analyze_data_field(
            field_name=field_name,
            field_context=field_context,
            human_name=human_name  # Always pass human name regardless of source
        )

        if field_analysis['status'] != 'success':
            return {
                'status': 'skipped',
                'reason': f"Analysis failed: {field_analysis.get('message', 'Unknown error')}"
            }

        # Step 4: Format HTML
        print(f"      [4/6] Formatting HTML...")

        # Query existing relationships for preview mode
        # IMPORTANT: Include BOTH existing relationships AND current chart
        related_charts_names = None
        related_charts_urls = None
        if preview_mode:
            related_charts_list = []

            # Add the CURRENT chart that's using this field
            related_charts_list.append({
                'title': chart_title,
                'url': '#'  # URL not available yet in preview mode
            })

            # Also query existing relationships from Google Sheets
            related_charts_result = self.google_sheets_service.get_related_charts_for_field(
                field_name=field_name,
                sheet_name=self.google_sheets_chart_library_sheet
            )
            if related_charts_result['status'] == 'success' and related_charts_result.get('related_charts'):
                for chart_info in related_charts_result['related_charts']:
                    # Avoid duplicates
                    if chart_info not in related_charts_list:
                        related_charts_list.append(chart_info)

            if related_charts_list:
                related_charts_names = [c['title'] for c in related_charts_list]
                related_charts_urls = [c['url'] for c in related_charts_list]

        html_content = self.html_formatter.format_data_field_html(
            field_name=human_name,
            ai_json=field_analysis['analysis'],
            related_charts_names=related_charts_names,
            related_charts_urls=related_charts_urls
        )

        # If preview mode, return comparison data without publishing
        if preview_mode:
            print(f"      [5/6] Preview mode - returning comparison data")
            old_html = existing_data.get('html', '')
            intercom_id = existing_data.get('intercom_id', '')

            # Fallback: if HTML not in Google Sheets, fetch from Intercom directly
            if not old_html and intercom_id:
                intercom_result = self.intercom_service.get_article(intercom_id)
                old_html = intercom_result.get('html', '')

            return {
                'status': 'preview',
                'article_type': 'data_field',
                'article_title': human_name,
                'field_name': field_name,
                'old_html': old_html,
                'new_html': html_content,
                'intercom_article_id': intercom_id,
                'collection_id': self.intercom_service.data_dict_collection_id,
                'message': 'Preview generated - awaiting confirmation'
            }

        # Step 5: Publish to Intercom (data dictionary collection)
        print(f"      [5/6] Publishing to Intercom...")
        article_title = human_name
        intercom_result = self.intercom_service.create_article(
            title=article_title,
            body_html=html_content,
            collection_id=self.intercom_service.data_dict_collection_id,
            author_id=self.intercom_author_id,
            state='published'
        )

        if intercom_result['status'] != 'success':
            return {
                'status': 'skipped',
                'reason': f"Intercom publish failed: {intercom_result.get('message', 'Unknown error')}"
            }

        # Step 6: Log to Google Sheets
        print(f"      [6/6] Logging to Google Sheets...")
        self.google_sheets_service.log_processed_item(
            original_name=field_name,
            human_name=human_name,
            intercom_url=intercom_result['article_url'],
            intercom_id=intercom_result['article_id'],
            html=html_content,
            sheet_name=self.google_sheets_data_dict_sheet
        )

        return {
            'status': 'success',
            'field_name': field_name,
            'human_name': human_name,
            'intercom_url': intercom_result['article_url'],
            'intercom_article_id': intercom_result['article_id'],
            'ai_analysis': field_analysis['analysis'],  # Needed for regenerating HTML with related charts
            'field_html': html_content  # Include HTML for relationship injection
        }
