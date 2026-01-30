# Quick Start Guide

Get your Intercom Help Center Automation up and running in 5 minutes.

## Prerequisites

- Python 3.9+
- Access to:
  - Joomla API
  - Tableau Server
  - Google Sheets (with Apps Script Web App)
  - OpenAI API
  - Intercom Help Center

## Installation

### 1. Clone & Setup

```bash
cd intercom-help-center-automation
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
nano .env  # or use your preferred editor
```

Fill in all the required credentials:

```env
# Joomla
JOOMLA_BASE_URL=https://rocket.sunwiz.com.au
JOOMLA_API_ENDPOINT=/your-endpoint
JOOMLA_API_TOKEN=your_token_here

# Tableau
TABLEAU_SERVER_URL=https://your-tableau-server.com
TABLEAU_USERNAME=your_username
TABLEAU_PASSWORD=your_password
TABLEAU_SITE_NAME=your_site
TABLEAU_GLOBAL_PROJECT_ID=70ceb8ae-d377-4341-a62f-32f4c150f601

# Google Sheets
GOOGLE_SHEETS_API_URL=https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec
GOOGLE_SHEETS_SHEET_NAME=Sheet1

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4

# Intercom
INTERCOM_API_TOKEN=your_token_here
INTERCOM_COLLECTION_ID=your_collection_id
```

### 3. Set Up Google Apps Script

Your Google Sheets needs a Web App that can:
- Read rows from specified sheets (GET requests)
- Write rows to specified sheets (POST requests)

**Apps Script Example:**
```javascript
function doGet(e) {
  const sheetName = e.parameter.sheet_name || 'Sheet1';
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);

  if (!sheet) {
    return ContentService.createTextOutput(JSON.stringify({error: 'Sheet not found'}))
      .setMimeType(ContentService.MimeType.JSON);
  }

  const data = sheet.getDataRange().getValues();
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  const data = JSON.parse(e.postData.contents);
  const sheetName = data.sheet_name || 'Sheet1';
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(sheetName);

  if (!sheet) {
    return ContentService.createTextOutput(JSON.stringify({error: 'Sheet not found'}))
      .setMimeType(ContentService.MimeType.JSON);
  }

  sheet.appendRow([data.col1 || '', data.col2 || '', data.col3 || '']);

  return ContentService.createTextOutput(JSON.stringify({status: 'success'}))
    .setMimeType(ContentService.MimeType.JSON);
}
```

Deploy as Web App with:
- Execute as: Me
- Who has access: Anyone

## Running the Server

```bash
python src/app.py
```

Server starts on `http://localhost:5000`

## Testing

### Health Check

```bash
curl http://localhost:5000/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "intercom-help-center-automation"
}
```

### Process an Article

```bash
curl -X POST http://localhost:5000/webhook \
  -H "Content-Type: application/json" \
  -d '{"article_id": "YOUR_ARTICLE_ID"}'
```

Expected response:
```json
{
  "success": true,
  "article_id": "YOUR_ARTICLE_ID",
  "result": {
    "article_title": "...",
    "total_charts": 10,
    "processed_charts": 8,
    ...
  }
}
```

## Monitoring Progress

The application outputs detailed logs to the console:

```
============================================================
Starting workflow for article ID: 123
============================================================

[Step 2] Downloading article from Joomla...
✓ Article downloaded successfully (HTML length: 45231 chars)

[Step 3] Cleaning HTML and extracting metadata...
✓ Article Title: Solar Energy Analysis
✓ Category: Residential
✓ Technology: Solar PV
✓ Charts found: 10

[Step 4-5] Authenticating with Tableau...
✓ Auth Token: abc123...
✓ Site ID: xyz789

============================================================
Processing Charts...
============================================================

[Chart 1/10] Monthly Generation
--------------------------------------------------
  [1/6] Checking for duplicates...
  ✓ No duplicate found
  [2/6] Searching for workbook: Solar_Dashboard
  ✓ Found 1 workbook(s)
  [3/6] Selecting workbook ID...
  ✓ Selected workbook ID: workbook123...
  [4/6] Downloading and cleaning XML...
  ✓ XML cleaned successfully
  [5/6] Analyzing with ChatGPT...
  ✓ Analysis completed
  [6/6] Extracting field names...
  ✓ Extracted 3 field(s)

  =============================================
  Processing Data Fields for Chart: Monthly Generation
  =============================================

    [Field 1/3] total_generation
      [1/6] Checking duplicates...
      [2/6] Analyzing field...
      [3/6] Rewriting field name...
      [4/6] Formatting HTML...
      [5/6] Publishing to Intercom...
      [6/6] Logging to Google Sheets...
    ✓ Published to Intercom

...
```

## Troubleshooting

### "Authentication failed" (Tableau)
- Verify username/password
- Check site name (may be empty string for default site)
- Ensure user has API access permissions

### "Google Sheet Script Error"
- Verify Apps Script URL ends with `/exec`
- Check sheet names match (case-sensitive)
- Ensure Apps Script is deployed and accessible

### "Intercom API Error"
- Regenerate API token
- Verify token has write permissions for articles
- Check collection ID exists

### "ChatGPT timeout"
- Increase timeout in code (default 60s)
- Check OpenAI API key is valid
- Verify you have available API credits

### "No charts found"
- Check HTML structure matches expected format
- Verify images have `view`, `title`, and `tabs` attributes
- Review HTML cleaning output in logs

## Performance Tips

1. **Start Small**: Test with a single-chart article first
2. **Monitor Costs**: ChatGPT API calls can add up with many fields
3. **Use Haiku for Testing**: Set `OPENAI_MODEL=gpt-3.5-turbo` for cheaper testing
4. **Background Processing**: For production, consider using task queues (Celery, RQ)

## Next Steps

- Read [COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md) for detailed workflow explanation
- Review [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details
- Customize ChatGPT prompts in `src/services/workflow.py`
- Add custom error handling or notifications
- Deploy to production (Heroku, AWS, etc.)

## Support

For issues or questions:
1. Check the logs for detailed error messages
2. Review the documentation files
3. Verify all environment variables are set correctly
4. Test each API endpoint independently
