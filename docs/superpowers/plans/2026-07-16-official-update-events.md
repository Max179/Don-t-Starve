# Official Update Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize official Steam news records into queryable update/event rows with dates, authors, app ids, event types, media URLs, and entity mention counts.

**Architecture:** Keep `official_records` as source evidence, then derive one `official_update_events` row per successful Steam news record and zero or more `official_update_media` rows from Steam clan image placeholders and HTML image tags. Use `official_record_id` as the evidence key so events can join to existing `official_record_mentions`.

**Tech Stack:** Python 3.9+, SQLite, `json`, `html.parser`, `datetime`, `pytest`.

---

## File Structure

- Create `dst_wiki_db/official_updates.py` for event and media derivation.
- Create `tests/test_official_updates.py` for Steam news extraction behavior.
- Modify `dst_wiki_db/schema.py` to add `official_update_events` and `official_update_media`.
- Modify `scripts/rebuild_derived_tables.py` to rebuild the new tables.
- Modify `dst_wiki_db/report.py` so inspection reports count both tables.
- Modify `tests/test_schema.py` to expect the new tables.
- Modify `README.md` and `docs/progress.md` after refreshing the committed database.
- Regenerate `reports/derived_tables.json`, `reports/inspect.json`, and `data/dont_starve_wiki.sqlite`.

### Task 1: Schema And Update Extraction

**Files:**
- Create: `tests/test_official_updates.py`
- Create: `dst_wiki_db/official_updates.py`
- Modify: `dst_wiki_db/schema.py`

- [x] **Step 1: Write failing update-event tests**

```python
def test_rebuild_official_update_events_extracts_event_and_media(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    record_id = upsert_official_record(conn, OfficialRecord(
        provider="steam",
        record_type="news",
        external_id="hotfix-1",
        title="Hotfix 740477",
        url="https://example.test/news",
        status="ok",
        summary="Changes and bug fixes.",
        payload={
            "appid": 322330,
            "author": "JesseB_Klei",
            "date": 1700000000,
            "contents": "Bug Fixes {STEAM_CLAN_IMAGE}/6835324/abc.png <img src=\"https://cdn.test/extra.jpg\" width=\"100\" height=\"50\"> Wilson fixed.",
        },
    ))
    source_id = upsert_source(conn, key="fandom", name="Fandom", base_url="https://dontstarve.fandom.com", api_url="https://dontstarve.fandom.com/api.php", role="comparison")
    entity_id = upsert_entity(conn, canonical_title="Wilson", kind="character", primary_source_id=source_id, primary_page_id=1, canonical_url="https://dontstarve.fandom.com/wiki/Wilson", summary="")
    conn.execute(
        """
        insert into official_record_mentions (
            official_record_id, entity_id, provider, record_type, external_id,
            entity_title, mention_text, match_field, match_method,
            confidence, context_text
        )
        values (?, ?, 'steam', 'news', 'hotfix-1', 'Wilson', 'Wilson',
                'payload', 'canonical_title_phrase', 0.95, 'Wilson fixed.')
        """,
        (record_id, entity_id),
    )

    result = rebuild_official_update_events(conn)

    assert result == {"official_update_events": 1, "official_update_media": 2}
```

- [x] **Step 2: Run focused test and verify RED**

Run: `python3 -m pytest tests/test_official_updates.py::test_rebuild_official_update_events_extracts_event_and_media -q`

Expected: fail because `dst_wiki_db.official_updates` does not exist.

- [x] **Step 3: Add schema tables**

Add `official_update_events` with event metadata, normalized content text, content length, and `mentioned_entity_count`. Add `official_update_media` with event/record ids, media role, media index, media URL, width, height, and source field.

- [x] **Step 4: Implement `rebuild_official_update_events`**

Read successful Steam news records, parse JSON payloads, convert Unix dates to UTC ISO strings, classify titles into `hotfix`, `event`, `milestone`, `update`, or `announcement`, count existing mention rows, extract Steam clan image placeholders into `https://clan.cloudflare.steamstatic.com/images/...` URLs, parse HTML `<img>` tags, and insert derived rows idempotently.

- [x] **Step 5: Run update tests**

Run: `python3 -m pytest tests/test_official_updates.py -q`

Expected: tests pass.

### Task 2: Wire Rebuild And Reports

**Files:**
- Modify: `scripts/rebuild_derived_tables.py`
- Modify: `dst_wiki_db/report.py`
- Modify: `tests/test_schema.py`

- [x] **Step 1: Add table expectations**

Add `official_update_events` and `official_update_media` to schema and report table lists.

- [x] **Step 2: Wire rebuild script**

Import `rebuild_official_update_events`, run it after `rebuild_official_record_mentions`, and include `official_update_events` plus `official_update_media` in `reports/derived_tables.json`.

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

Expected: `official_update_events` is 50 and `official_update_media` reflects Steam news image references.

- [x] **Step 2: Refresh inspection report**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite > reports/inspect.json`

Expected: `reports/inspect.json` includes both new official update tables.

- [x] **Step 3: Document measured results**

Update README and progress docs with exact event/media counts, type distribution, and examples such as `Hotfix 740477`, `Midsummer Cawnival is Back!`, and `From Beyond - Cursed Confrontation`.

- [ ] **Step 4: Verify, commit, and push**

Run:

```bash
python3 -m pytest -q
sqlite3 data/dont_starve_wiki.sqlite "pragma integrity_check"
git diff --check
```

Expected: all pass. Stage only this slice, commit as `data: normalize official update events`, and push `main`.
