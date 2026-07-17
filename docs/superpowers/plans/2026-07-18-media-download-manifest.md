# Media Download Manifest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a queryable media download manifest so every known entity image asset has a deterministic download target, priority, and status.

**Architecture:** Keep `entity_media_assets` as the unified media evidence table. Add derived `entity_media_downloads` rows keyed by media asset id, joining source/entity metadata and assigning queue priority from primary/variant/direct-url signals. Store direct download URLs when available and file-page URLs otherwise.

**Tech Stack:** Python 3, SQLite, pytest, existing derived-table rebuild pipeline.

---

### Task 1: Manifest Builder

**Files:**
- Create: `tests/test_media_downloads.py`
- Create: `dst_wiki_db/media_downloads.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write the failing test**

Create a fixture with a primary infobox image that has `original_url` and a page-reference variant image that has only `description_url`. Assert that `rebuild_entity_media_downloads(conn)` creates deterministic target paths, direct/file-page URL status, pending download status, and primary-before-variant priority.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_media_downloads.py::test_rebuild_entity_media_downloads_prioritizes_primary_and_variant_assets -q`

Expected: fail because `dst_wiki_db.media_downloads` does not exist.

- [x] **Step 3: Add schema**

Add `entity_media_downloads` with entity/media/source identity, download URL, file page URL, target path, URL status, download status, priority, variant fields, and indexes.

- [x] **Step 4: Implement builder**

Read `entity_media_assets` joined to `entities` and `sources`, generate one manifest row per media asset, classify URL status as `direct_url`, `file_page_only`, or `missing_url`, and sort priority by primary, direct URL, variant, and source row id.

- [x] **Step 5: Run focused tests**

Run: `python3 -m pytest tests/test_media_downloads.py -q`

Expected: pass.

### Task 2: Pipeline, Reports, And Docs

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`
- Modify: `README.md`
- Modify: `docs/progress.md`

- [x] **Step 1: Wire rebuild**

Run media download manifest after `rebuild_entity_media_assets`.

- [x] **Step 2: Add report/schema expectations**

Add the new table to count reports and schema tests.

- [x] **Step 3: Update docs**

Document count, direct URL/file page coverage, priority model, and the fact that binary downloads remain out of git by default.

- [x] **Step 4: Run focused tests**

Run: `python3 -m pytest tests/test_media_downloads.py tests/test_schema.py -q`

Expected: pass.

### Task 3: Rebuild And Publish

**Files:**
- Modify: `data/dont_starve_wiki.sqlite`
- Modify: `reports/derived_tables.json`
- Modify: `reports/inspect.json`

- [x] **Step 1: Rebuild derived tables**

Run: `python3 scripts/rebuild_derived_tables.py --db data/dont_starve_wiki.sqlite --report reports/derived_tables.json`

Expected: output includes `entity_media_downloads`.

- [x] **Step 2: Regenerate inspect and vacuum**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Run: `sqlite3 data/dont_starve_wiki.sqlite "vacuum;"`

Expected: database remains below GitHub hard file limit.

- [ ] **Step 3: Verify**

Run: `python3 -m pytest -q`

Run: `sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check; select count(*) from entity_media_downloads; select url_status, count(*) from entity_media_downloads group by url_status;"`

Run: `git diff --check`

Expected: tests pass, integrity is `ok`, manifest rows match media assets, URL status counts are visible, and diff check exits 0.

- [ ] **Step 4: Commit and push**

Commit with `data: add media download manifest`, push `main`, fetch remote tracking, and verify local `HEAD` matches `origin/main`.
