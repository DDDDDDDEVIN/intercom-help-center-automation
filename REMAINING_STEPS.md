# Remaining Implementation Steps

This document outlines the additional steps needed to complete the full workflow with chart JSON HTML and multiple Intercom collections.

## What's Already Implemented

✅ **Services Updated:**
- `HTMLFormatter` - Added `format_chart_with_json_html()` and `format_article_with_charts_html()`
- `IntercomService` - Added support for 3 separate collections (data_dict, chart, article)
- `GoogleSheetsService` - Added `log_chart()` method for chart_library logging
- `.env.example` - Added 3 collection ID variables

## What Needs to be Added to Workflow

### Step 1: Update WorkflowOrchestrator `__init__`

Add collection ID parameters:

```python
def __init__(
    self,
    # ... existing parameters ...
    intercom_api_token: str,
    intercom_collection_id: str,
    intercom_data_dict_collection_id: str = None,
    intercom_chart_collection_id: str = None,
    intercom_article_collection_id: str = None
):
    # ... existing initialization ...

    self.intercom_service = IntercomService(
        api_token=intercom_api_token,
        collection_id=intercom_collection_id,
        data_dict_collection_id=intercom_data_dict_collection_id,
        chart_collection_id=intercom_chart_collection_id,
        article_collection_id=intercom_article_collection_id
    )
```

### Step 2: Update `_process_single_chart()` - Replace Chart HTML Creation

Find the existing chart HTML creation section (around line 353-391) and replace with:

```python
# Step 8: Create detailed Chart HTML with JSON data
chart_intercom_url = None
if processed_fields:
    print(f"\n  [7/7] Creating detailed chart article...")

    # Collect processed field names
    processed_field_names = [f['field_name'] for f in processed_fields]

    # Batch lookup to get mapping
    lookup_result = self.google_sheets_service.batch_lookup(
        search_list=processed_field_names,
        sheet_name=self.google_sheets_data_dict_sheet
    )

    if lookup_result['status'] == 'success':
        # Build field mapping dict
        field_mapping = {}
        for tableau_name, human_name, url in zip(
            processed_field_names,
            lookup_result['human_name_list'],
            lookup_result['url_list']
        ):
            field_mapping[tableau_name] = {
                'human': human_name,
                'url': url
            }

        # Get chart JSON from GPT analysis (you may need to parse this)
        # For now, using a placeholder structure
        chart_json = {
            'Vertical': 'Y-axis field',
            'Horizontal': 'X-axis field',
            'Dimensions': processed_field_names[:2] if len(processed_field_names) > 1 else [],
            'Measures': processed_field_names[2:] if len(processed_field_names) > 2 else []
        }

        # Create detailed chart HTML
        chart_html = self.html_formatter.format_chart_with_json_html(
            chart_name=chart['title'],
            image_url=chart['image_url'],
            category=cleaned_data['category'],  # Pass from outer scope
            country='Global',  # Or extract from cleaned_data
            shows_text=chart['shows'],
            best_used_for=analysis_result['analysis'][:200],  # Extract from GPT
            considerations='',  # Extract if needed
            accuracy='',  # Extract if needed
            chart_json=chart_json,
            field_mapping=field_mapping
        )

        # Publish to CHART collection
        chart_article_result = self.intercom_service.create_article(
            title=f"Chart: {chart['title']}",
            body_html=chart_html,
            collection_id=self.intercom_service.chart_collection_id,
            state='published'
        )

        if chart_article_result['status'] == 'success':
            chart_intercom_url = chart_article_result['article_url']
            print(f"  ✓ Chart article published: {chart_intercom_url}")

            # Log to chart_library
            log_result = self.google_sheets_service.log_chart(
                chart_name=chart['title'],
                intercom_url=chart_intercom_url,
                sheet_name='chart_library'
            )
            print(f"  ✓ Chart logged to Google Sheets")
        else:
            print(f"  ✗ Failed to publish chart: {chart_article_result.get('message')}")
```

