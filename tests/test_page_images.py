import json

from dst_wiki_db.page_images import rebuild_page_images
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_page_images_from_raw_page_metadata(tmp_path):
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
    entity_id = upsert_entity(
        conn,
        canonical_title="Ancient Guardian",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=42,
        canonical_url="https://dontstarve.fandom.com/wiki/Ancient_Guardian",
        summary="A boss.",
    )
    images = [
        {"ns": 6, "title": "File:Ancient Guardian.png"},
        {"ns": 6, "title": "File:Ancient Guardian Phase 2.png"},
        {"ns": 6, "title": "File:Ancient Guardian.png"},
        "Image:Ancient Guardian Figure (Marble).png",
    ]
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext,
            images_json, fetched_at
        )
        values (?, 42, 0, 'Ancient Guardian', 100,
            'https://dontstarve.fandom.com/wiki/Ancient_Guardian', 'body', ?, 'now')
        """,
        (source_id, json.dumps(images)),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_sources (
            entity_id, source_id, raw_page_id, source_title, source_pageid,
            source_url, match_method
        )
        values (?, ?, ?, 'Ancient Guardian', 42,
            'https://dontstarve.fandom.com/wiki/Ancient_Guardian', 'title_slug')
        """,
        (entity_id, source_id, raw_page_id),
    )

    count = rebuild_page_images(conn)

    rows = conn.execute(
        """
        select image_title, image_name, image_slug, role, description_url
        from page_images
        where entity_id=?
        order by image_name
        """,
        (entity_id,),
    ).fetchall()
    assert count == 3
    assert [tuple(row) for row in rows] == [
        (
            "File:Ancient Guardian Figure (Marble).png",
            "Ancient Guardian Figure (Marble).png",
            "ancient-guardian-figure-marble-png",
            "page_reference",
            "https://dontstarve.fandom.com/wiki/File:Ancient_Guardian_Figure_%28Marble%29.png",
        ),
        (
            "File:Ancient Guardian Phase 2.png",
            "Ancient Guardian Phase 2.png",
            "ancient-guardian-phase-2-png",
            "page_reference",
            "https://dontstarve.fandom.com/wiki/File:Ancient_Guardian_Phase_2.png",
        ),
        (
            "File:Ancient Guardian.png",
            "Ancient Guardian.png",
            "ancient-guardian-png",
            "page_reference",
            "https://dontstarve.fandom.com/wiki/File:Ancient_Guardian.png",
        ),
    ]


def test_rebuild_page_images_caps_generic_refs_but_keeps_title_matches(tmp_path):
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
    entity_id = upsert_entity(
        conn,
        canonical_title="Rabbit",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=7,
        canonical_url="https://dontstarve.fandom.com/wiki/Rabbit",
        summary="A small animal.",
    )
    images = [
        {"ns": 6, "title": f"File:Generic Icon {index}.png"}
        for index in range(100)
    ] + [
        {"ns": 6, "title": "File:Rabbit Winter.png"},
        {"ns": 6, "title": "File:Rabbit.png"},
    ]
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext,
            images_json, fetched_at
        )
        values (?, 7, 0, 'Rabbit', 101,
            'https://dontstarve.fandom.com/wiki/Rabbit', 'body', ?, 'now')
        """,
        (source_id, json.dumps(images)),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_sources (
            entity_id, source_id, raw_page_id, source_title, source_pageid,
            source_url, match_method
        )
        values (?, ?, ?, 'Rabbit', 7,
            'https://dontstarve.fandom.com/wiki/Rabbit', 'title_slug')
        """,
        (entity_id, source_id, raw_page_id),
    )

    count = rebuild_page_images(conn)

    rows = conn.execute(
        """
        select image_name
        from page_images
        where entity_id=?
        order by id
        """,
        (entity_id,),
    ).fetchall()
    assert count == 82
    assert [row["image_name"] for row in rows[:2]] == [
        "Generic Icon 0.png",
        "Generic Icon 1.png",
    ]
    assert [row["image_name"] for row in rows[-2:]] == [
        "Rabbit Winter.png",
        "Rabbit.png",
    ]
