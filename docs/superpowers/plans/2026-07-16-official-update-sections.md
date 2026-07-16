# Official Update Sections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split normalized official Steam update events into queryable sections and item rows, so official Changes, Bug Fixes, Highlights, and similar patch-note content can be searched without scanning long text blobs.

**Architecture:** Keep `official_update_events` as the event-level record and derive `official_update_sections` plus `official_update_section_items` from its cleaned `content_text`. Section parsing uses a conservative heading vocabulary and preserves source order; item parsing splits section bodies into sentence-like entries while keeping source text intact.

**Tech Stack:** Python 3.9+, SQLite, `re`, `pytest`.

---

## File Structure

- Create `dst_wiki_db/official_update_sections.py` for section and item derivation.
- Create `tests/test_official_update_sections.py` for heading and item extraction behavior.
- Modify `dst_wiki_db/schema.py` to add `official_update_sections` and `official_update_section_items`.
- Modify `scripts/rebuild_derived_tables.py` to rebuild the new tables after update events.
- Modify `dst_wiki_db/report.py` so inspection reports count both tables.
- Modify `tests/test_schema.py` to expect the new tables.
- Modify `README.md` and `docs/progress.md` after refreshing the committed database.
- Regenerate `reports/derived_tables.json`, `reports/inspect.json`, and `data/dont_starve_wiki.sqlite`.

### Task 1: Schema And Parser

**Files:**
- Create: `tests/test_official_update_sections.py`
- Create: `dst_wiki_db/official_update_sections.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write failing section/item tests**

```python
from dst_wiki_db.official_update_sections import rebuild_official_update_sections
from dst_wiki_db.schema import connect, init_db


def test_rebuild_official_update_sections_extracts_headings_and_items(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    conn.execute(
        """
        insert into official_records (
            provider, record_type, external_id, title, url, status, summary, payload_json
        )
        values ('steam', 'news', 'hotfix-1', 'Hotfix 740477',
                'https://example.test/news', 'ok', '', '{}')
        """
    )
    record_id = conn.execute("select id from official_records").fetchone()[0]
    conn.execute(
        """
        insert into official_update_events (
            official_record_id, provider, record_type, external_id, appid,
            title, url, author, published_at_unix, published_at_iso,
            event_type, summary, content_text, content_length, mentioned_entity_count
        )
        values (?, 'steam', 'news', 'hotfix-1', 322330, 'Hotfix 740477',
                'https://example.test/news', 'KleiFish', 1700000000,
                '2023-11-14T22:13:20Z', 'hotfix', '',
                'Changes Added Coals. Added Thermal Balm. Bug Fixes Fixed Beefalo duplication. Fixed crashes.',
                96, 2)
        """,
        (record_id,),
    )

    result = rebuild_official_update_sections(conn)

    assert result == {
        "official_update_sections": 2,
        "official_update_section_items": 4,
    }
```

- [x] **Step 2: Run focused test and verify RED**

Run: `python3 -m pytest tests/test_official_update_sections.py::test_rebuild_official_update_sections_extracts_headings_and_items -q`

Expected: fail because `dst_wiki_db.official_update_sections` does not exist.

- [x] **Step 3: Add schema tables**

Add `official_update_sections` with event/record ids, provider, external id, section index, heading text, section type, body text, and item count. Add `official_update_section_items` with section/event/record ids, item index, item text, and character length.

- [x] **Step 4: Implement `rebuild_official_update_sections`**

Read `official_update_events`, split text on known headings such as `Highlights`, `Highlights Include`, `Other Additions`, `Changes`, `Bug Fixes`, `New Skins`, and `Login Rewards`, insert ordered section rows, split each body into sentence-like items, and store counts. If no heading is found, store the whole content as one `body` section.

- [x] **Step 5: Run section tests**

Run: `python3 -m pytest tests/test_official_update_sections.py -q`

Expected: tests pass.

### Task 2: Rebuild Wiring And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`

- [x] **Step 1: Add table expectations**

Add `official_update_sections` and `official_update_section_items` to schema and report table lists.

- [x] **Step 2: Wire rebuild script**

Import `rebuild_official_update_sections`, run it after `rebuild_official_update_events`, and include both counts in `reports/derived_tables.json`.

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

Expected: `official_update_sections` and `official_update_section_items` are populated from the 50 update events.

- [x] **Step 2: Refresh inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: `reports/inspect.json` includes both new official update section tables.

- [x] **Step 3: Document measured results**

Update README and progress docs with exact section/item counts, section type distribution, and examples from Hotfix and From Beyond update events.

- [ ] **Step 4: Verify, commit, and push**

Run:

```bash
python3 -m pytest -q
sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check"
git diff --check
```

Expected: all pass. Stage only this slice, commit as `data: parse official update sections`, and push `main`.
