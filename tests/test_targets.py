from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.targets import rebuild_entity_targets


def test_rebuild_entity_targets_resolves_wiki_link_relations(tmp_path):
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
    wilson_id = upsert_entity(
        conn,
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://dontstarve.fandom.com/wiki/Wilson",
        summary="Playable character.",
    )
    beard_id = upsert_entity(
        conn,
        canonical_title="Beard Hair",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://dontstarve.fandom.com/wiki/Beard_Hair",
        summary="A resource.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 1, 0, 'Wilson', 10, 'https://dontstarve.fandom.com/wiki/Wilson', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages where pageid=1").fetchone()["id"]
    conn.execute(
        """
        insert into entity_relations (
            entity_id, source_id, raw_page_id, relation_type,
            target_title, target_slug, raw_value
        )
        values (?, ?, ?, 'wikilink', 'Beard Hair', 'beard-hair', 'Beard Hair')
        """,
        (wilson_id, source_id, raw_page_id),
    )

    result = rebuild_entity_targets(conn)

    assert result["entity_relation_targets"] == 1
    assert result["entity_fact_targets"] == 0
    row = conn.execute(
        "select target_entity_id from entity_relations where entity_id=?", (wilson_id,)
    ).fetchone()
    assert row["target_entity_id"] == beard_id


def test_rebuild_entity_targets_creates_fact_target_bridge(tmp_path):
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
    spider_id = upsert_entity(
        conn,
        canonical_title="Cave Spider",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://dontstarve.fandom.com/wiki/Cave_Spider",
        summary="A spider.",
    )
    silk_id = upsert_entity(
        conn,
        canonical_title="Silk",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://dontstarve.fandom.com/wiki/Silk",
        summary="A material.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 1, 0, 'Cave Spider', 10, 'https://dontstarve.fandom.com/wiki/Cave_Spider', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages where pageid=1").fetchone()["id"]
    conn.execute(
        """
        insert into entity_facts (
            entity_id, source_id, raw_page_id, fact_type, raw_name, value_text,
            target_title, target_slug, probability_text
        )
        values (?, ?, ?, 'drops', 'drops', '{{Item|link=Silk}} 25%', 'Silk', 'silk', '25%')
        """,
        (spider_id, source_id, raw_page_id),
    )
    fact_id = conn.execute("select id from entity_facts").fetchone()["id"]

    result = rebuild_entity_targets(conn)

    assert result["entity_relation_targets"] == 0
    assert result["entity_fact_targets"] == 1
    row = conn.execute(
        """
        select entity_fact_id, entity_id, target_entity_id, target_title, match_method, confidence
        from entity_fact_targets
        """
    ).fetchone()
    assert tuple(row) == (
        fact_id,
        spider_id,
        silk_id,
        "Silk",
        "target_slug",
        0.9,
    )


def test_rebuild_entity_targets_creates_recipe_ingredient_bridge(tmp_path):
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
    alchemy_engine_id = upsert_entity(
        conn,
        canonical_title="Alchemy Engine",
        kind="structure",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://dontstarve.fandom.com/wiki/Alchemy_Engine",
        summary="A station.",
    )
    boards_id = upsert_entity(
        conn,
        canonical_title="Boards",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://dontstarve.fandom.com/wiki/Boards",
        summary="Crafting material.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 1, 0, 'Alchemy Engine', 10, 'https://dontstarve.fandom.com/wiki/Alchemy_Engine', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages where pageid=1").fetchone()["id"]
    conn.execute(
        """
        insert into recipe_ingredients (
            entity_id, source_id, raw_page_id, ingredient_slot,
            ingredient_name, ingredient_slug, quantity_text, quantity_number
        )
        values (?, ?, ?, 1, 'Boards', 'boards', '4', 4)
        """,
        (alchemy_engine_id, source_id, raw_page_id),
    )
    recipe_ingredient_id = conn.execute("select id from recipe_ingredients").fetchone()["id"]

    result = rebuild_entity_targets(conn)

    assert result["recipe_ingredient_targets"] == 1
    row = conn.execute(
        """
        select
            recipe_ingredient_id, entity_id, ingredient_entity_id,
            ingredient_name, match_method, confidence
        from recipe_ingredient_targets
        """
    ).fetchone()
    assert tuple(row) == (
        recipe_ingredient_id,
        alchemy_engine_id,
        boards_id,
        "Boards",
        "ingredient_slug",
        0.9,
    )
