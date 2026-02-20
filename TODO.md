# TODO — Known Bugs & Improvement Backlog

---

## Bugs

### 1. Article Title Extraction — Partial Title Captured
**Severity:** Medium
**File:** `html_cleaner.py` — `_extract_logic()`

The article title extraction sometimes picks up only a fragment of the title, for example extracting `(12 months)` instead of the full title. The regex that strips trailing parenthetical suffixes (e.g., country names like `"Solar Report (Australia)"`) is too aggressive and may strip content that is part of the title itself.

**Fix needed:** Improve the regex so it only removes trailing country/region qualifiers, not content that is semantically part of the title.

---

### 2. Google Sheets Duplicate Rows on Append
**Severity:** Low (non-critical)
**File:** `google_sheets_service.py` — `log_processed_item()`

When an article is logged to Google Sheets, a duplicate row is sometimes created alongside the intended row, resulting in two entries for the same article. This is suspected to be a race condition or retry issue in the Google Apps Script `doPost` handler.

**Fix needed:** Investigate the GAS `doPost` handler — it may be processing the request twice due to redirect-following behaviour. Add deduplication logic either in GAS (check before appending) or in the Python client (only log if not already present).

---

### 3. Tableau Field Prefix Removal — Incomplete Blacklist
**Severity:** Low
**Files:** `data_field_analyzer.py`, `tableau_xml_cleaner.py`

Both files maintain a list of Tableau aggregation/type prefixes to strip (e.g., `sum:`, `yr:`, `mn:`, `tqr:`, `io:`). Tableau can introduce new prefixes that aren't in the list, causing field names to appear with their raw prefix and fail to match metadata.

**Current blacklist:** `sum|none|avg|min|max|attr|usr|tmn|pcto|win|med|pcdf|mn|yr|tqr|io`

**Fix needed:** Replace the static blacklist with a dynamic approach — strip any lowercase word prefix followed by `:` at the start of the field name (i.e., match `^[a-z]+:` and remove it). This would be future-proof.

**Important:** Both files must always have identical prefix lists. If you add a prefix to one file, add it to the other immediately.

---

### 4. Update Feature — Relationship Issues in Preview Mode
**Severity:** High
**File:** `workflow.py`, `relationship_service.py`

The update/preview flow has two related problems:

**a. Duplicate related articles in preview**
After generating a preview, the new HTML shows duplicated entries in the "Related Articles" section. The relationship building logic queries existing relationships from Google Sheets and merges them with the current run's relationships, but doesn't deduplicate properly during the update flow.

**b. Missing related articles in original HTML**
When comparing old vs. new in preview mode, the old HTML (fetched from Google Sheets) is missing related articles that do exist in Intercom. This suggests the Google Sheets HTML was not updated after relationships were last injected — likely because the Sheets log was not written after a relationship update step.

**Fix needed:**
- Ensure `log_processed_item()` is always called after relationship injection updates
- Add deduplication by title when merging existing + new relationships in `build_chart_to_articles_map()` and `build_field_to_charts_map()`

---

### 5. Truncated Field Display Name in Chart HTML
**Severity:** Low
**File:** `workflow.py` — `_process_single_chart()`

When GPT extracts a field's display name from a chart image, long names appear truncated (e.g., `"PV kW-DC Seg..."`). There is post-processing logic in `extract_field_names()` that resolves or discards truncated display names for the **data field article**, but the **chart article HTML** still uses the original (possibly truncated) display name from the GPT response.

**Fix needed:** After `extract_field_names()` resolves truncated display names, feed the resolved names back into the chart JSON before formatting the chart HTML. The `display_name_map` already contains the resolved values — they just need to be applied when building the chart HTML's field labels.

---

### 6. Progress Bar Not Working Correctly
**Severity:** Low
**File:** Frontend UI (templates)

The progress bar in the web UI does not accurately reflect processing progress during long-running publish jobs.

**Fix needed:** Implement server-sent events (SSE) or a polling endpoint that reports per-chart/per-field progress. The current implementation likely uses a static estimate rather than real-time progress.

---

## Notes & Workarounds

### Deleting Articles Is Slow
The delete feature works correctly but is slow — it calls the Intercom API and Google Sheets API sequentially for each article. For bulk deletions, it is faster to delete directly via the Intercom web UI and then manually remove the corresponding row from the Google Sheet. The automated delete is most useful for small numbers of articles where convenience matters more than speed.
