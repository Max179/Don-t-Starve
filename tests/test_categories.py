import json

from dst_wiki_db.categories import rebuild_entity_categories
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_categories_from_raw_page_metadata(tmp_path):
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
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=18907,
        canonical_url="https://dontstarve.fandom.com/wiki/Wilson",
        summary="Wilson.",
    )
    categories = [
        {"ns": 14, "title": "Category:Characters"},
        {"ns": 14, "title": "Category:Lore"},
    ]
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext,
            categories_json, fetched_at
        )
        values (?, 18907, 0, 'Wilson', 100, 'https://dontstarve.fandom.com/wiki/Wilson', 'body', ?, 'now')
        """,
        (source_id, json.dumps(categories)),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_sources (
            entity_id, source_id, raw_page_id, source_title, source_pageid,
            source_url, match_method
        )
        values (?, ?, ?, 'Wilson', 18907, 'https://dontstarve.fandom.com/wiki/Wilson', 'title_slug')
        """,
        (entity_id, source_id, raw_page_id),
    )

    count = rebuild_entity_categories(conn)

    rows = conn.execute(
        """
        select category_name, category_slug
        from entity_categories
        where entity_id=?
        order by category_name
        """,
        (entity_id,),
    ).fetchall()
    assert count == 2
    assert [tuple(row) for row in rows] == [
        ("Characters", "characters"),
        ("Lore", "lore"),
    ]
