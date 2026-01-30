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
        intercom_article_collection_id: str = None
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
            model=openai_model
        )
        self.html_formatter = HTMLFormatter()
        self.intercom_service = IntercomService(
            api_token=intercom_api_token,
            collection_id=intercom_collection_id,
            data_dict_collection_id=intercom_data_dict_collection_id,
            chart_collection_id=intercom_chart_collection_id,
            article_collection_id=intercom_article_collection_id
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
        from .data_field_analyzer import DataFieldAnalyzer
        cleaned = chart_json.copy()

        # Clean comma-separated strings (Vertical, Horizontal)
        if 'Vertical' in cleaned and cleaned['Vertical']:
            fields = [DataFieldAnalyzer.clean_tableau_field_name(f.strip()) for f in str(cleaned['Vertical']).split(',')]
            cleaned['Vertical'] = ', '.join(fields)

        if 'Horizontal' in cleaned and cleaned['Horizontal']:
            fields = [DataFieldAnalyzer.clean_tableau_field_name(f.strip()) for f in str(cleaned['Horizontal']).split(',')]
            cleaned['Horizontal'] = ', '.join(fields)

        # Clean lists (Dimensions, Measures)
        if 'Dimensions' in cleaned and isinstance(cleaned['Dimensions'], list):
            cleaned['Dimensions'] = [DataFieldAnalyzer.clean_tableau_field_name(f) for f in cleaned['Dimensions']]

        if 'Measures' in cleaned and isinstance(cleaned['Measures'], list):
            cleaned['Measures'] = [DataFieldAnalyzer.clean_tableau_field_name(f) for f in cleaned['Measures']]

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
                # Apply smart title case formatting to chart title
                chart['title'] = self._smart_chart_title(chart['title'])

                print(f"\n[Chart {idx}/{len(cleaned_data['charts'])}] {chart['title']}")
                print("-" * 50)

                try:
                    result = self._process_single_chart(chart, xml_cleaner, cleaned_data['category'])

                    if result['status'] == 'skipped':
                        skipped_charts.append({
                            'chart': chart,
                            'reason': result['reason']
                        })
                        print(f"⊘ Skipped: {result['reason']}")
                    else:
                        processed_charts.append(result)
                        print(f"✓ Processed successfully")

                except Exception as e:
                    print(f"✗ Error processing chart: {str(e)}")
                    skipped_charts.append({
                        'chart': chart,
                        'reason': f"Error: {str(e)}"
                    })

            # Final Step: Create Article HTML with embedded charts
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
                            tableau_name=cleaned_data['article_title'],
                            human_name=cleaned_data['article_title'],
                            intercom_url=article_intercom_url,
                            sheet_name=self.google_sheets_article_library_sheet
                        )
                        print(f"✓ Article logged to Google Sheets")

                        # Update chart articles with related article link
                        print(f"\n{'='*60}")
                        print("Updating chart articles with related article link...")
                        print(f"{'='*60}\n")

                        for chart_result in processed_charts:
                            if chart_result['status'] == 'success' and chart_result.get('chart_article_id'):
                                try:
                                    # Regenerate chart HTML with related article URL
                                    updated_chart_html = self.html_formatter.format_chart_with_json_html(
                                        chart_name=chart_result['chart']['title'],
                                        image_url=chart_result['chart']['image_url'],
                                        category=chart_result.get('category', 'General'),
                                        country='Global',
                                        shows_text=chart_result['chart']['shows'],
                                        best_used_for='TBC',
                                        considerations='TBC',
                                        accuracy='TBC',
                                        chart_json=chart_result.get('chart_json', {}),
                                        field_mapping=chart_result.get('field_mapping', {}),
                                        related_article_names=[cleaned_data['article_title']],
                                        related_article_urls=[article_intercom_url]
                                    )

                                    # Update the chart article
                                    update_result = self.intercom_service.update_article(
                                        article_id=chart_result['chart_article_id'],
                                        body_html=updated_chart_html
                                    )

                                    if update_result['status'] == 'success':
                                        print(f"✓ Updated chart: {chart_result['chart']['title']}")
                                    else:
                                        print(f"✗ Failed to update chart {chart_result['chart']['title']}: {update_result.get('message', 'Unknown error')}")

                                except Exception as e:
                                    print(f"✗ Error updating chart {chart_result['chart']['title']}: {str(e)}")

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

    def _process_single_chart(self, chart: Dict, xml_cleaner: TableauXMLCleaner, category: str) -> Dict[str, Any]:
        """
        Process a single chart through all steps

        Steps:
        1. Check for duplicates in Google Sheets
        2. Search for workbook in Tableau
        3. Select correct workbook ID
        4. Download and clean XML
        5. Analyze with ChatGPT
        6. Extract field names from analysis

        Args:
            chart: Chart dictionary with view_id, title, image_url, tabs_name, shows
            xml_cleaner: Initialized TableauXMLCleaner instance

        Returns:
            Dictionary with processing results
        """
        # Step 1: Duplicate Check
        print(f"  [1/6] Checking for duplicates...")
        duplicate_check = self.google_sheets_service.check_duplicate(
            lookup_name=chart['view_id'],
            sheet_name=self.google_sheets_chart_library_sheet
        )

        if duplicate_check['exists']:
            return {
                'status': 'skipped',
                'reason': 'Duplicate found in Google Sheets',
                'chart': chart
            }
        print(f"  ✓ No duplicate found")

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

                # Process each field (field names are already cleaned by DataFieldAnalyzer)
                for idx, (field_name, field_context) in enumerate(
                    zip(
                        field_contexts_result['field_names'],
                        field_contexts_result['field_contexts']
                    ),
                    1
                ):
                    print(f"\n    [Field {idx}/{field_contexts_result['total_count']}] {field_name}")

                    try:
                        field_result = self._process_single_data_field(
                            field_name=field_name,
                            field_context=field_context,
                            chart_title=chart['title']
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

            # Create detailed chart HTML
            # Note: related_article lists are None during initial creation
            # Charts are updated later with the related article links after article creation
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
                related_article_names=None,  # Will be updated after article creation
                related_article_urls=None
            )

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
                log_result = self.google_sheets_service.log_chart(
                    chart_name=chart['title'],
                    intercom_url=chart_intercom_url,
                    sheet_name=self.google_sheets_chart_library_sheet
                )
                print(f"  ✓ Chart logged to Google Sheets")
            else:
                print(f"  ✗ Failed to publish chart: {chart_article_result.get('message', 'Unknown error')}")

        return {
            'status': 'success',
            'chart': chart,
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
            'chart_json': chart_json,
            'field_mapping': field_mapping,
            'category': category
        }

    def _process_single_data_field(
        self,
        field_name: str,
        field_context: str,
        chart_title: str
    ) -> Dict[str, Any]:
        """
        Process a single data field through all steps

        Steps:
        1. Check for duplicates in Google Sheets (data_dictionary)
        2. Analyze field with ChatGPT
        3. Rewrite field name with ChatGPT
        4. Format HTML
        5. Publish to Intercom
        6. Log to Google Sheets

        Args:
            field_name: The field name
            field_context: Extracted XML context
            chart_title: Parent chart title (for context)

        Returns:
            Dictionary with processing results
        """
        # Step 1: Duplicate Check
        print(f"      [1/6] Checking duplicates...")
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

        # Step 2: Analyze field with ChatGPT
        print(f"      [2/6] Analyzing field...")
        field_analysis = self.chatgpt_service.analyze_data_field(
            field_name=field_name,
            field_context=field_context
        )

        if field_analysis['status'] != 'success':
            return {
                'status': 'skipped',
                'reason': f"Analysis failed: {field_analysis.get('message', 'Unknown error')}"
            }

        # Step 3: Rewrite field name
        print(f"      [3/6] Rewriting field name...")
        name_rewrite = self.chatgpt_service.rewrite_field_name(
            field_name=field_name,
            field_context=field_context
        )

        human_name = field_name  # Fallback to original
        if name_rewrite['status'] == 'success':
            human_name = name_rewrite['human_name']

        # Step 4: Format HTML
        print(f"      [4/6] Formatting HTML...")
        html_content = self.html_formatter.format_data_field_html(
            field_name=human_name,
            ai_json=field_analysis['analysis']
        )

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
        log_result = self.google_sheets_service.log_processed_item(
            tableau_name=field_name,
            human_name=human_name,
            intercom_url=intercom_result['article_url'],
            sheet_name=self.google_sheets_data_dict_sheet
        )

        return {
            'status': 'success',
            'field_name': field_name,
            'human_name': human_name,
            'intercom_url': intercom_result['article_url'],
            'intercom_article_id': intercom_result['article_id']
        }
