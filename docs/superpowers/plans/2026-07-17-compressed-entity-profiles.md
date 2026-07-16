# Compressed Entity Profiles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compress `entity_profile_json.profile_json` so the committed SQLite database stays below GitHub's 100 MiB file limit while preserving full per-entity profile data.

**Architecture:** Keep queryable summary columns on `entity_profile_json` unchanged. Store the full profile payload as gzip-compressed base64 text with a `profile_encoding` marker and provide `load_profile_json(row)` so readers/tests can transparently decode profiles.

**Tech Stack:** Python 3 standard library `gzip`, `base64`, `json`, SQLite, pytest.

---

### Task 1: Compression API

**Files:**
- Modify: `tests/test_entity_profiles.py`
- Modify: `dst_wiki_db/entity_profiles.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write the failing test**

Add assertions that profile rows store `profile_encoding = 'gzip+base64+json'`, that the raw stored `profile_json` is not directly `json.loads`-able, and that `load_profile_json(row)` returns the original dictionary.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_entity_profiles.py::test_rebuild_entity_profile_json_aggregates_entity_evidence -q`

Expected: fail because `profile_encoding` and `load_profile_json` are not implemented.

- [x] **Step 3: Add schema column and migration**

Add `profile_encoding text not null default 'json'` to `entity_profile_json` and add a migration for existing databases.

- [x] **Step 4: Implement helpers**

Implement `dump_profile_json(profile)` and `load_profile_json(row_or_text, encoding=None)` in `dst_wiki_db/entity_profiles.py`, using gzip-compressed UTF-8 JSON encoded as base64 text.

- [x] **Step 5: Run focused profile tests**

Run: `python3 -m pytest tests/test_entity_profiles.py -q`

Expected: pass.

### Task 2: Rebuild And Verify Size

**Files:**
- Modify: `data/dont_starve_wiki.sqlite`
- Modify: `reports/inspect.json`
- Modify: `README.md`
- Modify: `docs/progress.md`

- [x] **Step 1: Rebuild derived tables**

Run: `python3 scripts/rebuild_derived_tables.py --db data/dont_starve_wiki.sqlite --report reports/derived_tables.json`

Expected: `entity_profile_json` remains 2,252 rows.

- [x] **Step 2: Regenerate inspect report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: report generation succeeds.

- [x] **Step 3: Vacuum database**

Run: `sqlite3 data/dont_starve_wiki.sqlite "vacuum;"`

Expected: database file size drops materially below the current 96 MiB.

- [x] **Step 4: Update docs**

Document that full profiles are stored compressed and decoded with helper functions; update the reported committed database size if useful.

- [ ] **Step 5: Verify**

Run: `python3 -m pytest -q`

Run: `sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check; select count(*) from entity_profile_json; select profile_encoding, count(*) from entity_profile_json group by profile_encoding;"`

Run: `git diff --check`

Expected: tests pass, SQLite integrity is `ok`, profile count remains 2,252, all profiles use gzip+base64+json, and diff check exits 0.

- [ ] **Step 6: Commit and push**

Commit with `data: compress entity profile payloads`, push `main`, fetch remote tracking, and verify local `HEAD` matches `origin/main`.
