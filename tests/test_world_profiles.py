from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.world_profiles import rebuild_entity_world_profiles


def test_rebuild_entity_world_profiles_pivots_plant_world_fields(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Berry Bush", "plant")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "biome", "GrasslandForest")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "spawn_code", '"berrybush""berrybush2"')
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "renew", "Yes:Cave RegenerationWorld Regrowth")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "perk", "Can be replanted")
    _insert_rollup(conn, entity_id, "Berry Bush", "plant", "resources", 1, 3, "Berries x1 | x3")

    result = rebuild_entity_world_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, kind, biome_text, spawn_code_text, renew_text,
               resources_min, resources_max, resources_text, perk_text,
               attribute_count, stat_count, has_biome, has_spawn_code,
               is_renewable, has_resources, has_growth_data, has_combat_stats
        from entity_world_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Berry Bush",
        "kind": "plant",
        "biome_text": "GrasslandForest",
        "spawn_code_text": "berrybush | berrybush2",
        "renew_text": "Yes:Cave RegenerationWorld Regrowth",
        "resources_min": 1.0,
        "resources_max": 3.0,
        "resources_text": "Berries x1 | x3",
        "perk_text": "Can be replanted",
        "attribute_count": 4,
        "stat_count": 1,
        "has_biome": 1,
        "has_spawn_code": 1,
        "is_renewable": 1,
        "has_resources": 1,
        "has_growth_data": 0,
        "has_combat_stats": 0,
    }


def test_rebuild_entity_world_profiles_includes_plant_combat_stats(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Hanging Vine", "plant")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "special_ability", "Knocks out items")
    _insert_rollup(conn, entity_id, "Hanging Vine", "plant", "health", 100, 100, "100")
    _insert_rollup(conn, entity_id, "Hanging Vine", "plant", "damage", 10, 10, "10")
    _insert_rollup(conn, entity_id, "Hanging Vine", "plant", "attack_range", 3, 3, "3")
    _insert_rollup(conn, entity_id, "Hanging Vine", "plant", "attack_period", 1, 1, "1")

    result = rebuild_entity_world_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select health_max, damage_max, attack_range_max,
               attack_period_max, special_ability_text, has_combat_stats
        from entity_world_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "health_max": 100.0,
        "damage_max": 10.0,
        "attack_range_max": 3.0,
        "attack_period_max": 1.0,
        "special_ability_text": "Knocks out items",
        "has_combat_stats": 1,
    }


def test_rebuild_entity_world_profiles_skips_item_only_entities(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Spear", "item")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "spawn_code", '"spear"')
    _insert_rollup(conn, entity_id, "Spear", "item", "damage", 34, 34, "34")

    assert rebuild_entity_world_profiles(conn) == 0
    assert conn.execute("select count(*) from entity_world_profiles").fetchone()[0] == 0


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


def _insert_attribute(conn, entity_id, source_id, raw_page_id, canonical_name, value_text):
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, variant_key
        )
        values (?, ?, ?, 0, 'Plant Infobox', ?, ?, ?, '')
        """,
        (entity_id, source_id, raw_page_id, canonical_name, canonical_name, value_text),
    )


def _insert_rollup(
    conn,
    entity_id,
    canonical_title,
    kind,
    stat_name,
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
        values (?, ?, ?, ?, ?, 'world', 'points', ?, ?, 1, 1, 1, 0, ?)
        """,
        (
            entity_id,
            canonical_title.lower().replace(" ", "-"),
            canonical_title,
            kind,
            stat_name,
            value_min,
            value_max,
            value_texts,
        ),
    )
