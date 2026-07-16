# Entity Media Assets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified per-entity media asset table that makes infobox images, page-level image references, and filename-derived image variants queryable from one place.

**Architecture:** Keep `entity_images`, `page_images`, and `image_variants` as source-specific normalized tables. Add derived `entity_media_assets` rows for infobox and page-reference images, preserving image URLs/file pages, local paths, variant labels/types, confidence, and source row ids.

**Tech Stack:** Python 3.9+, SQLite, `pytest`.

---

## File Structure

- Create `dst_wiki_db/media_assets.py` for rebuilding unified media rows.
- Create `tests/test_media_assets.py` for infobox/page/variant media behavior.
- Modify `dst_wiki_db/schema.py` to add `entity_media_assets`.
- Modify `scripts/rebuild_derived_tables.py` to rebuild media assets after `image_variants`.
- Modify `dst_wiki_db/report.py` and `tests/test_schema.py` to count/expect the table.
- Modify `README.md` and `docs/progress.md` with measured media asset results.
- Regenerate `reports/derived_tables.json`, `reports/inspect.json`, and `data/dont_starve_wiki.sqlite`.

### Task 1: Schema And Media Builder

**Files:**
- Create: `tests/test_media_assets.py`
- Create: `dst_wiki_db/media_assets.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write failing media asset tests**

```python
from dst_wiki_db.media_assets import rebuild_entity_media_assets


def test_rebuild_entity_media_assets_unifies_infobox_page_and_variant_images(tmp_path):
    ...
```

- [x] **Step 2: Run focused test and verify RED**

Run: `python3 -m pytest tests/test_media_assets.py::test_rebuild_entity_media_assets_unifies_infobox_page_and_variant_images -q`

Expected: fail because `dst_wiki_db.media_assets` does not exist.

- [x] **Step 3: Add `entity_media_assets` schema**

Add fields for entity/source/raw page ids, asset source, source row ids, image name/slug, role, URLs, local path, width/height/mime/sha1, variant key/type/label/confidence, `is_variant`, `is_primary`, and a uniqueness key.

- [x] **Step 4: Implement `rebuild_entity_media_assets`**

Insert infobox rows from `entity_images` and page-reference rows from `page_images`, left joining `image_variants` for variant metadata. Mark infobox `role in ('image', 'inventoryImage')` as primary and page rows with variant metadata as `is_variant=1`.

- [x] **Step 5: Run media asset tests**

Run: `python3 -m pytest tests/test_media_assets.py -q`

Expected: tests pass.

### Task 2: Wire Rebuild And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`

- [x] **Step 1: Add schema/report expectations**

Add `entity_media_assets` to schema expectations and report count tables.

- [x] **Step 2: Wire rebuild script**

Import `rebuild_entity_media_assets`, run it after `rebuild_image_variants`, and include the count in `reports/derived_tables.json`.

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

Expected: `entity_media_assets` equals infobox image rows plus page image rows.

- [x] **Step 2: Refresh inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: inspection report counts `entity_media_assets`.

- [x] **Step 3: Document measured results**

Update README and progress docs with total media assets, infobox/page split, variant asset count, and examples.

- [ ] **Step 4: Verify, commit, and push**

Run:

```bash
python3 -m pytest -q
sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check"
git diff --check
```

Expected: all pass. Stage only this slice, commit as `data: unify entity media assets`, and push `main`.
