# Implementation Summary

This document provides a detailed summary of the migrated Zapier workflow to Python.

## Architecture Overview

The automation is built as a Flask web application with modular services for each step of the workflow.

## Workflow Steps

### Step 1: Webhook Trigger
- **File**: [src/app.py](src/app.py)
- **Description**: Flask endpoint receives HTTP POST with `article_id`
- **Zapier equivalent**: Catch Hook trigger

### Step 2: Download Article
- **File**: [src/services/joomla_service.py](src/services/joomla_service.py)
- **Description**: Fetches article HTML from Joomla API
- **Key method**: `JoomlaService.download_article(article_id)`

### Step 3: HTML Cleaning
- **File**: [src/services/html_cleaner.py](src/services/html_cleaner.py)
- **Description**: Extracts metadata and chart information from raw HTML
- **Output**: Returns dictionary with:
  - `article_title`
  - `category`
  - `technology`
  - `slider_image`
  - `charts` (list of chart dictionaries)
- **Key improvement**: Returns list of chart dictionaries instead of separate lists for easier looping

### Step 4-5: Tableau Authentication
- **File**: [src/services/tableau_service.py](src/services/tableau_service.py)
- **Description**: Signs in to Tableau and extracts auth token and site ID
- **Key methods**:
  - `TableauService.sign_in()` - Authenticates with Tableau
  - `TableauService.extract_credentials(xml_string)` - Parses XML response

### Step 6-13: Chart Processing Loop

For each chart extracted in Step 3, the workflow executes:

#### Step 6: Duplicate Check
- **File**: [src/services/google_sheets_service.py](src/services/google_sheets_service.py)
- **Description**: Checks if chart already exists in Google Sheets using `view_id`
- **Key method**: `GoogleSheetsService.check_duplicate(lookup_name, sheet_name)`
- **Behavior**: Skips chart if duplicate found

#### Step 7: Workbook Search
- **File**: [src/services/tableau_service.py](src/services/tableau_service.py)
- **Description**: Searches for workbook using `tabs_name` from chart
- **Key method**: `TableauService.search_workbooks(workbook_name)`
- **Returns**: Lists of `project_ids` and `workbook_ids`

#### Step 8: Workbook ID Selection
- **File**: [src/services/tableau_service.py](src/services/tableau_service.py)
- **Description**: Selects correct workbook ID based on Global Project ID
- **Key method**: `TableauService.select_workbook_id(project_ids, workbook_ids, target_project_id)`
- **Behavior**: Matches project ID with target and returns corresponding workbook ID

#### Step 9-11: XML Processing
- **File**: [src/services/tableau_xml_cleaner.py](src/services/tableau_xml_cleaner.py)
- **Description**: Downloads workbook XML, extracts and cleans chart data
- **Key method**: `TableauXMLCleaner.download_and_clean(workbook_id, target_view_name)`
- **Features**:
  - Handles ZIP or direct XML responses
  - Builds field translation map
  - Extracts Y-axis, X-axis, filters
  - Cleans Tableau-specific syntax
  - Breaks down complex expressions (e.g., "INDEX * Capacity" → "INDEX, Capacity")

#### Step 12: ChatGPT Analysis
- **File**: [src/services/chatgpt_service.py](src/services/chatgpt_service.py)
- **Description**: Sends chart image and XML context to ChatGPT for analysis
- **Key method**: `ChatGPTService.analyze_chart(chart_image_url, chart_context, prompt)`
- **Note**: Prompt needs to be customized by user

#### Step 13: Field Name Extraction
- **File**: [src/services/chatgpt_service.py](src/services/chatgpt_service.py)
- **Description**: Extracts and cleans field names from GPT response
- **Key method**: `ChatGPTService.extract_field_names(gpt_response)`
- **Features**:
  - Handles JSON, list, or comma-separated string formats
  - Deduplicates field names
  - Normalizes names (removes spaces, hyphens)

## Workflow Orchestration

- **File**: [src/services/workflow.py](src/services/workflow.py)
- **Description**: Coordinates execution of all steps
- **Key methods**:
  - `WorkflowOrchestrator.execute(article_id)` - Main workflow entry point
  - `WorkflowOrchestrator._process_single_chart(chart, xml_cleaner)` - Processes individual chart

## Key Improvements Over Zapier

1. **Better Loop Handling**: Uses Python dictionaries instead of parallel lists
2. **Error Handling**: Comprehensive try-catch blocks with detailed error messages
3. **Safety Checks**: Multiple validation points to prevent data loss
4. **Modular Design**: Each service is self-contained and testable
5. **Detailed Logging**: Console output shows progress at each step
6. **Skipped vs Processed**: Clear distinction between successful processing and skipped items

## Configuration

All configuration is managed through environment variables in `.env`:

```env
# Joomla
JOOMLA_BASE_URL
JOOMLA_API_ENDPOINT
JOOMLA_API_TOKEN

# Tableau
TABLEAU_SERVER_URL
TABLEAU_USERNAME
TABLEAU_PASSWORD
TABLEAU_SITE_NAME
TABLEAU_GLOBAL_PROJECT_ID

# Google Sheets
GOOGLE_SHEETS_API_URL
GOOGLE_SHEETS_SHEET_NAME

# OpenAI
OPENAI_API_KEY
OPENAI_MODEL

# Intercom
INTERCOM_API_TOKEN
INTERCOM_COLLECTION_ID
```

## Response Format

The workflow returns a comprehensive result dictionary:

```python
{
    'article_id': str,
    'article_title': str,
    'category': str,
    'technology': str,
    'slider_image': dict,
    'total_charts': int,
    'processed_charts': int,
    'skipped_charts': int,
    'charts_data': [
        {
            'status': 'success',
            'chart': {...},
            'workbook_id': str,
            'xml_context': str,
            'gpt_analysis': str,
            'extracted_fields': [str, ...]
        },
        ...
    ],
    'skipped_data': [
        {
            'chart': {...},
            'reason': str
        },
        ...
    ]
}
```

## Next Steps

To complete the full workflow, the following still need implementation:

1. **HTML Formatting**: Convert GPT analysis to HTML format for Intercom
2. **Intercom Publishing**: Publish formatted content to Intercom Help Center
3. **Formula Processing**: For each extracted field, extract formulas from XML and analyze with GPT
4. **Google Sheets Logging**: Add processed charts to Google Sheets to prevent future duplicates

## Testing

To test the current implementation:

1. Set up `.env` with valid credentials
2. Install dependencies: `pip install -r requirements.txt`
3. Run the server: `python src/app.py`
4. Trigger workflow:
```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"article_id": "123"}'
```

## Notes

- The ChatGPT prompt in Step 12 is a placeholder - you need to provide your actual analysis prompt
- Google Sheets API URL must be from a deployed Google Apps Script Web App
- Tableau Global Project ID is hardcoded as `70ceb8ae-d377-4341-a62f-32f4c150f601`
