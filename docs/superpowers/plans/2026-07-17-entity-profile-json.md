# Entity Profile JSON Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a derived `entity_profile_json` table that stores one stable, English-first JSON profile per wiki entity.

**Architecture:** Keep normalized tables as the source of truth and build profile rows as a consumable projection. The profile builder reads `entities`, `entity_coverage`, `entity_media_assets`, `entity_stats`, `entity_variant_summary`, `entity_categories`, `entity_facts`, `recipe_ingredients`, and `official_record_mentions`, then writes deterministic JSON keyed by entity id.

**Tech Stack:** Python 3, SQLite, pytest, existing `dst_wiki_db` derived-table pipeline.

---

### Task 1: Profile Builder Test

**Files:**
- Create: `tests/test_entity_profiles.py`
- Create: `dst_wiki_db/entity_profiles.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write the failing test**

Create `tests/test_entity_profiles.py` with a fixture database containing a single `Berry Bush` entity, one coverage row, one media asset, one stat, one variant summary row, one category, one fact, one recipe ingredient, and one official mention. Assert that `rebuild_entity_profile_json(conn)` writes one row and that `json.loads(profile_json)` contains `identity`, `coverage`, `media`, `stats`, `variants`, `categories`, `facts`, `recipes`, and `official_mentions`.

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_entity_profiles.py::test_rebuild_entity_profile_json_aggregates_entity_evidence -q`

Expected: fail because `dst_wiki_db.entity_profiles` does not exist.

- [x] **Step 3: Add `entity_profile_json` schema**

Add a table with `entity_id` unique, identity columns, `profile_json`, denormalized count columns, and indexes for kind/title lookup.

- [x] **Step 4: Implement `rebuild_entity_profile_json`**

Create `dst_wiki_db/entity_profiles.py`. Delete existing profile rows, select entities in id order, gather child rows in deterministic order, build compact dictionaries, serialize with `json.dumps(..., ensure_ascii=False, sort_keys=True)`, insert rows, commit, and return the inserted count.

- [x] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_entity_profiles.py -q`

Expected: two tests pass, including idempotence.

### Task 2: Pipeline Wiring And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`
- Modify: `README.md`
- Modify: `docs/progress.md`

- [x] **Step 1: Add schema/report expectations**

Add `entity_profile_json` to `tests/test_schema.py` and `dst_wiki_db/report.py`.

- [x] **Step 2: Wire rebuild order**

Import `rebuild_entity_profile_json` in `scripts/rebuild_derived_tables.py`, run it after `rebuild_entity_coverage`, and add its count to the emitted JSON payload.

- [x] **Step 3: Update docs**

Update `README.md` and `docs/progress.md` with the new table purpose and current count after the rebuild.

- [x] **Step 4: Run focused tests**

Run: `python3 -m pytest tests/test_entity_profiles.py tests/test_schema.py -q`

Expected: pass.

### Task 3: Rebuild Data And Verify

**Files:**
- Modify: `data/dont_starve_wiki.sqlite`
- Modify: `reports/derived_tables.json`
- Modify: `reports/inspect.json`

- [x] **Step 1: Rebuild derived tables**

Run: `python3 scripts/rebuild_derived_tables.py --db data/dont_starve_wiki.sqlite --report reports/derived_tables.json`

Expected: output includes `entity_profile_json` equal to the entity count.

- [x] **Step 2: Regenerate inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: inspection report counts `entity_profile_json`.

- [x] **Step 3: Run full verification**

Run: `python3 -m pytest -q`

Run: `sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check; select count(*) from entity_profile_json; select json_valid(profile_json) from entity_profile_json limit 1;"`

Run: `git diff --check`

Expected: tests pass, SQLite integrity is `ok`, profile count equals entity count, sample JSON is valid, and diff check exits 0.

- [ ] **Step 4: Commit and push**

Stage explicit changed files, commit with `data: build entity profile json`, push `main` to `Max179/Don-t-Starve`, fetch remote tracking, and verify local `HEAD` matches `origin/main`.
