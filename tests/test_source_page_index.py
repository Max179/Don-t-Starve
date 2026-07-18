from dst_wiki_db.alias_profiles import rebuild_entity_alias_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.source_page_index import (
    fetch_source_page_index,
    rebuild_source_page_entity_matches,
)


def test_fetch_source_page_index_matches_external_titles_with_aliases(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Berry Bush",
        kind="plant",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Berry_Bush",
        summary="",
    )
    conn.execute(
        """
        insert into entity_identity_keys (
            entity_id, source_id, key_type, key_value, source_field, confidence
        )
        values (?, ?, 'spawn_code', 'berrybush', 'spawnCode', 0.98)
        """,
        (entity_id, source_id),
    )
    rebuild_entity_alias_profiles(conn)

    result = fetch_source_page_index(
        conn,
        source_key="wiki.gg",
        limit=None,
        client=FakeWikiClient(
            [
                {"pageid": 10, "ns": 0, "title": "Berry Bush"},
                {"pageid": 11, "ns": 0, "title": "berrybush"},
                {"pageid": 12, "ns": 0, "title": "Berry Bush/DST"},
                {"pageid": 13, "ns": 0, "title": "Unmatched Thing"},
            ]
        ),
    )

    assert result == {
        "source_key": "wiki.gg",
        "source_page_index": 4,
        "source_page_entity_matches": 3,
    }
    rows = conn.execute(
        """
        select source_key, source_pageid, title, title_slug, page_url
        from source_page_index
        order by source_pageid
        """
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "source_key": "wiki.gg",
            "source_pageid": 10,
            "title": "Berry Bush",
            "title_slug": "berry-bush",
            "page_url": "https://dontstarve.wiki.gg/wiki/Berry_Bush",
        },
        {
            "source_key": "wiki.gg",
            "source_pageid": 11,
            "title": "berrybush",
            "title_slug": "berrybush",
            "page_url": "https://dontstarve.wiki.gg/wiki/berrybush",
        },
        {
            "source_key": "wiki.gg",
            "source_pageid": 12,
            "title": "Berry Bush/DST",
            "title_slug": "berry-bush-dst",
            "page_url": "https://dontstarve.wiki.gg/wiki/Berry_Bush/DST",
        },
        {
            "source_key": "wiki.gg",
            "source_pageid": 13,
            "title": "Unmatched Thing",
            "title_slug": "unmatched-thing",
            "page_url": "https://dontstarve.wiki.gg/wiki/Unmatched_Thing",
        },
    ]
    matches = conn.execute(
        """
        select source_title, entity_title, match_method, confidence
        from source_page_entity_matches
        order by source_pageid
        """
    ).fetchall()
    assert [tuple(row) for row in matches] == [
        ("Berry Bush", "Berry Bush", "alias:canonical_title", 1.0),
        ("berrybush", "Berry Bush", "alias:prefab_code", 0.98),
        ("Berry Bush/DST", "Berry Bush", "alias_game_variant_suffix:canonical_title", 0.88),
    ]


def test_rebuild_source_page_entity_matches_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Wilson",
        summary="",
    )
    rebuild_entity_alias_profiles(conn)
    conn.execute(
        """
        insert into source_page_index (
            source_id, source_key, source_pageid, ns, title, title_slug,
            page_url, index_status
        )
        values (?, 'wiki.gg', 10, 0, 'Wilson', 'wilson',
                'https://dontstarve.wiki.gg/wiki/Wilson', 'listed')
        """,
        (source_id,),
    )

    first = rebuild_source_page_entity_matches(conn)
    second = rebuild_source_page_entity_matches(conn)

    assert first == second == 1
    row = conn.execute(
        "select source_title, entity_id from source_page_entity_matches"
    ).fetchone()
    assert tuple(row) == ("Wilson", entity_id)


class FakeWikiClient:
    def __init__(self, pages):
        self.pages = list(pages)

    def fetch_siteinfo(self):
        return {
            "query": {
                "statistics": {"articles": len(self.pages)},
                "general": {"sitename": "Don't Starve Wiki"},
            }
        }

    def iter_main_pages(self, limit=None):
        pages = self.pages if limit is None else self.pages[:limit]
        yield from pages
