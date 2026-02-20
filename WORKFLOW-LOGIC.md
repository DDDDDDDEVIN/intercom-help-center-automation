# Workflow Logic — Detailed Technical Reference

This document explains, step by step, how the automation pipeline works. It is intended for new developers who need to understand what the code does and why each decision was made.

---

## High-Level Overview

The system takes a **Joomla article ID** as input and produces structured, linked **Intercom Help Center articles** as output. One Joomla article typically contains several charts. For each chart, the system:

1. Downloads the Tableau workbook XML to understand the chart's structure
2. Sends the chart image + XML context to GPT to identify the data fields used
3. For each data field, analyzes and publishes a **Data Dictionary** article
4. Publishes a **Chart Library** article that links to those data fields
5. Publishes an **Article Library** article that links to all the charts

After everything is published, the system goes back and stitches bidirectional links:
- Each data field article gets a "Related Charts" section
- Each chart article gets a "Related Articles" section

---

## Entry Points

There are two main entry points in `app.py`:

| Route | Function | Description |
|---|---|---|
| `POST /api/articles/create` | `execute()` | Publish new articles for the first time |
| `POST /api/articles/update` | `execute_update()` | Regenerate and update existing articles |
| `POST /api/articles/update` with `"preview": true` | `execute_update(preview_mode=True)` | Generate new HTML and return a side-by-side comparison without writing anything |

---

## Step 1 — Download Article from Joomla (`JoomlaService`)

**File:** `src/services/joomla_service.py`

The system fetches the Joomla article using its ID via the Joomla REST API. The raw HTML of the article is returned.

Key detail: The article title has any country suffix in parentheses removed (e.g., `"Solar Market Share (Australia)"` → `"Solar Market Share"`). This normalized title is used as the lookup key in Google Sheets.

---

## Step 2 — Parse the HTML (`HTMLCleaner`)

**File:** `src/services/html_cleaner.py`

The raw Joomla HTML is messy — it contains GPT prompts, license text, inline styles, and Tableau image embeds. The cleaner does two phases:

**Phase 1 — Heavy Cleaning:**
- Strips `<script>`, `<style>`, and GPT prompt blocks
- Converts `<hr>` tags into `[[SECTION_DIVIDER]]` markers
- Converts `<img>` tags that contain Tableau embeds into `[[CHART_ANCHOR|view_id|image_url|title|tabs_name]]` markers
- Strips all remaining HTML tags

**Phase 2 — Logic Extraction:**
The cleaned text is split by `[[SECTION_DIVIDER]]`. Each section is scanned for `[[CHART_ANCHOR]]` markers.

- The **first** valid image is treated as the **slider** (decorative header). It is used to extract `category` and `technology` metadata from its title.
- Subsequent images become **charts**. For each chart, the system extracts:
  - `title` — text appearing immediately before the image
  - `image_url` — the Tableau screenshot URL
  - `tabs_name` — the Tableau view/sheet name (used for workbook lookup)
  - `shows` — text appearing after the image, cleaned of junk phrases

**Output:** A list of chart dictionaries, each containing `view_id`, `title`, `image_url`, `tabs_name`, `shows`.

---

## Step 3 — Authenticate with Tableau (`TableauService`)

**File:** `src/services/tableau_service.py`

Signs in to the Tableau Server API and stores the `auth_token` and `site_id` for use in subsequent API calls. These are also passed to the XML analyzer and data field analyzer.

---

## Step 4 — Per-Chart Processing Loop (`_process_single_chart`)

**File:** `src/services/workflow.py`

For each chart extracted from the article, the system runs a multi-step sub-pipeline:

### 4a — Duplicate Check (Publish mode only)

Calls `GoogleSheetsService.check_duplicate()` using the original chart name (before title-casing). If an entry already exists in the `chart_library` sheet, the chart is **skipped** entirely in publish mode. In update mode, this check is skipped and the existing entry is looked up instead.

### 4b — Find the Tableau Workbook

Calls `TableauService.search_workbooks(tabs_name)` which searches the Tableau API for views matching the `tabs_name`. Multiple workbooks may match (e.g., same chart name in different projects). The system then picks the one belonging to the configured `TABLEAU_GLOBAL_PROJECT_ID`.

### 4c — Download and Clean the Workbook XML (`TableauXMLCleaner`)

**File:** `src/services/tableau_xml_cleaner.py`

Downloads the `.twbx` workbook file (a ZIP), extracts the `.twb` XML inside it, and parses it to extract a clean summary of the target worksheet:
- **Title** — from the worksheet's `<title>` node, falling back to the sheet name
- **Y-Axis** (`rows`), **X-Axis** (`cols`) — cleaned field names
- **Filters** — field names used as filters (Action and Measure Names filters are excluded)

