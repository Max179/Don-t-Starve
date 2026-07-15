# Don't Starve Wiki Database Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a repeatable SQLite data pipeline that collects English-first Don't Starve / Don't Starve Together wiki entries, images, variants, raw evidence, structured attributes, and cross-source verification metadata.

**Architecture:** Use MediaWiki APIs as the primary ingestion layer, keeping raw page wikitext alongside parsed entities so the database remains auditable. Treat `dontstarve.wiki.gg` as the canonical source by default, ingest `dontstarve.fandom.com` as a comparison source, and register Klei pages/forums as official verification sources.

**Tech Stack:** Python 3.9+, SQLite, `requests`, `mwparserfromhell`, `pytest`.

---

## File Structure

- Create `requirements.txt` for runtime/test dependencies.
- Create `dst_wiki_db/mediawiki.py` for polite MediaWiki API requests, continuation handling, page fetching, parse metadata, image metadata, and downloads.
- Create `dst_wiki_db/parser.py` for wikitext parsing: infobox templates, attributes, image fields, categories, links, and display summaries.
- Create `dst_wiki_db/schema.py` for SQLite schema creation and idempotent upserts.
- Create `dst_wiki_db/build.py` for source orchestration, entity mapping, parsing, image registration, and verification row creation.
- Create `scripts/build_database.py` as the CLI entrypoint.
- Create `scripts/inspect_database.py` for quick counts and sample rows.
- Create `tests/test_parser.py`, `tests/test_schema.py`, and `tests/test_build.py`.
- Create `README.md` and `docs/sources.md` documenting source choice, coverage, and rerun commands.

## Task 1: Parser Behavior

**Files:**
- Create: `tests/test_parser.py`
- Create: `dst_wiki_db/parser.py`
- Create: `dst_wiki_db/__init__.py`

- [ ] **Step 1: Write failing parser tests**

```python
from dst_wiki_db.parser import parse_page


def test_parse_page_extracts_infobox_fields_and_images():
    text = """{{Character Infobox
|image ds=Wilson.png
|image dst=Wilson Original Portrait.png
|health ds=150
|hunger dst=150
|spawnCode dst="wilson"
}}
'''Wilson Percival Higgsbury''' is a playable [[character]].
[[Category:Characters]]
"""

    parsed = parse_page("Wilson", text)

    assert parsed.kind == "character"
    assert parsed.summary.startswith("Wilson Percival Higgsbury")
    assert parsed.infoboxes[0].name == "Character Infobox"
    assert parsed.attributes["health ds"] == "150"
    assert parsed.attributes["spawnCode dst"] == '"wilson"'
    assert [image.name for image in parsed.images] == [
        "Wilson.png",
        "Wilson Original Portrait.png",
    ]
    assert parsed.images[0].role == "image ds"
    assert parsed.categories == ["Characters"]
    assert parsed.links == ["character"]


def test_parse_page_classifies_boss_from_category():
    text = """{{Mob Infobox
|image=Deerclops.png
|health=2000
|damage=75
|attack period=3
}}
'''Deerclops''' is a giant.
[[Category:Bosses]]
[[Category:Mobs]]
"""

    parsed = parse_page("Deerclops", text)

    assert parsed.kind == "boss"
    assert parsed.attributes["damage"] == "75"
    assert parsed.categories == ["Bosses", "Mobs"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_parser.py -q`
Expected: failure because `dst_wiki_db.parser` does not exist.

- [ ] **Step 3: Implement parser**

Create dataclasses `ParsedImage`, `ParsedInfobox`, and `ParsedPage`. Use `mwparserfromhell` to extract top-level templates whose name contains `Infobox`, normalize parameter names without lowercasing, collect values as strings, classify kind from infobox/category keywords, collect image fields whose parameter name contains `image`, collect categories, collect wiki links, and generate a short plain-text summary from the first bold/plain sentence.

- [ ] **Step 4: Run parser tests**

Run: `pytest tests/test_parser.py -q`
Expected: 2 passed.

## Task 2: SQLite Schema

**Files:**
- Create: `tests/test_schema.py`
- Create: `dst_wiki_db/schema.py`

- [ ] **Step 1: Write failing schema tests**

```python
import sqlite3

from dst_wiki_db.schema import connect, init_db, upsert_source, upsert_entity


def test_schema_can_upsert_sources_and_entities(tmp_path):
    db_path = tmp_path / "wiki.sqlite"
    conn = connect(db_path)
    init_db(conn)

    source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg/",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    page_id = upsert_entity(
        conn,
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=18907,
        canonical_url="https://dontstarve.wiki.gg/wiki/Wilson",
        summary="Wilson is playable.",
    )

    row = conn.execute("select canonical_title, kind from entities where id=?", (page_id,)).fetchone()
    assert tuple(row) == ("Wilson", "character")


def test_schema_has_auditable_raw_tables(tmp_path):
    conn = sqlite3.connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    tables = {
        row[0]
        for row in conn.execute("select name from sqlite_master where type='table'")
    }

    assert {
        "sources",
        "raw_pages",
        "entities",
        "entity_sources",
        "entity_attributes",
        "entity_images",
        "entity_relations",
        "verification_checks",
        "run_metadata",
    }.issubset(tables)
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_schema.py -q`
Expected: failure because `dst_wiki_db.schema` does not exist.

