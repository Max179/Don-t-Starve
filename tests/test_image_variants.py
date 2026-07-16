import json

from dst_wiki_db.image_variants import rebuild_image_variants
from dst_wiki_db.page_images import rebuild_page_images
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_image_variants_detects_state_images_without_entity_false_positives(
    tmp_path,
):
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
    bee_id = upsert_entity(
        conn,
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=100,
        canonical_url="https://dontstarve.fandom.com/wiki/Bee",
        summary="A bee.",
    )
    upsert_entity(
        conn,
        canonical_title="Bee Box",
        kind="structure",
        primary_source_id=source_id,
        primary_page_id=101,
        canonical_url="https://dontstarve.fandom.com/wiki/Bee_Box",
        summary="A structure.",
    )
    images = [
        {"ns": 6, "title": "File:Bee.png"},
        {"ns": 6, "title": "File:Bee Build.png"},
        {"ns": 6, "title": "File:Bee Frozen.png"},
        {"ns": 6, "title": "File:Bee Box.png"},
    ]
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext,
            images_json, fetched_at
        )
        values (?, 100, 0, 'Bee', 200, 'https://dontstarve.fandom.com/wiki/Bee',
            'body', ?, 'now')
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
        values (?, ?, ?, 'Bee', 100, 'https://dontstarve.fandom.com/wiki/Bee',
            'title_slug')
        """,
        (bee_id, source_id, raw_page_id),
    )
    rebuild_page_images(conn)

    count = rebuild_image_variants(conn)

    rows = conn.execute(
        """
        select image_name, variant_key, variant_type, label, match_method, confidence
        from image_variants
        where entity_id=?
        order by image_name
        """,
        (bee_id,),
    ).fetchall()
    assert count == 2
    assert [tuple(row) for row in rows] == [
        (
            "Bee Build.png",
            "build",
            "build_state",
            "Build",
            "entity_slug_filename_prefix",
            0.85,
        ),
        (
            "Bee Frozen.png",
            "frozen",
            "state",
            "Frozen",
            "entity_slug_filename_prefix",
            0.85,
        ),
    ]


def test_rebuild_image_variants_classifies_farm_plant_growth_images(tmp_path):
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
    carrot_id = upsert_entity(
        conn,
        canonical_title="Carrot",
        kind="plant",
        primary_source_id=source_id,
        primary_page_id=200,
        canonical_url="https://dontstarve.fandom.com/wiki/Carrot",
        summary="A farm plant.",
    )
    images = [
        {"ns": 6, "title": "File:Carrot Plant Seed.png"},
        {"ns": 6, "title": "File:Carrot Plant Small.png"},
        {"ns": 6, "title": "File:Carrot Plant Med.png"},
        {"ns": 6, "title": "File:Carrot Plant Full.png"},
        {"ns": 6, "title": "File:Carrot Plant Oversized.png"},
        {"ns": 6, "title": "File:Carrot Plant Oversized Rot.png"},
    ]
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext,
            images_json, fetched_at
        )
        values (?, 200, 0, 'Carrot', 300,
            'https://dontstarve.fandom.com/wiki/Carrot', 'body', ?, 'now')
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
        values (?, ?, ?, 'Carrot', 200, 'https://dontstarve.fandom.com/wiki/Carrot',
            'title_slug')
        """,
        (carrot_id, source_id, raw_page_id),
    )
    rebuild_page_images(conn)

    count = rebuild_image_variants(conn)

    rows = conn.execute(
        """
        select variant_key, variant_type, confidence
        from image_variants
        where entity_id=?
        order by variant_key
        """,
        (carrot_id,),
    ).fetchall()
    assert count == 6
    assert [tuple(row) for row in rows] == [
        ("plant-full", "growth_stage", 0.85),
        ("plant-med", "growth_stage", 0.85),
        ("plant-oversized", "oversized_form", 0.85),
        ("plant-oversized-rot", "oversized_form", 0.85),
        ("plant-seed", "growth_stage", 0.85),
        ("plant-small", "growth_stage", 0.85),
    ]


def test_rebuild_image_variants_classifies_crop_stalk_growth_images(tmp_path):
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
    corn_id = upsert_entity(
        conn,
        canonical_title="Corn",
        kind="plant",
        primary_source_id=source_id,
        primary_page_id=300,
        canonical_url="https://dontstarve.fandom.com/wiki/Corn",
        summary="A crop.",
    )
    images = [
        {"ns": 6, "title": "File:Corn Stalk Seed.png"},
        {"ns": 6, "title": "File:Corn Stalk Small.png"},
        {"ns": 6, "title": "File:Corn Stalk Med.png"},
        {"ns": 6, "title": "File:Corn Stalk Full.png"},
        {"ns": 6, "title": "File:Corn Stalk Oversized.png"},
        {"ns": 6, "title": "File:Corn Stalk Rot Oversized.png"},
    ]
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext,
            images_json, fetched_at
        )
        values (?, 300, 0, 'Corn', 400, 'https://dontstarve.fandom.com/wiki/Corn',
            'body', ?, 'now')
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
        values (?, ?, ?, 'Corn', 300, 'https://dontstarve.fandom.com/wiki/Corn',
            'title_slug')
        """,
        (corn_id, source_id, raw_page_id),
    )
    rebuild_page_images(conn)

    count = rebuild_image_variants(conn)

    rows = conn.execute(
        """
        select variant_key, variant_type, confidence
        from image_variants
        where entity_id=?
        order by variant_key
        """,
        (corn_id,),
    ).fetchall()
    assert count == 6
    assert [tuple(row) for row in rows] == [
        ("stalk-full", "growth_stage", 0.85),
        ("stalk-med", "growth_stage", 0.85),
        ("stalk-oversized", "oversized_form", 0.85),
        ("stalk-rot-oversized", "oversized_form", 0.85),
        ("stalk-seed", "growth_stage", 0.85),
        ("stalk-small", "growth_stage", 0.85),
    ]
