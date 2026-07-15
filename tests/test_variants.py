from dst_wiki_db.build import write_parsed_page
from dst_wiki_db.parser import parse_page
from dst_wiki_db.schema import connect, init_db, upsert_source
from dst_wiki_db.variants import rebuild_entity_variants, variant_label, variant_type


def test_variant_label_and_type_for_known_keys():
    assert variant_label("dst") == "Don't Starve Together"
    assert variant_type("dst") == "game_scope"
    assert variant_label("seed") == "Seed"
    assert variant_type("seed") == "growth_stage"
    assert variant_label("2") == "Variant 2"
    assert variant_type("2") == "numbered_variant"


def test_rebuild_entity_variants_from_images_attributes_and_repeated_infoboxes(tmp_path):
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
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 77, 0, 'Carrot', 100, 'https://dontstarve.fandom.com/wiki/Carrot', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    parsed = parse_page(
        "Carrot",
        """{{Item Infobox
|image1=Carrot.png
|image2=Roasted Carrot.png
|health1=1
|health2=3
|seed=Carrot Seeds.png
}}
{{Item Infobox
|image=Planted Carrot.png
|health=10
}}
'''Carrot''' is food.
[[Category:Items]]
""",
    )
    entity_id = write_parsed_page(
        conn,
        source_id=source_id,
        raw_page_id=raw_page_id,
        source_title="Carrot",
        source_pageid=77,
        source_revid=100,
        source_timestamp="2026-07-01T00:00:00Z",
        page_url="https://dontstarve.fandom.com/wiki/Carrot",
        parsed=parsed,
        primary=False,
    )

    count = rebuild_entity_variants(conn)

    rows = conn.execute(
        """
        select variant_key, variant_type, label
        from entity_variants
        where entity_id=?
        order by variant_key, variant_type
        """,
        (entity_id,),
    ).fetchall()
    assert count == 4
    assert [tuple(row) for row in rows] == [
        ("1", "numbered_variant", "Variant 1"),
        ("2", "numbered_variant", "Variant 2"),
        ("seed", "growth_stage", "Seed"),
        ("template:1", "infobox_instance", "Item Infobox #1"),
    ]


def test_rebuild_entity_variants_does_not_treat_recipe_slots_as_variants(tmp_path):
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
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 78, 0, 'Alchemy Engine', 100, 'https://dontstarve.fandom.com/wiki/Alchemy_Engine', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    parsed = parse_page(
        "Alchemy Engine",
        """{{Structure Infobox
|ingredient1=Boards
|multiplier1=4
|ingredient2=Cut Stone
|multiplier2=2
}}
'''Alchemy Engine''' is a structure.
[[Category:Structures]]
""",
    )
    entity_id = write_parsed_page(
        conn,
        source_id=source_id,
        raw_page_id=raw_page_id,
        source_title="Alchemy Engine",
        source_pageid=78,
        source_revid=100,
        source_timestamp="2026-07-01T00:00:00Z",
        page_url="https://dontstarve.fandom.com/wiki/Alchemy_Engine",
        parsed=parsed,
        primary=False,
    )

    count = rebuild_entity_variants(conn)

    rows = conn.execute(
        "select variant_key from entity_variants where entity_id=?",
        (entity_id,),
    ).fetchall()
    assert count == 0
    assert rows == []
