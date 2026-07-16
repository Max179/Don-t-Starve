# Entity Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a queryable per-entity coverage table that summarizes whether each Don't Starve entry has source mappings, attributes, stats, images, variants, categories, relation/fact targets, official mentions, and remaining data gaps.

**Architecture:** Keep existing normalized tables as source-of-truth. Add a derived `entity_coverage` table rebuilt from aggregate joins across entity, image, stat, variant, category, relation, fact, recipe, and official mention tables. Store compact boolean flags, counts, a coverage score, and a pipe-delimited gap list for triage.

**Tech Stack:** Python 3.9+, SQLite, `pytest`.

---

## File Structure

- Create `dst_wiki_db/entity_coverage.py` for per-entity coverage aggregation.
- Create `tests/test_entity_coverage.py` for complete/missing coverage behavior.
- Modify `dst_wiki_db/schema.py` to add `entity_coverage`.
- Modify `scripts/rebuild_derived_tables.py` to rebuild coverage after target resolution.
- Modify `dst_wiki_db/report.py` and `tests/test_schema.py` to count/expect the table.
- Modify `README.md` and `docs/progress.md` with measured coverage results.
- Regenerate `reports/derived_tables.json`, `reports/inspect.json`, and `data/dont_starve_wiki.sqlite`.

### Task 1: Schema And Aggregator

**Files:**
- Create: `tests/test_entity_coverage.py`
- Create: `dst_wiki_db/entity_coverage.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write failing coverage tests**

```python
from dst_wiki_db.entity_coverage import rebuild_entity_coverage
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_coverage_summarizes_complete_and_missing_entries(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(conn, key="fandom", name="Fandom", base_url="https://dontstarve.fandom.com", api_url="https://dontstarve.fandom.com/api.php", role="comparison")
    full_id = upsert_entity(conn, canonical_title="Bee", kind="mob", primary_source_id=source_id, primary_page_id=1, canonical_url="https://example.test/Bee", summary="")
    missing_id = upsert_entity(conn, canonical_title="Mystery", kind="item", primary_source_id=source_id, primary_page_id=2, canonical_url="https://example.test/Mystery", summary="")

    result = rebuild_entity_coverage(conn)

    assert result == 2
```

- [x] **Step 2: Run focused test and verify RED**

Run: `python3 -m pytest tests/test_entity_coverage.py::test_rebuild_entity_coverage_summarizes_complete_and_missing_entries -q`

Expected: fail because `dst_wiki_db.entity_coverage` does not exist.

- [x] **Step 3: Add `entity_coverage` schema**

Add one row per entity with title, kind, source count, raw evidence count, attribute/stat/image/page-image/variant/category/relation/fact/recipe/official mention counts, boolean coverage flags, a 0-100 coverage score, and `missing_summary`.

- [x] **Step 4: Implement `rebuild_entity_coverage`**

Aggregate all existing tables with left joins grouped by entity. Set missing tokens such as `source`, `attributes`, `stats`, `images`, `variants`, `official_mentions`, and `targets` only when relevant counts are zero. Compute score from weighted flags.

- [x] **Step 5: Run coverage tests**

Run: `python3 -m pytest tests/test_entity_coverage.py -q`

Expected: tests pass.

### Task 2: Wire Rebuild And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`

- [x] **Step 1: Add schema/report expectations**

Add `entity_coverage` to schema expectations and report count tables.

- [x] **Step 2: Wire rebuild script**

Import `rebuild_entity_coverage`, run it after target resolution, and include the count in `reports/derived_tables.json`.

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

Expected: `entity_coverage` equals the entity count.

- [x] **Step 2: Refresh inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: inspection report counts `entity_coverage`.

- [x] **Step 3: Document measured results**

Update README and progress docs with exact coverage counts and top missing dimensions.

- [ ] **Step 4: Verify, commit, and push**

Run:

```bash
python3 -m pytest -q
sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check"
git diff --check
```

Expected: all pass. Stage only this slice, commit as `data: summarize entity coverage`, and push `main`.
