from dst_wiki_db.identity import extract_spawn_codes, rebuild_identity_keys
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_extract_spawn_codes_handles_quoted_and_concatenated_values():
    assert extract_spawn_codes('"anchor_item""anchor"') == ["anchor_item", "anchor"]
    assert extract_spawn_codes('"pig_ruins_entrance_small"\n"pig_ruins_entrance"') == [
        "pig_ruins_entrance_small",
        "pig_ruins_entrance",
    ]
    assert extract_spawn_codes("lavaarena_keyhole") == ["lavaarena_keyhole"]


def test_rebuild_identity_keys_from_title_spawn_code_and_image_sha(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com/",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Anchor",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://dontstarve.fandom.com/wiki/Anchor",
        summary="Anchor.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 1, 0, 'Anchor', 100, 'https://dontstarve.fandom.com/wiki/Anchor', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_sources (
            entity_id, source_id, raw_page_id, source_title, source_pageid,
            source_url, match_method
        )
        values (?, ?, ?, 'Anchor', 1, 'https://dontstarve.fandom.com/wiki/Anchor', 'title_slug')
        """,
        (entity_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name, raw_name,
            canonical_name, value_text, variant_key
        )
        values (?, ?, ?, 0, 'Item Infobox', 'spawnCode', 'spawn_code', '"anchor_item""anchor"', '')
        """,
        (entity_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_images (
            entity_id, source_id, raw_page_id, image_name, role, sha1, variant_key
        )
        values (?, ?, ?, 'Anchor.png', 'image', 'abc123', '')
        """,
        (entity_id, source_id, raw_page_id),
    )

    count = rebuild_identity_keys(conn)

    rows = conn.execute(
        """
        select key_type, key_value
        from entity_identity_keys
        where entity_id=?
        order by key_type, key_value
        """,
        (entity_id,),
    ).fetchall()
    assert count == 5
    assert [tuple(row) for row in rows] == [
        ("image_name", "anchor.png"),
        ("image_sha1", "abc123"),
        ("spawn_code", "anchor"),
        ("spawn_code", "anchor_item"),
        ("title_slug", "anchor"),
    ]
