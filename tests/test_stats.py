from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.stats import rebuild_entity_stat_values, rebuild_entity_stats


def test_rebuild_entity_stats_normalizes_core_combat_and_movement_fields(tmp_path):
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
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=100,
        canonical_url="https://dontstarve.fandom.com/wiki/Bee",
        summary="A bee.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 100, 0, 'Bee', 200, 'https://dontstarve.fandom.com/wiki/Bee',
            'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    attributes = [
        ("health", "health", "100", 100, ""),
        ("damage", "damage", "10", 10, ""),
        ("attackRange", "attack_range", "0.6", 0.6, ""),
        ("attackPeriod", "attack_period", "2", 2, ""),
        ("walkSpeed", "walk_speed", "4", 4, ""),
        ("runSpeed", "run_speed", "6", 6, ""),
        ("ingredient1", "ingredient1", "Honey", None, ""),
    ]
    for raw_name, canonical_name, value_text, value_number, variant_key in attributes:
        conn.execute(
            """
            insert into entity_attributes (
                entity_id, source_id, raw_page_id, template_index, template_name,
                raw_name, canonical_name, value_text, value_number, variant_key
            )
            values (?, ?, ?, 0, 'Mob Infobox', ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                source_id,
                raw_page_id,
                raw_name,
                canonical_name,
                value_text,
                value_number,
                variant_key,
            ),
        )

    count = rebuild_entity_stats(conn)

    rows = conn.execute(
        """
        select stat_name, stat_type, value_text, value_number, unit, variant_key
        from entity_stats
        where entity_id=?
        order by stat_name
        """,
        (entity_id,),
    ).fetchall()
    assert count == 6
    assert [tuple(row) for row in rows] == [
        ("attack_period", "combat", "2", 2, "seconds", ""),
        ("attack_range", "combat", "0.6", 0.6, "tiles", ""),
        ("damage", "combat", "10", 10, "points", ""),
        ("health", "combat", "100", 100, "points", ""),
        ("run_speed", "movement", "6", 6, "units_per_second", ""),
        ("walk_speed", "movement", "4", 4, "units_per_second", ""),
    ]


def test_rebuild_entity_stats_preserves_variant_keys_for_numbered_fields(tmp_path):
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
        canonical_title="Carrot",
        kind="food",
        primary_source_id=source_id,
        primary_page_id=200,
        canonical_url="https://dontstarve.fandom.com/wiki/Carrot",
        summary="A carrot.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 200, 0, 'Carrot', 300,
            'https://dontstarve.fandom.com/wiki/Carrot', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    attributes = [
        ("health1", "health1", "3", 3, "1"),
        ("health2", "health2", "1", 1, "2"),
        ("hunger1", "hunger1", "12.5", 12.5, "1"),
        ("hunger2", "hunger2", "6.25", 6.25, "2"),
    ]
    for raw_name, canonical_name, value_text, value_number, variant_key in attributes:
        conn.execute(
            """
            insert into entity_attributes (
                entity_id, source_id, raw_page_id, template_index, template_name,
                raw_name, canonical_name, value_text, value_number, variant_key
            )
            values (?, ?, ?, 0, 'Food Infobox', ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                source_id,
                raw_page_id,
                raw_name,
                canonical_name,
                value_text,
                value_number,
                variant_key,
            ),
        )

    count = rebuild_entity_stats(conn)

    rows = conn.execute(
        """
        select stat_name, stat_type, value_number, unit, variant_key, raw_name
        from entity_stats
        where entity_id=?
        order by stat_name, variant_key
        """,
        (entity_id,),
    ).fetchall()
    assert count == 4
    assert [tuple(row) for row in rows] == [
        ("health", "food", 3, "points", "1", "health1"),
        ("health", "food", 1, "points", "2", "health2"),
        ("hunger", "food", 12.5, "points", "1", "hunger1"),
        ("hunger", "food", 6.25, "points", "2", "hunger2"),
    ]


