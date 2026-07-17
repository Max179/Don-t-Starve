# Entity Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a derived taxonomy table that gives each entity queryable multi-label classification beyond the single coarse `entities.kind` field.

**Architecture:** Keep `entities.kind` unchanged for compatibility. Derive `entity_taxonomy` rows from entity kind, wiki categories, and parsed attributes, with one row per `(entity_id, taxonomy_type, taxonomy_key)`, preserving labels, confidence, and source evidence.

**Tech Stack:** Python 3, SQLite, pytest, existing derived-table rebuild pipeline.

---

### Task 1: Taxonomy Builder

**Files:**
- Create: `tests/test_entity_taxonomy.py`
- Create: `dst_wiki_db/taxonomy.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write the failing test**

Create a fixture with a `Bee` mob categorized as `Mobs`, `Hostile Creatures`, `Mob Dropped Items`, and `Don't Starve Together`, with health/damage stats and a spawn code. Assert that taxonomy rows include:

- `kind:mob`
- `source_category:mobs`
- `gameplay:hostile`
- `gameplay:drop_source`
- `game_mode:dst`
- `data:has_stats`
- `data:has_spawn_code`

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_entity_taxonomy.py::test_rebuild_entity_taxonomy_derives_kind_category_and_gameplay_tags -q`

Expected: fail because `dst_wiki_db.taxonomy` does not exist.

- [x] **Step 3: Add schema**

Add `entity_taxonomy` with entity id, slug/title/kind, taxonomy type, key, label, confidence, evidence source/count, and indexes by entity and taxonomy key.

- [x] **Step 4: Implement builder**

Generate taxonomy rows from:

- `entities.kind`
- distinct `entity_categories`
- category keyword mappings for gameplay/DLC/game mode tags
- stat and spawn-code evidence from `entity_stats` and `entity_attributes`

- [x] **Step 5: Run focused taxonomy tests**

Run: `python3 -m pytest tests/test_entity_taxonomy.py -q`

Expected: pass.

### Task 2: Pipeline, Profiles, And Docs

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/entity_profiles.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_entity_profiles.py`
- Modify: `tests/test_schema.py`
- Modify: `README.md`
- Modify: `docs/progress.md`

- [x] **Step 1: Wire rebuild**

Run taxonomy after categories/stats/facts/recipes are rebuilt and before profiles.

- [x] **Step 2: Add profile taxonomy**

Add `taxonomy` and `taxonomy_count` to compressed entity profiles.

- [x] **Step 3: Update docs and tests**

Add schema/report/profile expectations and document taxonomy counts.

- [x] **Step 4: Run focused tests**

Run: `python3 -m pytest tests/test_entity_taxonomy.py tests/test_entity_profiles.py tests/test_schema.py -q`

Expected: pass.

### Task 3: Rebuild And Publish

**Files:**
- Modify: `data/dont_starve_wiki.sqlite`
- Modify: `reports/derived_tables.json`
- Modify: `reports/inspect.json`

- [x] **Step 1: Rebuild derived tables**

Run: `python3 scripts/rebuild_derived_tables.py --db data/dont_starve_wiki.sqlite --report reports/derived_tables.json`

Expected: output includes `entity_taxonomy`.

- [x] **Step 2: Regenerate inspect report and vacuum if needed**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Run: `sqlite3 data/dont_starve_wiki.sqlite "vacuum;"`

Expected: database remains below GitHub hard file limit.

- [x] **Step 3: Verify**

Run: `python3 -m pytest -q`

Run: `sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check; select count(*) from entity_taxonomy; select taxonomy_type, count(*) from entity_taxonomy group by taxonomy_type order by count(*) desc;"`

Run: `git diff --check`

Expected: tests pass, integrity is `ok`, taxonomy rows are nonzero, and diff check exits 0.

- [ ] **Step 4: Commit and push**

Commit with `data: add entity taxonomy tags`, push `main`, fetch remote tracking, and verify local `HEAD` matches `origin/main`.