Field name cleaning removes Tableau prefixes (`sum:`, `yr:`, `mn:`, `tqr:`, `io:`, `win:`, `med:`, `pcdf:`, etc.), strips SQL proxy namespace prefixes like `[sqlproxy.xxx].`, removes wrapping `[]` and `()`, and decomposes formula expressions like `INDEX * Capacity` into separate fields `INDEX, Capacity`.

**Output:** A text block like:
```
=== Chart: My Sheet ===
Title: My Chart Title
Y-Axis: Capacity, Index
X-Axis: Date
Filters: Brand, Country
```

### 4d — GPT Chart Analysis (`ChatGPTService.analyze_chart`)

**File:** `src/services/chatgpt_service.py`

Sends two things to the GPT vision model:
1. The XML context text (from step 4c) as the system prompt
2. The Tableau chart image URL as a user message

GPT returns a JSON object identifying which Tableau fields correspond to each visual axis:

```json
{
  "Vertical": [{"field": "Capacity", "display_name": "Total Capacity (MW)"}],
  "Horizontal": [{"field": "Date", "display_name": null}],
  "Dimensions": [...],
  "Measures": [...]
}
```

The `field` key must match the Tableau metadata exactly. The `display_name` is the visible label on the chart (e.g., axis title) — used as the human-readable name for the data field article. If the chart label is truncated (ends with `..`), a post-processing step checks whether the truncated prefix exists in the full field name and resolves or discards it accordingly.

### 4e — Extract Field Names

`extract_field_names()` deduplicates the GPT response across all four axes and returns:
- `field_names` — list of raw Tableau field names
- `display_name_map` — mapping of field name → visible label (or None)

---

## Step 5 — Per-Field Processing Loop (`_process_single_data_field`)

For each field name returned by GPT, the system runs another sub-pipeline:

### 5a — Duplicate Check

Same as chart: if the field already exists in `data_dictionary` sheet, it is skipped in publish mode but looked up in update mode.

### 5b — Resolve Human Name

Priority order:
1. `display_name` from GPT chart analysis (if not None) — most accurate since it's the actual label on the chart
2. `ChatGPTService.rewrite_field_name()` — calls GPT with the field name + XML context to generate a clean business name
3. Original `field_name` — fallback if both above return null

### 5c — Extract Deep Field Context (`DataFieldAnalyzer`)

**File:** `src/services/data_field_analyzer.py`

Re-downloads the workbook XML (same process as `TableauXMLCleaner`), then builds a rich knowledge base:

- **`id_to_human`** — translates Tableau internal IDs (e.g., `[Calculation_1234]`) to human names
- **`field_map`** — maps every field's normalized name to its role, datatype, formula (if calculated), etc.

For each target field, it generates a context tree by recursively following formula dependencies. For example, if `Market Share` = `SUM([Sales]) / SUM([Total Market])`, the context tree would show:
```
FIELD: [Market Share] (Calculation)
   Formula: SUM([Sales]) / SUM([Total Market])
  └─ FIELD: [Sales] (Native integer)
     Values: (Numeric Measure - No hardcoded filter range found)
  └─ FIELD: [Total Market] (Native integer)
     Values: (Numeric Measure - No hardcoded filter range found)
```

For native (non-calculated) fields it also scrapes filter values (for categorical fields) or min/max ranges (for numeric measures) from the XML.

**Fields not found in the metadata are no longer skipped** — they are still processed with whatever context is available. Previously this filter was considered too aggressive and was removed.

### 5d — Analyze Field with GPT (`ChatGPTService.analyze_data_field`)

Sends the context tree to GPT (text model, no image) with instructions to extract:
- `definition` — 1-sentence plain English business definition
- `calculation_explanation` — how the field is computed
- `pseudo_formula` — human-readable formula (or "None" for native fields)
- `considerations` — notable filter values, ranges, or caveats

### 5e — Format HTML (`HTMLFormatter.format_data_field_html`)

**File:** `src/services/html_formatter.py`

Converts the GPT JSON response into Intercom-compatible HTML with sections for Term, Definition, Calculation, Considerations, and a Related Charts placeholder.

### 5f — Publish to Intercom and Log to Google Sheets

Creates the article in the `data_dictionary` Intercom collection. On success, logs a row to the `data_dictionary` Google Sheet with:
`original_name | human_name | intercom_url | intercom_id | html`

---

## Step 6 — Create Chart Article

After all data fields for a chart are processed, the system builds and publishes the **Chart Library** article.

### 6a — Build Field Mapping

