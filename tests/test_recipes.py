from dst_wiki_db.build import write_parsed_page
from dst_wiki_db.parser import parse_page
from dst_wiki_db.recipes import rebuild_recipe_ingredients
from dst_wiki_db.schema import connect, init_db, upsert_source


def test_rebuild_recipe_ingredients_pairs_ingredients_with_multipliers(tmp_path):
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
        values (?, 12, 0, 'Alchemy Engine', 100, 'https://dontstarve.fandom.com/wiki/Alchemy_Engine', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    parsed = parse_page(
        "Alchemy Engine",
        """{{Structure Infobox
|image=Alchemy Engine.png
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
        source_pageid=12,
        source_revid=100,
        source_timestamp="2026-07-01T00:00:00Z",
        page_url="https://dontstarve.fandom.com/wiki/Alchemy_Engine",
        parsed=parsed,
        primary=False,
    )

    count = rebuild_recipe_ingredients(conn)

    rows = conn.execute(
        """
        select ingredient_slot, ingredient_name, quantity_number
        from recipe_ingredients
        where entity_id=?
        order by ingredient_slot
        """,
        (entity_id,),
    ).fetchall()
    assert count == 2
    assert [tuple(row) for row in rows] == [(1, "Boards", 4), (2, "Cut Stone", 2)]