def test_rebuild_entity_stats_extracts_food_value_after_wiki_icon_size(tmp_path):
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
        canonical_title="Berries",
        kind="food",
        primary_source_id=source_id,
        primary_page_id=300,
        canonical_url="https://dontstarve.fandom.com/wiki/Berries",
        summary="Berries.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 300, 0, 'Berries', 400,
            'https://dontstarve.fandom.com/wiki/Berries', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, value_number, variant_key
        )
        values (?, ?, ?, 0, 'Food Infobox', 'foodValue', 'food_value',
            '32px|link=Fruit × 0.5', 32, '')
        """,
        (entity_id, source_id, raw_page_id),
    )

    count = rebuild_entity_stats(conn)

    row = conn.execute(
        """
        select stat_name, stat_type, value_text, value_number, unit
        from entity_stats
        where entity_id=?
        """,
        (entity_id,),
    ).fetchone()
    assert count == 1
    assert tuple(row) == (
        "food_value",
        "food",
        "32px|link=Fruit × 0.5",
        0.5,
        "points",
    )


def test_rebuild_entity_stat_values_extracts_all_combat_numbers(tmp_path):
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
        canonical_title="Antlion",
        kind="boss",
        primary_source_id=source_id,
        primary_page_id=400,
        canonical_url="https://dontstarve.fandom.com/wiki/Antlion",
        summary="A boss.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 400, 0, 'Antlion', 500,
            'https://dontstarve.fandom.com/wiki/Antlion', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, value_number, variant_key
        )
        values (?, ?, ?, 0, 'Mob Infobox', 'damage', 'damage',
            '50, 75, 100 to players 100, 150, 200 to mobs', 50, '')
        """,
        (entity_id, source_id, raw_page_id),
    )
    rebuild_entity_stats(conn)

    count = rebuild_entity_stat_values(conn)

    rows = conn.execute(
        """
        select value_index, raw_value, value_number, context_text, unit
        from entity_stat_values
        where entity_id=?
        order by value_index
        """,
        (entity_id,),
    ).fetchall()
    assert count == 6
    assert [tuple(row) for row in rows] == [
        (0, "50", 50, "50", "points"),
        (1, "75", 75, "75", "points"),
        (2, "100", 100, "100 to players", "points"),
        (3, "100", 100, "100", "points"),
        (4, "150", 150, "150", "points"),
        (5, "200", 200, "200 to mobs", "points"),
    ]


def test_rebuild_entity_stat_values_keeps_parenthesized_context(tmp_path):
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
        canonical_title="Bearger",
        kind="boss",
        primary_source_id=source_id,
        primary_page_id=500,
        canonical_url="https://dontstarve.fandom.com/wiki/Bearger",
        summary="A boss.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 500, 0, 'Bearger', 600,
            'https://dontstarve.fandom.com/wiki/Bearger', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, value_number, variant_key
        )
        values (?, ?, ?, 0, 'Mob Infobox', 'walkSpeed', 'walk_speed',
            '3 (casual)6 (aggressive)', 3, '')
        """,
        (entity_id, source_id, raw_page_id),
    )
    rebuild_entity_stats(conn)

    count = rebuild_entity_stat_values(conn)

    rows = conn.execute(
        """
        select raw_value, value_number, context_text, unit
        from entity_stat_values
        where entity_id=?
        order by value_index
        """,
        (entity_id,),
    ).fetchall()
    assert count == 2
    assert [tuple(row) for row in rows] == [
        ("3", 3, "3 (casual)", "units_per_second"),
        ("6", 6, "6 (aggressive)", "units_per_second"),
    ]


def test_rebuild_entity_stat_values_uses_clean_food_value_numbers(tmp_path):
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
        canonical_title="Berries",
        kind="food",
        primary_source_id=source_id,
        primary_page_id=600,
        canonical_url="https://dontstarve.fandom.com/wiki/Berries",
        summary="Berries.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 600, 0, 'Berries', 700,
            'https://dontstarve.fandom.com/wiki/Berries', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, value_number, variant_key
        )
        values (?, ?, ?, 0, 'Food Infobox', 'foodValue', 'food_value',
            '32px|link=Fruit × 0.5', 32, '')
        """,
        (entity_id, source_id, raw_page_id),
    )
    rebuild_entity_stats(conn)

    count = rebuild_entity_stat_values(conn)

    rows = conn.execute(
        """
        select raw_value, value_number, context_text
        from entity_stat_values
        where entity_id=?
        """,
        (entity_id,),
    ).fetchall()
    assert count == 1
    assert [tuple(row) for row in rows] == [("0.5", 0.5, "× 0.5")]
