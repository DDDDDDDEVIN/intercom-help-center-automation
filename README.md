# Intercom Help Center Automation

Automated workflow to process Joomla articles, analyze Tableau charts with ChatGPT, and publish to Intercom.

## Overview

This automation replaces a Zapier workflow that had limitations with parallel loops and list separation. The workflow:

1. **Receives webhook** - Triggered by HTTP POST with article ID
2. **Downloads article** - Fetches HTML content from Joomla API
3. **Cleans HTML** - Extracts article metadata (title, country, technology, category) and chart information
4. **Authenticates with Tableau** - Signs in to get auth token and site ID
5. **Processes charts** - Loops through each chart to:
   - Check for duplicates
   - Find workbook ID
   - Download workbook XML
   - Extract data fields
   - Send to ChatGPT for analysis
   - Format as HTML and publish to Intercom
   - Extract and analyze formulas

## Setup

### Prerequisites

- Python 3.9 or higher
- pip (Python package manager)
- Access to:
  - Joomla API
  - Tableau Server
  - Intercom API
  - OpenAI API (ChatGPT)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd intercom-help-center-automation
```

2. Create a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

### Environment Variables

Edit `.env` with your configuration:

```env
# Server Configuration
PORT=5000

# Joomla API Configuration
JOOMLA_BASE_URL=https://rocket.sunwiz.com.au
JOOMLA_API_ENDPOINT=/api/articles
JOOMLA_API_TOKEN=your_joomla_token

# Tableau Configuration
TABLEAU_SERVER_URL=https://your-tableau-server.com
TABLEAU_USERNAME=your_username
TABLEAU_PASSWORD=your_password
TABLEAU_SITE_NAME=your_site_name
TABLEAU_GLOBAL_PROJECT_ID=70ceb8ae-d377-4341-a62f-32f4c150f601

# Google Sheets Configuration (for duplicate checking)
GOOGLE_SHEETS_API_URL=https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec
GOOGLE_SHEETS_SHEET_NAME=Sheet1

# OpenAI/ChatGPT Configuration
OPENAI_API_KEY=your_openai_key
OPENAI_MODEL=gpt-4

# Intercom Configuration
INTERCOM_API_TOKEN=your_intercom_token
INTERCOM_COLLECTION_ID=your_collection_id
```

## Usage

### Running the Server

```bash
python src/app.py
```

The server will start on `http://localhost:5000` (or the port specified in `.env`).

### Triggering the Workflow

Send a POST request to the webhook endpoint:

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"article_id": "123"}'
```

### Health Check

```bash
curl http://localhost:5000/health
```

## Project Structure

```
intercom-help-center-automation/
├── src/
│   ├── app.py                           # Flask app with webhook endpoint
│   └── services/
│       ├── __init__.py
│       ├── workflow.py                  # Workflow orchestrator (nested loops)
│       ├── joomla_service.py            # Joomla API integration
│       ├── html_cleaner.py              # HTML parsing & extraction
│       ├── tableau_service.py           # Tableau auth & workbook search
│       ├── google_sheets_service.py     # Duplicate checking & logging
│       ├── tableau_xml_cleaner.py       # Chart XML processing
│       ├── data_field_analyzer.py       # Field context extraction
│       ├── chatgpt_service.py           # AI analysis (charts & fields)
│       ├── html_formatter.py            # HTML formatting for Intercom
│       └── intercom_service.py          # Intercom Help Center publishing
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
└── IMPLEMENTATION_SUMMARY.md            # Detailed technical docs
```

## Current Implementation Status

### ✅ Fully Completed - All Steps Implemented!

**Initial Processing:**
- ✅ Step 1: Webhook endpoint to receive article ID
- ✅ Step 2: Download article from Joomla API
- ✅ Step 3: HTML cleaning and metadata extraction
- ✅ Step 4: Tableau authentication
- ✅ Step 5: Extract auth token and site ID

**Chart Processing Loop (for each chart):**
- ✅ Step 6: Check for duplicate charts (Google Sheets)
- ✅ Step 7: Search workbook by Tableau name
- ✅ Step 8: Select workbook ID by Global Project ID
- ✅ Step 9: Download workbook XML
- ✅ Step 10: Extract and clean chart data fields from XML
- ✅ Step 11: Send chart to ChatGPT for analysis
- ✅ Step 12: Extract field names from GPT response

**Data Field Processing Loop (for each field in each chart):**
- ✅ Step 13: Extract detailed field context from XML (formulas, dependencies, values)
- ✅ Step 14: Check for duplicate fields in Google Sheets (data_dictionary)
- ✅ Step 15: Analyze field with ChatGPT
- ✅ Step 16: Rewrite field name to human-readable format
- ✅ Step 17: Format analysis as HTML
- ✅ Step 18: Publish field to Intercom Help Center
- ✅ Step 19: Log processed field to Google Sheets

**Chart HTML Creation (after processing all fields in chart):**
- ✅ Step 20: Batch lookup field URLs from Google Sheets
- ✅ Step 21: Create chart HTML with linked fields
- ✅ Step 22: Publish chart article to Intercom

**Article HTML Creation (after processing all charts):**
- ✅ Step 23: Aggregate all chart URLs
- ✅ Step 24: Create article HTML with chart links
- ✅ Step 25: Publish article to Intercom

## API Endpoints

### POST /webhook
Trigger the automation workflow

**Request:**
```json
{
  "article_id": "123"
}
```

**Response:**
```json
{
  "success": true,
  "article_id": "123",
  "result": {
    "article_title": "Analysis Report",
    "category": "Residential",
    "technology": "Solar PV",
    "total_charts": 10,
    "processed_charts": 8,
    "skipped_charts": 2,
    "article_intercom_url": "https://help.intercom.com/articles/main-article-123",
    "charts_data": [
      {
        "status": "success",
        "chart": {...},
        "workbook_id": "abc123",
        "extracted_fields": ["Field1", "Field2"],
        "processed_fields": 2,
        "skipped_fields": 0,
        "chart_intercom_url": "https://help.intercom.com/articles/chart-456",
        "fields_data": [
          {
            "field_name": "Field1",
            "human_name": "Customer Count",
            "intercom_url": "https://help.intercom.com/articles/field-789",
            "intercom_article_id": "789"
          }
        ]
      }
    ],
    "skipped_data": [...]
  }
}
```

### GET /health
Health check endpoint

**Response:**
```json
{
  "status": "healthy",
  "service": "intercom-help-center-automation"
}
```

## Development

### Running in Development Mode

The Flask app runs with debug mode enabled by default:

```bash
python src/app.py
```

### Adding New Steps

To add new workflow steps, update `src/services/workflow.py` and create new service modules as needed.

## License

MIT