### Step 3: Update Article HTML Creation in `execute()`

Find the article HTML creation section (around line 119-155) and replace with:

```python
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
                'shows': chart_result['chart']['shows']
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
                sheet_name='article_library'
            )
            print(f"✓ Article logged to Google Sheets")
        else:
            print(f"✗ Failed to publish article: {article_result.get('message')}")
```

### Step 4: Update `app.py` to Pass Collection IDs

```python
orchestrator = WorkflowOrchestrator(
    # ... existing parameters ...
    intercom_api_token=os.getenv('INTERCOM_API_TOKEN'),
    intercom_collection_id=os.getenv('INTERCOM_COLLECTION_ID'),
    intercom_data_dict_collection_id=os.getenv('INTERCOM_DATA_DICT_COLLECTION_ID'),
    intercom_chart_collection_id=os.getenv('INTERCOM_CHART_COLLECTION_ID'),
    intercom_article_collection_id=os.getenv('INTERCOM_ARTICLE_COLLECTION_ID')
)
```

### Step 5: Update Data Field Publishing to Use Data Dict Collection

In `_process_single_data_field()` method, update the Intercom publish call (around line 477-483):

```python
# Step 5: Publish to Intercom
print(f"      [5/6] Publishing to Intercom...")
article_title = f"{human_name} - {chart_title}"
intercom_result = self.intercom_service.create_article(
    title=article_title,
    body_html=html_content,
    collection_id=self.intercom_service.data_dict_collection_id,  # Use data dict collection
    state='published'
)
```

## Environment Variables

Add to your `.env`:

```env
# Intercom Collections
INTERCOM_DATA_DICT_COLLECTION_ID=1234567  # Data Dictionary collection
INTERCOM_CHART_COLLECTION_ID=1234568      # Chart Library collection
INTERCOM_ARTICLE_COLLECTION_ID=1234569    # Article Library collection
```

## Chart JSON Parsing

You may need to enhance the chart JSON extraction. The GPT analysis should return structured data. Consider updating the ChatGPT prompt to explicitly request:

```python
gpt_prompt = f"""
Analyze this Tableau chart and provide a structured response in JSON format:
{{
    "vertical_axis": "field name or list of field names",
    "horizontal_axis": "field name or list of field names",
    "dimensions": ["list", "of", "dimension", "fields"],
    "measures": ["list", "of", "measure", "fields"],
    "best_used_for": "description of use cases",
    "considerations": "important notes",
    "accuracy": "accuracy considerations"
}}

Chart Title: {chart['title']}
Description: {chart['shows']}
Context: {xml_result['analysis_context']}
"""
```

Then parse the JSON response to extract the structured data for the chart HTML formatter.

## Google Sheets Structure

Ensure your Google Sheet has these tabs:
- `Sheet1` or custom name (for chart duplicate checking)
- `data_dictionary` (for field logging: tableau_name, human_name, url)
- `chart_library` (for chart logging: chart_name, url)
- `article_library` (for article logging: article_name, url)

## Testing Strategy

1. **Test with 1 chart, 1 field** first
2. **Verify Intercom collections** - check articles appear in correct collections
3. **Verify Google Sheets** - check all 3 sheets are being populated
4. **Test full article** - verify hierarchy: Article → Charts → Fields

## Summary of Changes

**Files Modified:**
- ✅ `src/services/html_formatter.py` - Added 2 new formatters
- ✅ `src/services/intercom_service.py` - Added collection support
- ✅ `src/services/google_sheets_service.py` - Added chart logging
- ✅ `.env.example` - Added collection variables
- ⏳ `src/services/workflow.py` - Needs chart JSON HTML integration
- ⏳ `src/app.py` - Needs collection ID parameters

**Estimated Additional Lines:**
- ~150 lines to workflow.py
- ~10 lines to app.py

**Total Project Size After Completion:**
- Service code: ~2,650 lines
- Complete automation: 25 steps implemented

This should complete your migration from Zapier to a fully functional Python application!
