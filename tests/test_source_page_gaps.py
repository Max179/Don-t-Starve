from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.source_page_gaps import rebuild_source_page_gaps


def test_rebuild_source_page_gaps_classifies_unmatched_source_pages(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Axe",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Axe",
        summary="",
    )
    _index(conn, source_id, 10, "Axe", "axe")
    _index(conn, source_id, 11, "Badland/DST", "badland-dst")
    _index(conn, source_id, 12, "Animation Cancelling", "animation-cancelling")
    _index(conn, source_id, 13, "Beefalo Skins", "beefalo-skins")
    _index(conn, source_id, 14, "Guides/Mob Killing Guide", "guides-mob-killing-guide")
    conn.execute(
        """
        insert into source_page_entity_matches (
            source_page_index_id, source_key, source_pageid, source_title,
            source_title_slug, entity_id, entity_slug, entity_title,
            entity_kind, match_method, confidence
        )
        select id, source_key, source_pageid, title, title_slug,
               ?, 'axe', 'Axe', 'item', 'alias:canonical_title', 1.0
        from source_page_index
        where source_pageid = 10
        """,
        (entity_id,),
    )

    result = rebuild_source_page_gaps(conn, source_key="wiki.gg")

    assert result == 4
    rows = conn.execute(
        """
        select title, gap_type, priority, suggested_title, suggested_slug
        from source_page_gaps
        order by priority, title
        """
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        (
            "Animation Cancelling",
            "potential_new_entity",
            10,
            "",
            "",
        ),
        (
            "Badland/DST",
            "unmatched_game_variant_page",
            20,
            "Badland",
            "badland",
        ),
        (
            "Beefalo Skins",
            "cosmetic_or_curio_page",
            60,
            "",
            "",
        ),
        (
            "Guides/Mob Killing Guide",
            "guide_or_reference_page",
            70,
            "",
            "",
        ),
    ]


def test_rebuild_source_page_gaps_is_idempotent_without_index(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    assert rebuild_source_page_gaps(conn) == 0
    assert rebuild_source_page_gaps(conn) == 0


def _index(conn, source_id, pageid, title, slug):
    conn.execute(
        """
        insert into source_page_index (
            source_id, source_key, source_pageid, ns, title, title_slug,
            page_url, index_status
        )
        values (?, 'wiki.gg', ?, 0, ?, ?,
                'https://dontstarve.wiki.gg/wiki/' || replace(?, ' ', '_'),
                'listed')
        """,
        (source_id, pageid, title, slug, title),
    )
