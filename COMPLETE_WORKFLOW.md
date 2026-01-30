# Complete Workflow Documentation

This document describes the complete end-to-end workflow of the Intercom Help Center Automation.

## Overview

The automation processes Joomla articles with Tableau charts and creates comprehensive data dictionaries in Intercom Help Center. It uses a **nested loop structure**:

- **Outer Loop**: Process each chart in the article
- **Inner Loop**: Process each data field in each chart

## Architecture

```
Article
  ├── Chart 1
  │   ├── Data Field 1.1 → Intercom Article
  │   ├── Data Field 1.2 → Intercom Article
  │   └── Data Field 1.3 → Intercom Article
  ├── Chart 2
  │   ├── Data Field 2.1 → Intercom Article
  │   └── Data Field 2.2 → Intercom Article
  └── Chart 3
      └── ...
```

## Step-by-Step Workflow

### Phase 1: Initial Processing (Steps 1-5)

#### Step 1: Webhook Trigger
- **File**: [src/app.py](src/app.py)
- **Input**: `{"article_id": "123"}`
- **Action**: Flask endpoint receives POST request
- **Output**: Triggers workflow orchestrator

#### Step 2: Download Article
- **File**: [src/services/joomla_service.py](src/services/joomla_service.py)
- **Action**: Fetches HTML from Joomla API
- **Output**: Raw HTML content

#### Step 3: HTML Cleaning
- **File**: [src/services/html_cleaner.py](src/services/html_cleaner.py)
- **Action**:
  - Removes scripts, styles, unnecessary tags
  - Converts images to chart anchors with metadata
  - Extracts article title, category, technology
  - Parses chart information (view_id, title, image_url, tabs_name, shows)
- **Output**: Dictionary with article metadata and **list of chart dictionaries**

#### Step 4: Tableau Authentication
- **File**: [src/services/tableau_service.py](src/services/tableau_service.py)
- **Action**: Signs in to Tableau Server
- **Output**: XML response with credentials

#### Step 5: Extract Credentials
- **File**: [src/services/tableau_service.py](src/services/tableau_service.py)
- **Action**: Parses XML to extract auth_token and site_id
- **Output**: Authentication credentials for subsequent API calls

### Phase 2: Chart Processing Loop (Steps 6-12)

For each chart extracted in Step 3:

#### Step 6: Duplicate Check (Charts)
- **File**: [src/services/google_sheets_service.py](src/services/google_sheets_service.py)
- **Action**: Checks if chart `view_id` exists in Google Sheet
- **Sheet**: As configured (default: Sheet1)
- **Behavior**: Skips chart if duplicate found

#### Step 7: Search Workbook
- **File**: [src/services/tableau_service.py](src/services/tableau_service.py)
- **Action**: Searches Tableau for workbooks matching `tabs_name`
- **Output**: Lists of `project_ids` and `workbook_ids`

#### Step 8: Select Workbook ID
- **File**: [src/services/tableau_service.py](src/services/tableau_service.py)
- **Action**: Matches Global Project ID against project_ids list
- **Config**: `TABLEAU_GLOBAL_PROJECT_ID` (70ceb8ae-d377-4341-a62f-32f4c150f601)
- **Output**: Selected workbook_id

#### Step 9: Download Workbook XML
- **File**: [src/services/tableau_xml_cleaner.py](src/services/tableau_xml_cleaner.py)
- **Action**: Downloads workbook content (ZIP or direct XML)
- **Output**: Raw workbook XML

#### Step 10: Extract Chart Data
- **File**: [src/services/tableau_xml_cleaner.py](src/services/tableau_xml_cleaner.py)
- **Action**:
  - Builds field translation map
  - Finds target worksheet by view_id
  - Extracts Y-axis, X-axis, filters
  - Cleans Tableau syntax
- **Output**: Formatted chart context

#### Step 11: Analyze Chart with ChatGPT
- **File**: [src/services/chatgpt_service.py](src/services/chatgpt_service.py)
- **Action**: Sends chart image + XML context to ChatGPT
- **Input**: Chart image URL, chart context, custom prompt
- **Output**: AI analysis of the chart

#### Step 12: Extract Field Names
- **File**: [src/services/chatgpt_service.py](src/services/chatgpt_service.py)
- **Action**: Parses GPT response to extract data field names
- **Handles**: JSON, lists, comma-separated strings
- **Output**: Deduplicated list of field names

