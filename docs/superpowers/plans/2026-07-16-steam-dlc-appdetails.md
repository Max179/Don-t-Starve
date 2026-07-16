# Steam DLC Appdetails Enrichment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich every Steam DLC id listed by Don't Starve and Don't Starve Together with official English appdetails, including its real title, description, parent game, and official media URLs.

**Architecture:** Keep the existing `steam_dlc_id` records as evidence that a parent app listed a DLC, then add one `steam:dlc_appdetails` record per discovered DLC appid. Reuse the existing official-record schema and upsert path so reruns remain idempotent and failed Steam requests are retained as explicit records.

**Tech Stack:** Python 3.9+, SQLite, `requests`, `pytest`, Steam Store appdetails JSON.

---

## File Structure

- Modify `dst_wiki_db/official.py` to convert and fetch DLC appdetails records.
- Modify `scripts/fetch_official_sources.py` to fetch DLC details by default and expose a skip flag for constrained runs.
- Modify `tests/test_official.py` to cover successful, invalid, and failed DLC detail requests.
- Modify `README.md` and `docs/progress.md` after the committed database is refreshed.
- Regenerate `reports/official_sources.json`, `reports/derived_tables.json`, `reports/inspect.json`, and `data/dont_starve_wiki.sqlite`.

### Task 1: Convert DLC Appdetails Payloads

**Files:**
- Modify: `tests/test_official.py`
- Modify: `dst_wiki_db/official.py`

- [x] **Step 1: Write the failing converter test**

```python
def test_records_from_steam_dlc_appdetails_preserves_parent_and_media():
    payload = {
        "4211520": {
            "success": True,
            "data": {
                "type": "dlc",
                "name": "Don't Starve Together: Starter Pack 2026",
                "steam_appid": 4211520,
                "short_description": "Starter pack.",
                "fullgame": {"appid": "322330", "name": "Don't Starve Together"},
                "header_image": "https://cdn.test/header.jpg",
            },
        }
    }

    record = records_from_steam_dlc_appdetails(4211520, 322330, payload)

    assert record.record_type == "dlc_appdetails"
    assert record.title == "Don't Starve Together: Starter Pack 2026"
    assert record.payload["parent_appid"] == 322330
    assert record.payload["data"]["header_image"] == "https://cdn.test/header.jpg"
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `python3 -m pytest tests/test_official.py::test_records_from_steam_dlc_appdetails_preserves_parent_and_media -q`

Expected: fail because `records_from_steam_dlc_appdetails` does not exist.

- [x] **Step 3: Implement the converter**

Add `records_from_steam_dlc_appdetails(dlc_appid, parent_appid, payload)` that returns one `OfficialRecord`. Use `dlc_appdetails` as the record type, retain `parent_appid` alongside the original Steam data, and return `invalid_payload` or `failed` records when the payload cannot prove a valid app.

- [x] **Step 4: Run converter tests**

Run: `python3 -m pytest tests/test_official.py -q`

Expected: all tests pass.

### Task 2: Fetch Discovered DLC Details

**Files:**
- Modify: `tests/test_official.py`
- Modify: `dst_wiki_db/official.py`
- Modify: `scripts/fetch_official_sources.py`

- [x] **Step 1: Write the failing fetch orchestration test**

```python
def test_fetch_steam_records_fetches_details_for_discovered_dlc():
    session = SequencedSession([
        parent_appdetails_payload,
        parent_news_payload,
        dlc_appdetails_payload,
    ])

    records = fetch_steam_records(
        appids=[322330],
        news_count=1,
        timeout=5,
        session=session,
        include_dlc_details=True,
    )

    assert [record.record_type for record in records] == [
        "appdetails",
        "steam_dlc_id",
        "news",
        "dlc_appdetails",
    ]
    assert session.calls[-1][1]["appids"] == "4211520"
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `python3 -m pytest tests/test_official.py::test_fetch_steam_records_fetches_details_for_discovered_dlc -q`

Expected: fail because the fetcher does not request DLC appdetails.

- [x] **Step 3: Implement DLC fetching**

Collect unique `(dlc_appid, parent_appid)` pairs while parsing parent appdetails, request each DLC through the same Store appdetails endpoint, append converted records, and preserve request failures as `dlc_appdetails` records. Add `include_dlc_details=True` to `fetch_steam_records` and `--skip-steam-dlc-details` to the CLI.

- [x] **Step 4: Run all tests**

Run: `python3 -m pytest -q`

Expected: all tests pass.

### Task 3: Refresh Official Data And Derived Links

**Files:**
- Modify: `data/dont_starve_wiki.sqlite`
- Modify: `reports/official_sources.json`
- Modify: `reports/derived_tables.json`
- Modify: `reports/inspect.json`
- Modify: `README.md`
- Modify: `docs/progress.md`

- [x] **Step 1: Fetch current official records**

Run:

```bash
python3 scripts/fetch_official_sources.py \
  --db data/dont_starve_wiki.sqlite \
  --steam-news-count 25 \
  --timeout 30 \
  --report reports/official_sources.json
```

Expected: output includes `steam:dlc_appdetails` records for the discovered DLC ids.

- [x] **Step 2: Rebuild official entity mentions**

Run:

```bash
python3 scripts/rebuild_derived_tables.py \
  --db data/dont_starve_wiki.sqlite \
  --report reports/derived_tables.json
```

Expected: `official_record_mentions` increases when DLC names and descriptions mention known entities.

- [x] **Step 3: Refresh inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: the report includes the new official-record total.

- [x] **Step 4: Document measured results**

Update `README.md` and `docs/progress.md` with the exact DLC detail count, official-record total, mention count, status distribution, and examples found in the refreshed database.

- [ ] **Step 5: Verify and publish**

Run:

```bash
python3 -m pytest -q
sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check"
git diff --check
```

Expected: tests pass, SQLite reports `ok`, and the diff check is clean. Stage only the files listed in this plan, commit with `data: enrich official Steam DLC records`, and push `main` to GitHub.
