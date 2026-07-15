from dst_wiki_db.build import (
    canonical_field_name,
    canonical_slug,
    extract_number,
    source_url,
    write_parsed_page,
)
from dst_wiki_db.mediawiki import MediaWikiClient
from dst_wiki_db.parser import parse_page
from dst_wiki_db.schema import connect, init_db, upsert_source


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
    session = FakeSession(
        [
            {
                "continue": {"apcontinue": "B", "continue": "-||"},
                "query": {"allpages": [{"title": "A"}]},
            },
            {"batchcomplete": "", "query": {"allpages": [{"title": "B"}]}},
        ]
    )
    client = MediaWikiClient(
        "test", "https://example.test/api.php", session=session, sleep_seconds=0
    )

    rows = list(client.query_all({"action": "query", "list": "allpages"}))

    assert rows == [{"title": "A"}, {"title": "B"}]
    assert session.calls[1][1]["apcontinue"] == "B"


def test_fetch_page_batch_requests_revisions_and_metadata():
    session = FakeSession(
        [
            {
                "query": {
                    "pages": [
                        {
                            "pageid": 1,
                            "ns": 0,
                            "title": "Wilson",
                            "revisions": [
                                {
                                    "revid": 10,
                                    "timestamp": "2026-07-01T00:00:00Z",
                                    "slots": {"main": {"content": "body"}},
                                }
                            ],
                            "categories": [{"title": "Category:Characters"}],
                        }
                    ]
                }
            }
        ]
    )
    client = MediaWikiClient(
        "test", "https://example.test/api.php", session=session, sleep_seconds=0
    )

    pages = client.fetch_page_batch(["Wilson"])

    assert pages[0]["title"] == "Wilson"
    assert pages[0]["revisions"][0]["slots"]["main"]["content"] == "body"
    assert session.calls[0][1]["titles"] == "Wilson"
    assert "revisions" in session.calls[0][1]["prop"]


def test_fetch_imageinfo_normalizes_file_titles():
    session = FakeSession(
        [
            {
                "query": {
                    "pages": [
                        {
                            "title": "File:Wilson.png",
                            "imageinfo": [
                                {
                                    "url": "https://example.test/Wilson.png",
                                    "descriptionurl": "https://example.test/wiki/File:Wilson.png",
                                    "width": 64,
                                    "height": 64,
                                    "mime": "image/png",
                                    "sha1": "abc",
                                }
                            ],
                        }
                    ]
                }
            }
        ]
    )
    client = MediaWikiClient(
        "test", "https://example.test/api.php", session=session, sleep_seconds=0
    )

    info = client.fetch_imageinfo(["Wilson.png"])

    assert info["File:Wilson.png"]["sha1"] == "abc"
    assert session.calls[0][1]["titles"] == "File:Wilson.png"


def test_canonical_slug_matches_titles_across_sources():
    assert canonical_slug("Wilson") == "wilson"
    assert canonical_slug("Don't Starve Together") == "dont-starve-together"
    assert canonical_slug("Maxwell/NPC") == "maxwell-npc"


def test_source_url_uses_mediawiki_article_path():
    assert (
        source_url("https://dontstarve.wiki.gg", "Maxwell/NPC")
        == "https://dontstarve.wiki.gg/wiki/Maxwell/NPC"
    )


def test_canonical_field_name_handles_dst_suffixes_and_camel_case():
    assert canonical_field_name("health dst") == "health"
    assert canonical_field_name("DSThealth") == "health"
    assert canonical_field_name("attackRange") == "attack_range"


def test_extract_number_reads_first_numeric_value():
    assert extract_number("150") == 150
    assert extract_number("6 tiles") == 6
    assert extract_number("-3.5 per minute") == -3.5
    assert extract_number("unknown") is None


def test_write_parsed_page_records_attributes_images_and_relations(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg/",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 18907, 0, 'Wilson', 568062, 'https://dontstarve.wiki.gg/wiki/Wilson', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    parsed = parse_page(
        "Wilson",
        """{{Character Infobox
|image dst=Wilson Original Portrait.png
|health dst=150
|attackRange=2
}}
'''Wilson''' is a playable [[character]].
[[Category:Characters]]
""",
    )

    entity_id = write_parsed_page(
        conn,
        source_id=source_id,
        raw_page_id=raw_page_id,
        source_title="Wilson",
        source_pageid=18907,
        source_revid=568062,
        source_timestamp="2026-07-01T00:00:00Z",
        page_url="https://dontstarve.wiki.gg/wiki/Wilson",
        parsed=parsed,
        primary=True,
    )

    entity = conn.execute("select slug, kind from entities where id=?", (entity_id,)).fetchone()
    attribute = conn.execute(
        "select canonical_name, value_number from entity_attributes where raw_name='health dst'"
    ).fetchone()
    image = conn.execute("select image_name, role, variant_key from entity_images").fetchone()
    relation = conn.execute("select relation_type, target_title from entity_relations").fetchone()

    assert tuple(entity) == ("wilson", "character")
    assert tuple(attribute) == ("health", 150)
    assert tuple(image) == ("Wilson Original Portrait.png", "image dst", "dst")
    assert tuple(relation) == ("wikilink", "character")
