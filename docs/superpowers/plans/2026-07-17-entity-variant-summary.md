# Entity Variant Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a per-entity variant summary table that merges variant evidence from attributes, stats, entity variants, and media assets.

**Architecture:** Keep `entity_variants`, `entity_attributes`, `entity_stats`, `entity_facts`, `recipe_ingredients`, and `entity_media_assets` as detailed provenance tables. Add derived `entity_variant_summary` rows keyed by `(entity_id, variant_key)`, with normalized type/label, counts by evidence source, media presence, stat/fact/recipe presence, and a combined confidence score.

**Tech Stack:** Python 3.9+, SQLite, `pytest`.

---

## File Structure

- Create `dst_wiki_db/variant_summary.py` for rebuilding merged variant rows.
- Create `tests/test_variant_summary.py` for merged variant evidence behavior.
- Modify `dst_wiki_db/schema.py` to add `entity_variant_summary`.
- Modify `scripts/rebuild_derived_tables.py` to rebuild variant summary after `entity_media_assets` and before `entity_coverage`.
- Modify `dst_wiki_db/report.py` and `tests/test_schema.py` to count/expect the table.
- Modify `README.md` and `docs/progress.md` with measured variant summary results.
- Regenerate `reports/derived_tables.json`, `reports/inspect.json`, and `data/dont_starve_wiki.sqlite`.

### Task 1: Schema And Variant Summary Builder

**Files:**
- Create: `tests/test_variant_summary.py`
- Create: `dst_wiki_db/variant_summary.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write failing variant summary tests**

```python
from dst_wiki_db.variant_summary import rebuild_entity_variant_summary


def test_rebuild_entity_variant_summary_merges_data_and_media_evidence(tmp_path):
    ...
```

- [x] **Step 2: Run focused test and verify RED**

Run: `python3 -m pytest tests/test_variant_summary.py::test_rebuild_entity_variant_summary_merges_data_and_media_evidence -q`

Expected: fail because `dst_wiki_db.variant_summary` does not exist.

- [x] **Step 3: Add `entity_variant_summary` schema**

Add fields for entity id, slug/title/kind, variant key/type/label, counts for attributes, stats, facts, recipes, entity variant rows, media assets, primary media assets, booleans for data/media/stat/fact/recipe evidence, confidence, and source summary.

- [x] **Step 4: Implement `rebuild_entity_variant_summary`**

Collect variant keys from `entity_variants`, non-empty `variant_key` fields in attributes/stats/facts/recipes, and `entity_media_assets.is_variant=1`. Merge per entity/key, infer type/label from strongest evidence, count evidence sources, and write deterministic rows.

- [x] **Step 5: Run variant summary tests**

Run: `python3 -m pytest tests/test_variant_summary.py -q`

Expected: tests pass.

### Task 2: Wire Rebuild And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`

- [x] **Step 1: Add schema/report expectations**

Add `entity_variant_summary` to schema expectations and report count tables.

- [x] **Step 2: Wire rebuild script**

Import `rebuild_entity_variant_summary`, run it after media assets, and include the count in `reports/derived_tables.json`.

- [x] **Step 3: Run full tests**

Run: `python3 -m pytest -q`

Expected: all tests pass.

### Task 3: Refresh Data And Publish

**Files:**
- Modify: `data/dont_starve_wiki.sqlite`
- Modify: `reports/derived_tables.json`
- Modify: `reports/inspect.json`
- Modify: `README.md`
- Modify: `docs/progress.md`

- [x] **Step 1: Rebuild derived tables**

Run:

```bash
python3 scripts/rebuild_derived_tables.py \
  --db data/dont_starve_wiki.sqlite \
  --report reports/derived_tables.json
```

Expected: `entity_variant_summary` is populated with merged data/media variant rows.

- [x] **Step 2: Refresh inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: inspection report counts `entity_variant_summary`.

- [x] **Step 3: Document measured results**

Update README and progress docs with total merged variant rows, type distribution, and evidence coverage.

- [ ] **Step 4: Verify, commit, and push**

Run:

```bash
python3 -m pytest -q
sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check"
git diff --check
```

Expected: all pass. Stage only this slice, commit as `data: summarize entity variants`, and push `main`.
