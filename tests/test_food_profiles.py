from dst_wiki_db.food_profiles import rebuild_entity_food_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_food_profiles_normalizes_recipe_restore_stats(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Meatballs", "item")
    _insert_rollup(conn, entity_id, "Meatballs", "item", "hp_restored", "survival", "points", 3, 3, "3")
    _insert_rollup(
        conn,
        entity_id,
        "Meatballs",
        "item",
        "hunger_restored",
        "survival",
        "points",
        62.5,
        62.5,
        "62.5",
    )
    _insert_rollup(
        conn,
        entity_id,
        "Meatballs",
        "item",
        "sanity_restored",
        "survival",
        "points",
        5,
        5,
        "5",
    )
    _insert_rollup(conn, entity_id, "Meatballs", "item", "spoil", "survival", "days", 10, 10, "10 Days")
    _insert_rollup(conn, entity_id, "Meatballs", "item", "cooktime", "stat", "seconds", 15, 15, "15 sec")
    _insert_rollup(conn, entity_id, "Meatballs", "item", "priority", "item", "level", -1, -1, "-1")

    result = rebuild_entity_food_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, kind, health_min, health_max, hunger_min,
               hunger_max, sanity_min, sanity_max, spoil_days_min,
               spoil_days_max, cooktime_seconds_min, priority_min,
               stat_count, has_restore_stats, has_food_value
        from entity_food_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Meatballs",
        "kind": "item",
        "health_min": 3.0,
        "health_max": 3.0,
        "hunger_min": 62.5,
        "hunger_max": 62.5,
        "sanity_min": 5.0,
        "sanity_max": 5.0,
        "spoil_days_min": 10.0,
        "spoil_days_max": 10.0,
        "cooktime_seconds_min": 15.0,
        "priority_min": -1.0,
        "stat_count": 6,
        "has_restore_stats": 1,
        "has_food_value": 0,
    }


def test_rebuild_entity_food_profiles_normalizes_raw_food_stats(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _source_id, _raw_page_id, entity_id = _seed_entity(conn, "Berries", "food")
    _insert_rollup(conn, entity_id, "Berries", "food", "health", "food", "points", 0, 1, "0 | 1")
    _insert_rollup(conn, entity_id, "Berries", "food", "hunger", "food", "points", 9.375, 12.5, "9.375 | 12.5")
    _insert_rollup(conn, entity_id, "Berries", "food", "sanity", "food", "points", 0, 0, "0")
    _insert_rollup(conn, entity_id, "Berries", "food", "spoil", "food", "days", 3, 6, "3 Days | 6 Days")
    _insert_rollup(conn, entity_id, "Berries", "food", "food_value", "food", "points", 0.5, 0.5, "Fruit x 0.5")

    result = rebuild_entity_food_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, health_min, health_max, hunger_min,
               hunger_max, sanity_min, sanity_max, food_value_min,
               food_value_max, has_restore_stats, has_food_value
        from entity_food_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Berries",
        "health_min": 0.0,
        "health_max": 1.0,
        "hunger_min": 9.375,
        "hunger_max": 12.5,
        "sanity_min": 0.0,
        "sanity_max": 0.0,
        "food_value_min": 0.5,
        "food_value_max": 0.5,
        "has_restore_stats": 1,
        "has_food_value": 1,
    }


def test_rebuild_entity_food_profiles_skips_non_food_stats(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _source_id, _raw_page_id, entity_id = _seed_entity(conn, "Football Helmet", "item")
    _insert_rollup(conn, entity_id, "Football Helmet", "item", "durability", "item", "uses", 315, 450, "315 | 450")

    assert rebuild_entity_food_profiles(conn) == 0
    assert conn.execute("select count(*) from entity_food_profiles").fetchone()[0] == 0


def _seed_entity(conn, canonical_title, kind):
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title=canonical_title,
        kind=kind,
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url=f"https://example.test/{canonical_title.replace(' ', '_')}",
        summary="",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, ?, 'https://example.test/Page', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id, canonical_title),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    return source_id, raw_page_id, entity_id


def _insert_rollup(
    conn,
    entity_id,
    canonical_title,
    kind,
    stat_name,
    stat_type,
    unit,
    value_min,
    value_max,
    value_texts,
):
    conn.execute(
        """
        insert into entity_stat_rollups (
            entity_id, slug, canonical_title, kind, stat_name, stat_type,
            unit, value_min, value_max, value_count, evidence_count,
            source_count, variant_count, value_texts
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 1, 1, 0, ?)
        """,
        (
            entity_id,
            canonical_title.lower().replace(" ", "-"),
            canonical_title,
            kind,
            stat_name,
            stat_type,
            unit,
            value_min,
            value_max,
            value_texts,
        ),
    )