### Phase 3: Data Field Processing Loop (Steps 13-19)

For each field name extracted in Step 12:

#### Step 13: Extract Field Context
- **File**: [src/services/data_field_analyzer.py](src/services/data_field_analyzer.py)
- **Action**:
  - Downloads workbook XML again (with auth)
  - Builds knowledge base (field metadata, formulas, dependencies)
  - Recursively generates context tree for each field
  - Translates field IDs to human names
  - Scrapes filter values (for dimensions) or ranges (for measures)
- **Output**: Parallel lists of `field_names` and `field_contexts`

**Example Field Context:**
```
FIELD: [Customer Count] (Calculation)
   Formula: COUNT([Customer ID])
   └─ FIELD: [Customer ID] (Native string)
      Categories: ID001, ID002, ID003...
```

#### Step 14: Duplicate Check (Data Fields)
- **File**: [src/services/google_sheets_service.py](src/services/google_sheets_service.py)
- **Action**: Checks if field name exists in data_dictionary sheet
- **Sheet**: `data_dictionary`
- **Behavior**: Skips field if duplicate found

#### Step 15: Analyze Field with ChatGPT
- **File**: [src/services/chatgpt_service.py](src/services/chatgpt_service.py)
- **Action**: Sends field context to ChatGPT for detailed analysis
- **Output**: JSON with:
  ```json
  {
    "definition": "What this field represents",
    "calculation_explanation": "How it's calculated",
    "pseudo_formula": "Human-readable formula",
    "considerations": "Important notes"
  }
  ```

#### Step 16: Rewrite Field Name
- **File**: [src/services/chatgpt_service.py](src/services/chatgpt_service.py)
- **Action**: Gets human-readable name from ChatGPT
- **Example**: "cust_cnt_active" → "Active Customer Count"
- **Output**: Human-friendly field name

#### Step 17: Format HTML
- **File**: [src/services/html_formatter.py](src/services/html_formatter.py)
- **Action**: Formats analysis into Intercom-compatible HTML
- **Structure**:
  - **Term**: Field name
  - **Definition**: What it is
  - **Calculation**: How it's computed (with formula in italics)
  - **Considerations**: Important notes
  - **HR separator**

**Example Output:**
```html
<p><strong>Term:</strong> Active Customer Count</p>
<p>&nbsp;</p>
<p><strong>Definition:</strong></p>
<p>The total number of customers with active subscriptions.</p>
<p>&nbsp;</p>
<p><strong>Calculation:</strong></p>
<p>Count of unique customer IDs where status equals 'Active'.</p>
<p>&nbsp;</p>
<p><em>COUNT(IF [Status] = "Active" THEN [Customer ID] END)</em></p>
<p>&nbsp;</p>
<p><strong>Considerations:</strong></p>
<p>May not include trial customers or recently churned accounts.</p>
<p>&nbsp;</p>
<hr>
```

#### Step 18: Publish to Intercom
- **File**: [src/services/intercom_service.py](src/services/intercom_service.py)
- **Action**: Creates article in Intercom Help Center
- **Title Format**: `{human_name} - {chart_title}`
- **State**: `published` (immediately visible)
- **Output**: Intercom article URL and ID

#### Step 19: Log to Google Sheets
- **File**: [src/services/google_sheets_service.py](src/services/google_sheets_service.py)
- **Action**: Logs processed field for future duplicate checking
- **Sheet**: `data_dictionary`
- **Columns**:
  - Col 1: `tableau_name` (original field name)
  - Col 2: `human_name` (rewritten name)
  - Col 3: `intercom_url` (article URL)

## Workflow Orchestration

The workflow is orchestrated in [src/services/workflow.py](src/services/workflow.py):

```python
def execute(article_id):
    # Phase 1: Initial Processing
    download_article()
    clean_html()
    authenticate_tableau()

    # Phase 2: Chart Loop
    for chart in charts:
        check_chart_duplicate()
        search_workbook()
        select_workbook_id()
        download_xml()
        analyze_chart()
        extract_field_names()

        # Phase 3: Field Loop (Nested)
        for field in fields:
            extract_field_context()
            check_field_duplicate()
            analyze_field()
            rewrite_name()
            format_html()
            publish_to_intercom()
            log_to_sheets()
```

