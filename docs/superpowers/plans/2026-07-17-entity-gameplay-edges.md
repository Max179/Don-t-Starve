# Entity Gameplay Edges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a typed gameplay relationship table so recipe ingredients and parsed facts become queryable entity-to-entity edges.

**Architecture:** Keep `recipe_ingredients`, `recipe_ingredient_targets`, `entity_facts`, and `entity_fact_targets` as detailed evidence tables. Build a derived `entity_gameplay_edges` table with forward and inverse edges for recipes, drops, dropped-by, sold-by, spawn-from, and spawns facts, then expose compact relationship lists in entity JSON profiles.

**Tech Stack:** Python 3, SQLite, pytest, existing `dst_wiki_db` derived-table pipeline.

---

### Task 1: Edge Builder

**Files:**
- Create: `tests/test_gameplay_edges.py`
- Create: `dst_wiki_db/gameplay_edges.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write the failing test**

Create `tests/test_gameplay_edges.py` with one crafted entity, one ingredient entity, one mob entity, one drop entity, one recipe ingredient target, and one entity fact target. Assert that `rebuild_entity_gameplay_edges(conn)` writes forward and inverse edges:

- `uses_ingredient`
- `ingredient_for`
- `drops`
- `dropped_by`

- [x] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_gameplay_edges.py::test_rebuild_entity_gameplay_edges_adds_forward_and_inverse_edges -q`

Expected: fail because `dst_wiki_db.gameplay_edges` does not exist.

- [x] **Step 3: Add `entity_gameplay_edges` schema**

Add columns for `entity_id`, `related_entity_id`, titles/slugs/kinds, `edge_type`, `edge_group`, `direction`, source table/row id, quantity/probability/variant evidence, confidence, and indexes by entity, related entity, and edge type.

- [x] **Step 4: Implement `rebuild_entity_gameplay_edges`**

Delete existing rows. Insert recipe edges from `recipe_ingredient_targets`, including inverse `ingredient_for` rows. Insert fact edges from `entity_fact_targets`, mapping each fact type to forward and inverse semantic edge names. Commit and return inserted count.

- [x] **Step 5: Run test to verify it passes**

Run: `python3 -m pytest tests/test_gameplay_edges.py -q`

Expected: edge builder and idempotence tests pass.

### Task 2: Pipeline, Profiles, And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/entity_profiles.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_entity_profiles.py`
- Modify: `tests/test_schema.py`
- Modify: `README.md`
- Modify: `docs/progress.md`

- [x] **Step 1: Wire rebuild order**

Import `rebuild_entity_gameplay_edges` and run it after `rebuild_entity_targets` and before `rebuild_entity_variant_summary`.

- [x] **Step 2: Add profile relationships**

Add `relationships` and `relationship_count` to `entity_profile_json`, populated from `entity_gameplay_edges`.

- [x] **Step 3: Update tests and docs**

Update schema tests, profile tests, report counts, README, and progress notes.

- [x] **Step 4: Run focused tests**

Run: `python3 -m pytest tests/test_gameplay_edges.py tests/test_entity_profiles.py tests/test_schema.py -q`

Expected: pass.

### Task 3: Rebuild Data And Publish

**Files:**
- Modify: `data/dont_starve_wiki.sqlite`
- Modify: `reports/derived_tables.json`
- Modify: `reports/inspect.json`

- [x] **Step 1: Rebuild derived tables**

Run: `python3 scripts/rebuild_derived_tables.py --db data/dont_starve_wiki.sqlite --report reports/derived_tables.json`

Expected: output includes `entity_gameplay_edges`.

- [x] **Step 2: Regenerate inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: inspection report counts `entity_gameplay_edges`.

- [x] **Step 3: Verify**

Run: `python3 -m pytest -q`

Run: `sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check; select count(*) from entity_gameplay_edges; select edge_type, count(*) from entity_gameplay_edges group by edge_type order by count(*) desc;"`

Run: `git diff --check`

Expected: tests pass, SQLite integrity is `ok`, edge counts are nonzero, and diff check exits 0.

- [ ] **Step 4: Commit and push**

Commit with `data: add gameplay relationship edges`, push `main`, fetch remote tracking, and verify local `HEAD` matches `origin/main`.
