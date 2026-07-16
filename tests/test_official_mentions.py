import json

from dst_wiki_db.official_mentions import rebuild_official_record_mentions
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_official_record_mentions_links_official_text_to_entities(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    wormwood_id = upsert_entity(
        conn,
        canonical_title="Wormwood",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=10,
        canonical_url="https://dontstarve.fandom.com/wiki/Wormwood",
        summary="A character.",
    )
    winona_id = upsert_entity(
        conn,
        canonical_title="Winona",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=11,
        canonical_url="https://dontstarve.fandom.com/wiki/Winona",
        summary="A character.",
    )
    dst_id = upsert_entity(
        conn,
        canonical_title="Don't Starve Together",
        kind="page",
        primary_source_id=source_id,
        primary_page_id=12,
        canonical_url="https://dontstarve.fandom.com/wiki/Don%27t_Starve_Together",
        summary="The multiplayer game.",
    )
    upsert_entity(
        conn,
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=13,
        canonical_url="https://dontstarve.fandom.com/wiki/Bee",
        summary="A mob.",
    )
    conn.execute(
        """
        insert into official_records (
            provider, record_type, external_id, title, url, status, summary, payload_json
        )
        values (
            'steam',
            'news',
            '1000',
            'Winona and Wormwood update',
            'https://store.steampowered.com/news/app/322330/view/1000',
            'ok',
            'The latest Don''t Starve Together update expands Winona and Wormwood.',
            ?
        )
        """,
        (json.dumps({"contents": "The team has been tuning Winona."}),),
    )

    count = rebuild_official_record_mentions(conn)

    rows = conn.execute(
        """
        select entity_id, mention_text, match_field, match_method, confidence, context_text
        from official_record_mentions
        order by mention_text
        """
    ).fetchall()
    assert count == 3
    assert [tuple(row)[:5] for row in rows] == [
        (dst_id, "Don't Starve Together", "summary", "canonical_title_phrase", 0.95),
        (winona_id, "Winona", "title", "canonical_title_phrase", 0.95),
        (wormwood_id, "Wormwood", "title", "canonical_title_phrase", 0.95),
    ]
    assert all("Bee" not in row["context_text"] for row in rows)


def test_rebuild_official_record_mentions_uses_word_boundaries(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    upsert_entity(
        conn,
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=13,
        canonical_url="https://dontstarve.fandom.com/wiki/Bee",
        summary="A mob.",
    )
    conn.execute(
        """
        insert into official_records (
            provider, record_type, external_id, title, url, status, summary, payload_json
        )
        values (
            'steam',
            'news',
            '1001',
            'Quality has been improved',
            'https://store.steampowered.com/news/app/322330/view/1001',
            'ok',
            'The update has been released.',
            '{"contents": "Nothing about bees here."}'
        )
        """
    )

    count = rebuild_official_record_mentions(conn)

    assert count == 0


def test_rebuild_official_record_mentions_skips_generic_single_word_entries(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    upsert_entity(
        conn,
        canonical_title="Farm",
        kind="structure",
        primary_source_id=source_id,
        primary_page_id=20,
        canonical_url="https://dontstarve.fandom.com/wiki/Farm",
        summary="A structure.",
    )
    upsert_entity(
        conn,
        canonical_title="Don't Starve Together",
        kind="page",
        primary_source_id=source_id,
        primary_page_id=21,
        canonical_url="https://dontstarve.fandom.com/wiki/Don%27t_Starve_Together",
        summary="The multiplayer game.",
    )
    conn.execute(
        """
        insert into official_records (
            provider, record_type, external_id, title, url, status, summary, payload_json
        )
        values (
            'steam',
            'appdetails',
            '322330',
            'Don''t Starve Together',
            'https://store.steampowered.com/app/322330/',
            'ok',
            'Fight, Farm, Build and Explore Together.',
            '{}'
        )
        """
    )

    count = rebuild_official_record_mentions(conn)

    rows = conn.execute(
        """
        select entity_title, match_field
        from official_record_mentions
        order by entity_title
        """
    ).fetchall()
    assert count == 1
    assert [tuple(row) for row in rows] == [("Don't Starve Together", "title")]
