# Source Catalog Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store ranked Don't Starve data-source candidates and their verification evidence in SQLite, so the project can query which wiki/official/competitor sources are authoritative, usable, restricted, or secondary.

**Architecture:** Keep `sources` and `source_audits` as low-level source/access records. Add derived `source_catalog` rows for ranked strategic sources and `source_catalog_evidence` rows for search, official, audit, and community evidence. Rebuild deterministically from a curated source list plus existing audit/source rows.

**Tech Stack:** Python 3.9+, SQLite, `pytest`.

---

## File Structure

- Create `dst_wiki_db/source_catalog.py` for ranked source catalog derivation.
- Create `tests/test_source_catalog.py` for catalog and evidence behavior.
- Modify `dst_wiki_db/schema.py` to add `source_catalog` and `source_catalog_evidence`.
- Modify `scripts/rebuild_derived_tables.py` to rebuild the new tables.
- Modify `dst_wiki_db/report.py` and `tests/test_schema.py` to count/expect both tables.
- Modify `README.md`, `docs/progress.md`, and `docs/sources.md` with measured source catalog results.
- Regenerate `reports/derived_tables.json`, `reports/inspect.json`, and `data/dont_starve_wiki.sqlite`.

### Task 1: Schema And Catalog Builder

**Files:**
- Create: `tests/test_source_catalog.py`
- Create: `dst_wiki_db/source_catalog.py`
- Modify: `dst_wiki_db/schema.py`

- [ ] **Step 1: Write failing catalog tests**

```python
from dst_wiki_db.schema import connect, init_db, upsert_source
from dst_wiki_db.source_catalog import rebuild_source_catalog


def test_rebuild_source_catalog_records_ranked_sources_and_evidence(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    upsert_source(conn, key="wiki.gg", name="Don't Starve Wiki", base_url="https://dontstarve.wiki.gg", api_url="https://dontstarve.wiki.gg/api.php", role="canonical")
    upsert_source(conn, key="fandom", name="Don't Starve Wiki on Fandom", base_url="https://dontstarve.fandom.com", api_url="https://dontstarve.fandom.com/api.php", role="comparison")

    result = rebuild_source_catalog(conn)

    assert result == {"source_catalog": 8, "source_catalog_evidence": 17}
```

- [ ] **Step 2: Run focused test and verify RED**

Run: `python3 -m pytest tests/test_source_catalog.py::test_rebuild_source_catalog_records_ranked_sources_and_evidence -q`

Expected: fail because `dst_wiki_db.source_catalog` does not exist.

- [ ] **Step 3: Add schema tables**

Add `source_catalog` with source key, optional `source_id`, rank, tier, source type, role, URLs, access method, ingestion status, license summary, coverage summary, verification use, notes, and last verified date. Add `source_catalog_evidence` with source key, evidence type, URL, title, summary, provider, and checked date.

- [ ] **Step 4: Implement `rebuild_source_catalog`**

Populate ranked rows for wiki.gg, Klei, Steam, Fandom, Fextralife, Wikipedia, Reddit migration/community signal, and PatchBot/community patch tracking. Preserve source ids when matching rows exist in `sources`. Insert evidence rows for search results, official probes, siteinfo/audit records, and manual ranking rationale.

- [ ] **Step 5: Run catalog tests**

Run: `python3 -m pytest tests/test_source_catalog.py -q`

Expected: tests pass.

### Task 2: Wire Rebuild And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`

- [ ] **Step 1: Add report/schema expectations**

Add `source_catalog` and `source_catalog_evidence` to schema expectations and report count tables.

- [ ] **Step 2: Wire rebuild script**

Import `rebuild_source_catalog`, run it after source/audit-dependent derived tables, and include both counts in `reports/derived_tables.json`.

- [ ] **Step 3: Run full tests**

Run: `python3 -m pytest -q`

Expected: all tests pass.

### Task 3: Refresh Data And Publish

**Files:**
- Modify: `data/dont_starve_wiki.sqlite`
- Modify: `reports/derived_tables.json`
- Modify: `reports/inspect.json`
- Modify: `README.md`
- Modify: `docs/progress.md`
- Modify: `docs/sources.md`

- [ ] **Step 1: Rebuild derived tables**

Run:

```bash
python3 scripts/rebuild_derived_tables.py \
  --db data/dont_starve_wiki.sqlite \
  --report reports/derived_tables.json
```

Expected: `source_catalog` is 8 and `source_catalog_evidence` is 17 or more.

- [ ] **Step 2: Refresh inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: inspection report counts both new source catalog tables.

- [ ] **Step 3: Document measured results**

Update README/progress/sources docs with source catalog counts and ranked source examples.

- [ ] **Step 4: Verify, commit, and push**

Run:

```bash
python3 -m pytest -q
sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check"
git diff --check
```

Expected: all pass. Stage only this slice, commit as `data: catalog ranked sources`, and push `main`.
