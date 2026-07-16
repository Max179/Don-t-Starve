# Official Product Facts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize official Steam product records into queryable product fact and media tables so games, DLC, soundtracks, parent products, descriptions, and official image URLs are searchable without parsing JSON.

**Architecture:** Keep `official_records` as immutable source evidence, then rebuild two derived tables from successful Steam `appdetails` and `dlc_appdetails` records. `official_products` stores one row per official product record, while `official_product_media` stores direct Steam media fields plus image URLs found in Steam HTML description fields.

**Tech Stack:** Python 3.9+, SQLite, `json`, `html.parser`, `pytest`.

---

## File Structure

- Create `dst_wiki_db/official_products.py` for official product/media derivation.
- Create `tests/test_official_products.py` for product fact/media extraction behavior.
- Modify `dst_wiki_db/schema.py` to add `official_products` and `official_product_media`.
- Modify `scripts/rebuild_derived_tables.py` to rebuild the new tables.
- Modify `dst_wiki_db/report.py` so inspection reports count both tables.
- Modify `README.md` and `docs/progress.md` after refreshing the committed database.
- Regenerate `reports/derived_tables.json`, `reports/inspect.json`, and `data/dont_starve_wiki.sqlite`.

### Task 1: Schema And Product Extraction

**Files:**
- Create: `tests/test_official_products.py`
- Create: `dst_wiki_db/official_products.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write the failing product/media test**

```python
from dst_wiki_db.official import OfficialRecord
from dst_wiki_db.official_products import rebuild_official_products
from dst_wiki_db.schema import connect, init_db, upsert_official_record


def test_rebuild_official_products_extracts_product_facts_and_media(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    upsert_official_record(conn, OfficialRecord(
        provider="steam",
        record_type="dlc_appdetails",
        external_id="4211520",
        title="Don't Starve Together: Starter Pack 2026",
        url="https://store.steampowered.com/app/4211520/",
        status="ok",
        summary="Starter pack.",
        payload={
            "parent_appid": 322330,
            "data": {
                "type": "dlc",
                "name": "Don't Starve Together: Starter Pack 2026",
                "steam_appid": 4211520,
                "short_description": "Starter pack.",
                "fullgame": {"appid": "322330", "name": "Don't Starve Together"},
                "header_image": "https://cdn.test/header.jpg",
                "capsule_image": "https://cdn.test/capsule.jpg",
                "detailed_description": "<img src=\"https://cdn.test/extra.avif\" width=491 height=654>",
            },
        },
    ))

    result = rebuild_official_products(conn)

    assert result == {"official_products": 1, "official_product_media": 3}
```

- [x] **Step 2: Run the focused test and verify RED**

Run: `python3 -m pytest tests/test_official_products.py::test_rebuild_official_products_extracts_product_facts_and_media -q`

Expected: fail because `dst_wiki_db.official_products` does not exist.

- [x] **Step 3: Add schema tables**

Add `official_products` with fields for source record id, provider, record type, external id, product type, title, URL, parent id/title, short description, release date text, free flag, required age, controller support, website, supported languages, and a unique key on `official_record_id`. Add `official_product_media` with product/record ids, role, URL, optional width/height, and a unique key on `official_record_id, media_role, media_index, media_url`.

- [x] **Step 4: Implement `rebuild_official_products`**

Read successful Steam `appdetails` and `dlc_appdetails` records, unwrap DLC payloads, insert one product row per record, add media rows for `header_image`, `capsule_image`, `capsule_imagev5`, `background`, and `background_raw`, then parse `detailed_description` and `about_the_game` HTML for image `src`, `width`, and `height`.

- [x] **Step 5: Run product tests**

Run: `python3 -m pytest tests/test_official_products.py -q`

Expected: product facts and media tests pass.

### Task 2: Wire Rebuild And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`

- [x] **Step 1: Write schema/report expectations**

Add `official_products` and `official_product_media` to schema table expectations and report counts.

- [x] **Step 2: Run schema tests and verify RED where needed**

Run: `python3 -m pytest tests/test_schema.py -q`

Expected: pass once schema is present; fail before schema is added.

- [x] **Step 3: Wire rebuild script**

Import `rebuild_official_products`, run it after official mentions, and write `official_products` plus `official_product_media` counts into `reports/derived_tables.json`.

- [x] **Step 4: Run full tests**

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

Expected: `official_products` is 55 and `official_product_media` is greater than the 110 direct header/capsule URLs because description images are also extracted.

- [x] **Step 2: Refresh inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: `reports/inspect.json` includes both new official tables.

- [x] **Step 3: Document measured results**

Update README and progress docs with exact table counts and a few examples such as `Don't Starve Together`, `Don't Starve Together: Starter Pack 2026`, and `Don't Starve Soundtrack`.

- [ ] **Step 4: Verify, commit, and push**

Run:

```bash
python3 -m pytest -q
sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check"
git diff --check
```

Expected: all pass. Stage only this slice, commit as `data: normalize official product facts`, and push `main`.