## Error Handling

The workflow uses a **skip pattern** for graceful degradation:

- **Charts**: If a chart fails, it's skipped and logged in `skipped_charts`
- **Fields**: If a field fails, it's skipped and logged in `fields_skipped`
- **Continue Processing**: Other charts/fields continue processing

## Key Features

### 1. Nested Loop Structure
- **Problem Solved**: Zapier's poor parallel loop handling
- **Solution**: Native Python loops with proper dictionary structures

### 2. Comprehensive Duplicate Checking
- **Charts**: Checked against main Google Sheet
- **Fields**: Checked against data_dictionary sheet
- **Prevents**: Creating duplicate articles in Intercom

### 3. Deep Field Context Extraction
- **Recursive Analysis**: Follows calculation dependencies
- **Formula Translation**: Converts IDs to human names
- **Value Extraction**: Scrapes actual filter values/ranges

### 4. Intelligent HTML Formatting
- **Intercom-Optimized**: Uses proper spacing with `<p>&nbsp;</p>`
- **Conditional Sections**: Only shows relevant information
- **Professional Layout**: Consistent structure across all articles

### 5. Detailed Logging
- **Console Output**: Shows progress for each step
- **Google Sheets**: Permanent record of processed items
- **Status Tracking**: Clear success/skip/error states

## Performance Characteristics

For a typical article with **10 charts** and **5 fields per chart**:

- **Total API Calls**: ~165
  - Joomla: 1
  - Tableau: ~35 (auth + workbook searches + XML downloads)
  - ChatGPT: ~60 (chart analysis + field analysis + name rewrites)
  - Google Sheets: ~60 (duplicate checks + logging)
  - Intercom: ~50 (article creation)

- **Estimated Runtime**: 15-25 minutes
  - Depends on API latencies and ChatGPT response times

## Configuration Requirements

All services are configured via environment variables:

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
GOOGLE_SHEETS_API_URL (Google Apps Script Web App)
GOOGLE_SHEETS_SHEET_NAME (for charts)

# OpenAI
OPENAI_API_KEY
OPENAI_MODEL (default: gpt-4)

# Intercom
INTERCOM_API_TOKEN
INTERCOM_COLLECTION_ID
```

## Output Structure

```json
{
  "article_id": "123",
  "article_title": "Solar Energy Analysis",
  "category": "Residential",
  "technology": "Solar PV",
  "total_charts": 10,
  "processed_charts": 8,
  "skipped_charts": 2,
  "charts_data": [
    {
      "status": "success",
      "chart": {
        "view_id": "chart_001",
        "title": "Monthly Generation",
        "tabs_name": "Solar_Dashboard"
      },
      "workbook_id": "abc123",
      "extracted_fields": ["Field1", "Field2", "Field3"],
      "processed_fields": 3,
      "skipped_fields": 0,
      "fields_data": [
        {
          "field_name": "Field1",
          "human_name": "Total Generation (kWh)",
          "intercom_url": "https://help.intercom.com/articles/789",
          "intercom_article_id": "789"
        }
      ]
    }
  ]
}
```

## Success Metrics

- **Charts Processed**: Number of charts successfully analyzed
- **Fields Published**: Number of data dictionary entries created
- **Duplicates Avoided**: Charts/fields skipped due to existing records
- **Error Rate**: Charts/fields that failed processing

## Future Enhancements

Potential improvements:

1. **Batch Processing**: Process multiple articles in parallel
2. **Retry Logic**: Automatic retry for transient API failures
3. **Caching**: Cache workbook XMLs to reduce Tableau API calls
4. **Progress Webhooks**: Send real-time updates during processing
5. **Draft Mode**: Create Intercom articles as drafts for review
6. **Rich Media**: Include chart images in Intercom articles
7. **Version Control**: Track changes to field definitions over time

## Troubleshooting

Common issues and solutions:

- **Tableau Auth Fails**: Check username/password and site name
- **Google Sheets Error**: Verify Apps Script URL ends with /exec
- **Intercom 401**: Regenerate API token with correct permissions
- **ChatGPT Timeout**: Increase timeout or reduce max_tokens
- **Duplicate Detection**: Ensure consistent field name formatting