- [ ] **Step 3: Implement schema**

Create tables with stable primary keys, `unique` constraints for idempotent reruns, JSON text columns for raw API payloads, and helper functions `connect`, `init_db`, `upsert_source`, and `upsert_entity`.

- [ ] **Step 4: Run schema tests**

Run: `pytest tests/test_schema.py -q`
Expected: 2 passed.

## Task 3: MediaWiki Client

**Files:**
- Create: `tests/test_build.py`
- Create: `dst_wiki_db/mediawiki.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Write failing API-client unit tests with fake sessions**

```python
from dst_wiki_db.mediawiki import MediaWikiClient


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payloads.pop(0))


def test_query_all_follows_continue():
    session = FakeSession([
        {"continue": {"apcontinue": "B", "continue": "-||"}, "query": {"allpages": [{"title": "A"}]}},
        {"batchcomplete": "", "query": {"allpages": [{"title": "B"}]}},
    ])
    client = MediaWikiClient("test", "https://example.test/api.php", session=session, sleep_seconds=0)

    rows = list(client.query_all({"action": "query", "list": "allpages"}))

    assert rows == [{"title": "A"}, {"title": "B"}]
    assert session.calls[1][1]["apcontinue"] == "B"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_build.py -q`
Expected: failure because `dst_wiki_db.mediawiki` does not exist.

- [ ] **Step 3: Implement MediaWikiClient**

Implement `query`, `query_all`, `fetch_siteinfo`, `iter_main_pages`, `fetch_page_batch`, `fetch_parse_metadata`, `fetch_imageinfo`, and `download_url`. Include a descriptive User-Agent and a configurable delay.

- [ ] **Step 4: Run API-client tests**

Run: `pytest tests/test_build.py -q`
Expected: 1 passed.

## Task 4: Build Pipeline

**Files:**
- Modify: `tests/test_build.py`
- Create: `dst_wiki_db/build.py`
- Create: `scripts/build_database.py`
- Create: `scripts/inspect_database.py`

- [ ] **Step 1: Write failing orchestration test**

```python
from dst_wiki_db.build import canonical_slug, source_url


def test_canonical_slug_matches_titles_across_sources():
    assert canonical_slug("Wilson") == "wilson"
    assert canonical_slug("Don't Starve Together") == "dont-starve-together"
    assert canonical_slug("Maxwell/NPC") == "maxwell-npc"


def test_source_url_uses_mediawiki_article_path():
    assert source_url("https://dontstarve.wiki.gg", "Maxwell/NPC") == "https://dontstarve.wiki.gg/wiki/Maxwell/NPC"
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `pytest tests/test_build.py -q`
Expected: failure because `dst_wiki_db.build` does not exist.

- [ ] **Step 3: Implement build orchestration**

Implement a CLI pipeline that initializes the database, registers source definitions, fetches pages from selected sources, saves raw pages, parses infoboxes, upserts entities by canonical slug, stores attributes/images/relations, fetches image metadata, optionally downloads primary/all images, and records verification checks for cross-source title matches.

- [ ] **Step 4: Run orchestration tests**

Run: `pytest tests/test_build.py -q`
Expected: all tests pass.

## Task 5: Full Data Run and Documentation

**Files:**
- Create: `README.md`
- Create: `docs/sources.md`
- Database output: `data/dont_starve_wiki.sqlite`
- Image output: `data/images/`
- Report output: `reports/coverage.json`

- [ ] **Step 1: Install dependencies**

Run: `python3 -m pip install -r requirements.txt`
Expected: `requests`, `mwparserfromhell`, and `pytest` installed.

- [ ] **Step 2: Build canonical database**

Run: `python3 scripts/build_database.py --db data/dont_starve_wiki.sqlite --sources wiki.gg fandom --download-images primary --image-dir data/images --coverage reports/coverage.json`
Expected: SQLite database with sources, raw pages, entities, attributes, image registrations, and verification rows.

- [ ] **Step 3: Inspect database**

Run: `python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite`
Expected: counts for sources, raw pages, entities, attributes, images, relations, and verification checks plus sample records.

- [ ] **Step 4: Run tests**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 5: Document results**

Document the selected source ranking, exact rerun command, table meanings, known limitations, and the difference between downloaded primary image files and all registered image URLs.

## Self-Review

- Spec coverage: The plan covers source discovery, English-first wiki entries, image registration and download, variants via infobox image roles and relation rows, structured stats via infobox attributes, raw evidence preservation, and cross-source verification.
- Placeholder scan: No task uses `TBD`, `TODO`, or unspecified follow-up work as an implementation step.
- Type consistency: The parser returns `ParsedPage`; schema helpers accept stable scalar values; build orchestration consumes parser dataclasses and writes schema tables.
