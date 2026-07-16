from dst_wiki_db.gameplay_edges import rebuild_entity_gameplay_edges
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_gameplay_edges_adds_forward_and_inverse_edges(tmp_path):
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
    meatball_id = upsert_entity(
        conn,
        canonical_title="Meatballs",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Meatballs",
        summary="",
    )
    berries_id = upsert_entity(
        conn,
        canonical_title="Berries",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Berries",
        summary="",
    )
    spider_id = upsert_entity(
        conn,
        canonical_title="Spider",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=3,
        canonical_url="https://example.test/Spider",
        summary="",
    )
    silk_id = upsert_entity(
        conn,
        canonical_title="Silk",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=4,
        canonical_url="https://example.test/Silk",
        summary="",
    )
    for pageid, title in enumerate(("Meatballs", "Berries", "Spider", "Silk"), 1):
        conn.execute(
            """
            insert into raw_pages (
                source_id, pageid, ns, title, canonical_url, wikitext,
                categories_json, templates_json, images_json, externallinks_json,
                fetched_at
            )
            values (?, ?, 0, ?, 'https://example.test', '',
                    '[]', '[]', '[]', '[]', 'now')
            """,
            (source_id, pageid, title),
        )
    raw_page_id = conn.execute(
        "select id from raw_pages where title='Meatballs'"
    ).fetchone()["id"]
    conn.execute(
        """
        insert into recipe_ingredients (
            entity_id, source_id, raw_page_id, template_index,
            ingredient_slot, ingredient_name, ingredient_slug,
            quantity_text, quantity_number, variant_key
        )
        values (?, ?, ?, 0, 1, 'Berries', 'berries', '2', 2, 'dst')
        """,
        (meatball_id, source_id, raw_page_id),
    )
    recipe_ingredient_id = conn.execute(
        "select id from recipe_ingredients"
    ).fetchone()["id"]
    conn.execute(
        """
        insert into recipe_ingredient_targets (
            recipe_ingredient_id, entity_id, source_id, ingredient_entity_id,
            ingredient_name, ingredient_slug, match_method, confidence
        )
        values (?, ?, ?, ?, 'Berries', 'berries', 'ingredient_slug', 0.9)
        """,
        (recipe_ingredient_id, meatball_id, source_id, berries_id),
    )
    spider_page_id = conn.execute(
        "select id from raw_pages where title='Spider'"
    ).fetchone()["id"]
    conn.execute(
        """
        insert into entity_facts (
            entity_id, source_id, raw_page_id, template_index, fact_index,
            fact_type, raw_name, value_text, target_title, target_slug,
            probability_text, quantity_text, quantity_number, variant_key
        )
        values (?, ?, ?, 0, 0, 'drops', 'drops', 'Silk 50%',
                'Silk', 'silk', '50%', 'x1', 1, '')
        """,
        (spider_id, source_id, spider_page_id),
    )
    entity_fact_id = conn.execute("select id from entity_facts").fetchone()["id"]
    conn.execute(
        """
        insert into entity_fact_targets (
            entity_fact_id, entity_id, source_id, target_entity_id,
            target_title, target_slug, match_method, confidence
        )
        values (?, ?, ?, ?, 'Silk', 'silk', 'target_slug', 0.9)
        """,
        (entity_fact_id, spider_id, source_id, silk_id),
    )

    result = rebuild_entity_gameplay_edges(conn)

    assert result == 4
    rows = conn.execute(
        """
        select
            entity_id,
            related_entity_id,
            edge_type,
            edge_group,
            direction,
            source_table,
            quantity_text,
            quantity_number,
            probability_text,
            variant_key,
            confidence
        from entity_gameplay_edges
        order by edge_group, edge_type
        """
    ).fetchall()
    rows_by_type = {row["edge_type"]: dict(row) for row in rows}
    assert rows_by_type == {
        "drops": {
            "entity_id": spider_id,
            "related_entity_id": silk_id,
            "edge_type": "drops",
            "edge_group": "fact",
            "direction": "forward",
            "source_table": "entity_facts",
            "quantity_text": "x1",
            "quantity_number": 1.0,
            "probability_text": "50%",
            "variant_key": "",
            "confidence": 0.9,
        },
        "dropped_by": {
            "entity_id": silk_id,
            "related_entity_id": spider_id,
            "edge_type": "dropped_by",
            "edge_group": "fact",
            "direction": "inverse",
            "source_table": "entity_facts",
            "quantity_text": "x1",
            "quantity_number": 1.0,
            "probability_text": "50%",
            "variant_key": "",
            "confidence": 0.9,
        },
        "ingredient_for": {
            "entity_id": berries_id,
            "related_entity_id": meatball_id,
            "edge_type": "ingredient_for",
            "edge_group": "recipe",
            "direction": "inverse",
            "source_table": "recipe_ingredients",
            "quantity_text": "2",
            "quantity_number": 2.0,
            "probability_text": None,
            "variant_key": "dst",
            "confidence": 0.9,
        },
        "uses_ingredient": {
            "entity_id": meatball_id,
            "related_entity_id": berries_id,
            "edge_type": "uses_ingredient",
            "edge_group": "recipe",
            "direction": "forward",
            "source_table": "recipe_ingredients",
            "quantity_text": "2",
            "quantity_number": 2.0,
            "probability_text": None,
            "variant_key": "dst",
            "confidence": 0.9,
        },
    }


def test_rebuild_entity_gameplay_edges_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_entity_gameplay_edges(conn)
    second = rebuild_entity_gameplay_edges(conn)

    assert first == second == 0
