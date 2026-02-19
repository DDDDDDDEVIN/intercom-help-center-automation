"""
Relationship Service - Manages bidirectional relationships between articles, charts, and data fields

This service handles:
- Building field → charts mappings
- Building chart → articles mappings
- Updating articles with relationship sections (Related Charts, Related Articles)
- Updating both Intercom and Google Sheets with the updated HTML
"""

from typing import Dict, List, Any


class RelationshipService:
    """Manages relationships between articles, charts, and data fields"""

    def __init__(self, google_sheets_service, html_formatter, intercom_service):
        """
        Initialize RelationshipService

        Args:
            google_sheets_service: Service for Google Sheets operations
            html_formatter: Service for HTML formatting
            intercom_service: Service for Intercom operations
        """
        self.google_sheets_service = google_sheets_service
        self.html_formatter = html_formatter
        self.intercom_service = intercom_service

    def build_field_to_charts_map(
        self,
        processed_charts: List[Dict],
        chart_library_sheet: str
    ) -> Dict[str, List[Dict]]:
        """
        Build mapping of data fields to charts that use them

        Args:
            processed_charts: List of successfully processed chart results
            chart_library_sheet: Name of the chart library sheet

        Returns:
            Dictionary: {field_name: [{'title': chart_title, 'url': chart_url}, ...]}
        """
        print(f"\n{'='*60}")
        print("Building field-to-charts relationships...")
        print(f"{'='*60}\n")

        field_to_charts_map = {}

        # Add relationships from current workflow
        for chart_result in processed_charts:
            if chart_result['status'] == 'success':
                chart_title = chart_result['chart']['title']
                chart_url = chart_result.get('chart_intercom_url', '')

                # Skip if no URL (shouldn't happen in correct flow)
                if not chart_url:
                    print(f"  ⚠️  Skipping {chart_title}: No Intercom URL")
                    continue

                # Get all fields used in this chart
                field_mapping = chart_result.get('field_mapping', {})
                for field_name in field_mapping.keys():
                    if field_name not in field_to_charts_map:
                        field_to_charts_map[field_name] = []

                    # Avoid duplicates by title
                    existing_titles = {c['title'] for c in field_to_charts_map[field_name]}
                    if chart_title not in existing_titles:
                        field_to_charts_map[field_name].append({'title': chart_title, 'url': chart_url})

        # Query existing relationships from Google Sheets
        for field_name in field_to_charts_map.keys():
            existing_relations = self.google_sheets_service.get_related_charts_for_field(
                field_name=field_name,
                sheet_name=chart_library_sheet
            )
            if existing_relations['status'] == 'success':
                existing_titles = {c['title'] for c in field_to_charts_map[field_name]}
                for chart_info in existing_relations['related_charts']:
                    if chart_info['title'] not in existing_titles:
                        field_to_charts_map[field_name].append(chart_info)
                        existing_titles.add(chart_info['title'])

        print(f"✓ Built relationships for {len(field_to_charts_map)} fields")
        return field_to_charts_map

    def build_chart_to_articles_map(
        self,
        processed_charts: List[Dict],
        article_title: str,
        article_url: str,
        article_library_sheet: str
    ) -> Dict[str, List[Dict]]:
        """
        Build mapping of charts to articles that use them

        Args:
            processed_charts: List of successfully processed chart results
            article_title: Title of the current article
            article_url: Intercom URL of the current article
            article_library_sheet: Name of the article library sheet

        Returns:
            Dictionary: {chart_title: [{'title': article_title, 'url': article_url}, ...]}
        """
        print(f"\n{'='*60}")
        print("Building chart-to-articles relationships...")
        print(f"{'='*60}\n")

        chart_to_articles_map = {}

        # Add current article to all charts used
        for chart_result in processed_charts:
            if chart_result['status'] == 'success':
                chart_title = chart_result['chart']['title']

                # Initialize list for this chart
                if chart_title not in chart_to_articles_map:
                    chart_to_articles_map[chart_title] = []

                # Add current article
                article_info = {'title': article_title, 'url': article_url}
                if article_info not in chart_to_articles_map[chart_title]:
                    chart_to_articles_map[chart_title].append(article_info)

        # Query existing relationships from Google Sheets
        for chart_title in chart_to_articles_map.keys():
            existing_relations = self.google_sheets_service.get_related_articles_for_chart(
                chart_title=chart_title,
                sheet_name=article_library_sheet
            )
            if existing_relations['status'] == 'success':
                existing_titles = {a['title'] for a in chart_to_articles_map[chart_title]}
                for article_info in existing_relations['related_articles']:
                    if article_info['title'] not in existing_titles:
                        chart_to_articles_map[chart_title].append(article_info)
                        existing_titles.add(article_info['title'])

        print(f"✓ Built relationships for {len(chart_to_articles_map)} charts")
        return chart_to_articles_map

    def update_data_fields_with_relationships(
        self,
        field_to_charts_map: Dict[str, List[Dict]],
        processed_charts: List[Dict],
        data_dict_sheet: str
    ) -> Dict[str, Any]:
        """
        Update data field articles with Related Charts sections

        Args:
            field_to_charts_map: Mapping of fields to charts
            processed_charts: List of processed chart results
            data_dict_sheet: Name of the data dictionary sheet

        Returns:
            Dictionary with update statistics
        """
        print(f"\n{'='*60}")
        print("Updating data field articles with Related Charts...")
        print(f"{'='*60}\n")

        updated_count = 0
        failed_count = 0
        fields_to_update = {}

        # Collect all fields that need updating
        for chart_result in processed_charts:
            if chart_result['status'] == 'success':
                # Check newly created fields
                for field_result in chart_result.get('fields_data', []):
                    if field_result['status'] == 'success':
                        field_name = field_result['field_name']

                        # Skip if not in mapping (shouldn't happen)
                        if field_name not in field_to_charts_map:
                            continue

                        # Use HTML from field result (just generated)
                        field_html = field_result.get('field_html', '')

                        if field_html:
                            fields_to_update[field_name] = {
                                'human_name': field_result['human_name'],
                                'article_id': field_result['intercom_article_id'],
                                'old_html': field_html,
                                'intercom_url': field_result.get('intercom_url', '')
                            }
                        else:
                            print(f"  ⊘ {field_name}: No HTML in field result")

                # Check skipped fields (existing data fields that were duplicates)
                for skipped_field in chart_result.get('fields_skipped', []):
                    field_name = skipped_field.get('field_name')

                    if field_name and field_name in field_to_charts_map:
                        # This is an EXISTING field that needs updating - must look up HTML
                        lookup_result = self.google_sheets_service.lookup_article_by_title(
                            article_title=field_name,
                            sheet_name=data_dict_sheet
                        )

                        if lookup_result['exists']:
                            fields_to_update[field_name] = {
                                'human_name': skipped_field.get('human_name', field_name),
                                'article_id': lookup_result['intercom_id'],
                                'old_html': lookup_result.get('html', ''),
                                'intercom_url': lookup_result.get('intercom_url', '')
                            }
                        else:
                            print(f"  ⊘ {field_name}: Skipped field not found in Google Sheets")

        # Update all fields by injecting Related Charts section
        for field_name, field_info in fields_to_update.items():
            related_charts = field_to_charts_map.get(field_name, [])

            if related_charts and field_info['article_id'] and field_info['old_html']:
                # Inject Related Charts section into existing HTML
                updated_html = self.html_formatter.inject_related_charts_to_field_html(
                    existing_html=field_info['old_html'],
                    related_charts_names=[c['title'] for c in related_charts],
                    related_charts_urls=[c['url'] for c in related_charts]
                )

                # Update in Intercom
                intercom_result = self.intercom_service.update_article(
                    article_id=field_info['article_id'],
                    body_html=updated_html
                )

                if intercom_result['status'] == 'success':
                    # Update Google Sheets with new HTML
                    self.google_sheets_service.log_processed_item(
                        original_name=field_name,
                        human_name=field_info['human_name'],
                        intercom_url=field_info['intercom_url'],
                        intercom_id=field_info['article_id'],
                        html=updated_html,
                        sheet_name=data_dict_sheet
                    )

                    updated_count += 1
                    print(f"  ✓ {field_info['human_name']}: {len(related_charts)} chart(s)")
                else:
                    failed_count += 1
                    print(f"  ✗ {field_info['human_name']}: Update failed")

        print(f"\n✓ Updated {updated_count} data fields ({failed_count} failed)")

        return {
            'updated': updated_count,
            'failed': failed_count,
            'total': len(fields_to_update)
        }

    def update_charts_with_relationships(
        self,
        chart_to_articles_map: Dict[str, List[Dict]],
        processed_charts: List[Dict],
        chart_library_sheet: str,
        skipped_charts: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update chart articles with Related Articles sections

        Args:
            chart_to_articles_map: Mapping of charts to articles
            processed_charts: List of processed chart results
            chart_library_sheet: Name of the chart library sheet
            skipped_charts: List of skipped chart results (optional)

        Returns:
            Dictionary with update statistics
        """
        print(f"\n{'='*60}")
        print("Updating chart articles with Related Articles...")
        print(f"{'='*60}\n")

        updated_count = 0
        failed_count = 0
        skipped_count = 0

        # Combine processed and skipped charts
        all_charts = list(processed_charts)
        if skipped_charts:
            all_charts.extend(skipped_charts)

        for chart_result in all_charts:
            # Handle both successful and skipped charts
            is_success = chart_result.get('status') == 'success'
            is_skipped = chart_result.get('status') == 'skipped'

            if not (is_success or is_skipped):
                continue

            # Get chart information
            if is_success:
                chart_title = chart_result['chart']['title']
                original_chart_name = chart_result.get('original_chart_name', chart_title)
                chart_url = chart_result.get('chart_intercom_url', '')
                chart_id = chart_result.get('chart_article_id', '')
                chart_html = chart_result.get('chart_html', '')  # From just-generated HTML
            else:  # is_skipped
                # Support both 'chart_name' key and nested 'chart'.'title'
                chart_title = (
                    chart_result.get('chart_name')
                    or chart_result.get('chart', {}).get('title', '')
                )
                original_chart_name = chart_result.get('original_chart_name', chart_title)
                chart_url = chart_result.get('intercom_url', '')

                if not chart_title:
                    skipped_count += 1
                    continue

                # For skipped charts, need to look up article_id and HTML from Google Sheets
                lookup_result = self.google_sheets_service.lookup_article_by_title(
                    article_title=chart_title,
                    sheet_name=chart_library_sheet
                )

                if not lookup_result['exists']:
                    print(f"  ⊘ {chart_title}: Skipped chart not found in Google Sheets")
                    skipped_count += 1
                    continue

                chart_id = lookup_result['intercom_id']
                chart_html = lookup_result.get('html', '')

            if not chart_html or not chart_id:
                print(f"  ⊘ {chart_title}: Missing HTML or article ID")
                skipped_count += 1
                continue

            # Get related articles for this chart
            related_articles = chart_to_articles_map.get(chart_title, [])

            if not related_articles:
                print(f"  ⊘ {chart_title}: No related articles to add")
                skipped_count += 1
                continue

            try:
                # Inject Related Articles section into chart HTML
                updated_html = self.html_formatter.inject_related_articles_to_chart_html(
                    existing_html=chart_html,
                    related_articles_names=[a['title'] for a in related_articles],
                    related_articles_urls=[a['url'] for a in related_articles]
                )

                # Update in Intercom
                intercom_result = self.intercom_service.update_article(
                    article_id=chart_id,
                    body_html=updated_html
                )

                if intercom_result['status'] == 'success':
                    # Update Google Sheets with new HTML
                    self.google_sheets_service.log_processed_item(
                        original_name=original_chart_name,
                        human_name=chart_title,
                        intercom_url=chart_url,
                        intercom_id=chart_id,
                        html=updated_html,
                        sheet_name=chart_library_sheet
                    )

                    updated_count += 1
                    status_msg = "(skipped/existing)" if is_skipped else ""
                    print(f"  ✓ {chart_title}: {len(related_articles)} article(s) {status_msg}")
                else:
                    failed_count += 1
                    print(f"  ✗ {chart_title}: Update failed")

            except Exception as e:
                failed_count += 1
                print(f"  ✗ {chart_title}: Error - {str(e)}")

        print(f"\n✓ Updated {updated_count} charts ({failed_count} failed, {skipped_count} skipped)")

        return {
            'updated': updated_count,
            'failed': failed_count,
            'skipped': skipped_count,
            'total': len(all_charts)
        }
