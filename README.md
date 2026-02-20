# Intercom Help Center Automation

Automates the creation and maintenance of a structured Intercom Help Center from Joomla articles containing Tableau charts. Given a Joomla article ID, the system extracts chart data, analyzes each chart and its underlying data fields using GPT, and publishes three layers of linked articles in Intercom.

---

## What It Does

1. **Downloads** a Joomla article and parses its embedded Tableau chart images
2. **Analyzes** each chart by downloading its Tableau workbook XML and sending the chart image + XML context to GPT
3. **Documents** each data field used in the charts — definition, calculation logic, formula, and filter values
4. **Publishes** three types of Intercom articles:
   - **Data Dictionary** — one article per data field
   - **Chart Library** — one article per chart, with linked data fields
   - **Article Library** — one summary article per Joomla article, with linked charts
5. **Links** everything bidirectionally: data fields link to charts that use them; charts link back to the articles they appear in

---

## Tech Stack

- **Python / Flask** — backend API and webhook server
- **OpenAI GPT** — chart image analysis, field documentation, name rewriting
- **Tableau REST API** — workbook download and XML parsing
- **Intercom API** — article creation and updates
- **Joomla REST API** — source article download
- **Google Apps Script** — simple REST API over Google Sheets for logging and duplicate checking

---

## Project Structure

```
intercom-help-center-automation/
├── src/
│   ├── app.py                       # Flask app, all API routes
│   └── services/
│       ├── workflow.py              # Main orchestrator (publish & update flows)
│       ├── joomla_service.py        # Joomla API — fetch articles
│       ├── html_cleaner.py          # Parse Joomla HTML → chart list + metadata
│       ├── tableau_service.py       # Tableau auth + workbook search
│       ├── tableau_xml_cleaner.py   # Download workbook XML, extract chart structure
│       ├── data_field_analyzer.py   # Extract deep field context from XML
│       ├── chatgpt_service.py       # GPT: chart analysis, field docs, name rewriting
│       ├── html_formatter.py        # Build Intercom HTML from GPT output
│       ├── intercom_service.py      # Intercom: create / update / delete articles
│       ├── google_sheets_service.py # Google Sheets: log rows, check duplicates
│       └── relationship_service.py  # Post-publish: inject bidirectional links
├── WORKFLOW-LOGIC.md                # Detailed step-by-step logic reference
├── TODO.md                          # Known bugs and improvement backlog
├── README.md                        # This file
└── requirements.txt
```

---

## Setup

### Prerequisites

- Python 3.10+
- OpenAI API key with GPT-4 vision access
- Tableau Server or Tableau Cloud with REST API access
- Joomla site with REST API enabled
- Intercom workspace with Help Center enabled and three collections created
- Google Sheet with a Google Apps Script web app deployed

### Installation

```bash
git clone <repo-url>
cd intercom-help-center-automation
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
# Joomla
JOOMLA_BASE_URL=https://yoursite.com
JOOMLA_API_ENDPOINT=/api/index.php/v1/content/articles
JOOMLA_API_TOKEN=your_joomla_token
JOOMLA_CATEGORY_ID=227

# Tableau
TABLEAU_SERVER_URL=https://your-tableau-server.com
TABLEAU_USERNAME=your_username
TABLEAU_PASSWORD=your_password
TABLEAU_SITE_NAME=your_site_name
TABLEAU_GLOBAL_PROJECT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_TEXT_MODEL=gpt-4o
OPENAI_IMAGE_DETAIL=high

# Intercom
INTERCOM_API_TOKEN=your_intercom_token
INTERCOM_COLLECTION_ID=default_collection_id
INTERCOM_DATA_DICT_COLLECTION_ID=data_dictionary_collection_id
INTERCOM_CHART_COLLECTION_ID=chart_library_collection_id
INTERCOM_ARTICLE_COLLECTION_ID=article_library_collection_id
INTERCOM_AUTHOR_ID=your_author_id

# Google Sheets (via GAS web app)
GOOGLE_SHEETS_API_URL=https://script.google.com/macros/s/.../exec
GOOGLE_SHEETS_DATA_DICT_SHEET=data_dictionary
GOOGLE_SHEETS_CHART_LIBRARY_SHEET=chart_library
GOOGLE_SHEETS_ARTICLE_LIBRARY_SHEET=article_library

PORT=5000
```

### Google Sheets Setup

Each of the three sheets (`data_dictionary`, `chart_library`, `article_library`) must have these columns in order:

| A | B | C | D | E |
|---|---|---|---|---|
| original_name | human_name | intercom_url | intercom_id | html |

Deploy a Google Apps Script web app with `doGet` (returns all rows as JSON) and `doPost` (appends rows or deletes by value) handlers. See `WORKFLOW-LOGIC.md` for the expected request/response format.

---

## Running

```bash
cd src
python app.py
```

Server starts at `http://localhost:5000`.

---

## API Reference

### Publish new articles
```
POST /api/articles/create
{ "article_ids": ["123", "456"] }
```
Runs the full publish pipeline for each Joomla article ID. Already-published charts and data fields are skipped (duplicate detection via Google Sheets).

### Preview changes before updating
```
POST /api/articles/update
{ "article_ids": ["123"], "preview": true }
```
Regenerates all content without writing anything. Returns `old_html` / `new_html` pairs for side-by-side review in the UI.

### Apply updates
```
POST /api/articles/update
{ "article_ids": ["123"], "preview": false }
```
Regenerates and overwrites existing articles in Intercom and Google Sheets.

### Confirm selected preview changes
```
POST /api/articles/update/confirm
{ "updates": [{ "article_title": "...", "article_type": "chart|data_field|main_article", "intercom_article_id": "...", "html": "...", "collection_id": "..." }] }
```
Applies a specific subset of changes from a preview session.

### List published Intercom articles
```
GET /api/intercom/articles
```
Returns all articles grouped by collection (Article Library, Chart Library, Data Dictionary).

### Delete articles
```
POST /api/intercom/articles/delete
{ "articles": [{ "id": "123", "title": "...", "collection": "Chart Library" }] }
```
Deletes from both Intercom and Google Sheets.

### List Joomla articles
```
GET /api/joomla/articles
```
Returns published Joomla articles filtered by the configured Global category.

### Web UI
```
GET /articles
```
Browser-based interface for selecting and publishing articles.

---

## Key Design Decisions

**Google Sheets as an HTML cache** — The full HTML of every published article is stored in Google Sheets. This avoids re-calling GPT when adding relationship links to existing articles.

**Relationships injected after publishing** — Intercom URLs only exist after an article is published. All relationship links are added in a second pass once every article in the batch has a URL.

**Duplicate detection by original name** — Charts are registered by their raw Tableau name (before title-case formatting). This survives reformatting between runs.

**GPT field identification** — GPT vision reads the actual chart image and matches visible labels to Tableau XML metadata. This handles cases where fields appear under different display names on different charts.

For detailed step-by-step logic, see [WORKFLOW-LOGIC.md](WORKFLOW-LOGIC.md).