For newly created fields: batch-lookup their human names and URLs from Google Sheets.
For skipped/existing fields: their URLs were already stored in `skipped_fields` from the duplicate check.

This produces a `field_mapping` dict: `{field_name: {human: "...", url: "..."}}`

### 6b — Clean Chart JSON

`_clean_chart_json_fields()` applies the same Tableau prefix removal (using `DataFieldAnalyzer.clean_tableau_field_name`) to the GPT-extracted field names in the chart JSON. This ensures display names in the chart article match the actual published field names.

### 6c — Format Chart HTML (`HTMLFormatter.format_chart_with_json_html`)

Creates a rich chart article with:
- Chart title and image
- Category and Availability
- Shows, Best Used For, Considerations (TBC placeholders until manually filled)
- Axes (Vertical / Horizontal) with linked field names
- Dimensions and Measures with linked field names
- Related Charts and Related Articles sections (populated later)

### 6d — Publish Chart to Intercom and Log

Same publish-and-log pattern as data fields. Uses the `chart_library` collection.

---

## Step 7 — Create Main Article

After all charts are processed, the system builds the **Article Library** entry — a summary page with the article title, category, technology, and a list of embedded charts (each with its image, title linked to the Chart Library article, and "Shows" description).

---

## Step 8 — Relationship Injection (`RelationshipService`)

**File:** `src/services/relationship_service.py`

This step runs AFTER everything is published (so all Intercom URLs exist).

### 8a — Build field → charts map

For each processed chart, the `field_mapping` dict tells us which fields it used. This is inverted into:
`{field_name: [{title: chart_title, url: chart_url}, ...]}`

Existing relationships already stored in Google Sheets HTML are also merged in to avoid losing previously established links.

### 8b — Inject Related Charts into Data Field articles

For each data field that was created or already existed:
1. Fetch its current HTML (from Google Sheets or Intercom directly)
2. Call `HTMLFormatter.inject_related_charts_to_field_html()` which either:
   - Replaces an existing "Related Charts" section if one already exists
   - Inserts a new section before the `<hr>` divider at the bottom
3. Update the article in Intercom
4. Update the row in Google Sheets with the new HTML (critical — prevents stale HTML on next run)

### 8c — Build chart → articles map

Maps each chart to the article that just referenced it, merging with any previously known related articles from Google Sheets.

### 8d — Inject Related Articles into Chart articles

Same inject-update-log pattern as 8b, for "Related Articles" sections in chart articles.

---

## Google Sheets Schema

Each sheet (`data_dictionary`, `chart_library`, `article_library`) has the same 5-column schema:

| Column | Content |
|---|---|
| A (`original_name`) | Raw Tableau name or original chart title (used as lookup key) |
| B (`human_name`) | Human-readable display name |
| C (`intercom_url`) | Full Intercom article URL |
| D (`intercom_id`) | Intercom article numeric ID |
| E (`html`) | Full article HTML (used for relationship injection and update comparison) |

The Google Sheets serves as both a **duplicate registry** and an **HTML cache**. Storing the HTML is critical because relationship injection needs to modify existing articles without re-calling GPT.

---

## Preview Mode (Update Only)

When `preview_mode=True`, the entire pipeline runs but nothing is written to Intercom or Google Sheets. Instead, for each item (data field, chart, main article), the system returns a comparison object:

```json
{
  "article_type": "data_field | chart | main_article",
  "article_title": "...",
  "old_html": "...",   // Current HTML from Google Sheets / Intercom
  "new_html": "...",   // Freshly regenerated HTML
  "intercom_article_id": "...",
  "collection_id": "..."
}
```

The frontend displays these as a diff for the user to review. After approval, `POST /api/articles/update/confirm` applies the selected updates.

---

## Service Responsibilities Summary

| Service | Responsibility |
|---|---|
| `JoomlaService` | Download article HTML from Joomla API |
| `HTMLCleaner` | Parse Joomla HTML → chart list + metadata |
| `TableauService` | Authenticate with Tableau, find workbook IDs |
| `TableauXMLCleaner` | Download workbook XML, extract chart structure summary |
| `DataFieldAnalyzer` | Download workbook XML, build deep field context trees |
| `ChatGPTService` | Analyze chart images, analyze data fields, rewrite field names |
| `HTMLFormatter` | Convert GPT output into Intercom HTML; inject relationship sections |
| `IntercomService` | Create/update/delete Intercom articles |
| `GoogleSheetsService` | Log rows, check duplicates, batch lookup, relationship queries |
| `RelationshipService` | Orchestrate post-publish relationship injection across all article types |
| `WorkflowOrchestrator` | Coordinate all services; main entry point for both publish and update flows |
