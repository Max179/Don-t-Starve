from dst_wiki_db.item_profiles import rebuild_entity_item_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_item_profiles_pivots_weapon_and_armor_stats(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _source_id, _raw_page_id, entity_id = _seed_entity(conn, "Football Helmet", "item")
    _insert_rollup(conn, entity_id, "Football Helmet", "item", "durability", "item", "uses", 315, 450, "315 hp | 450 hp")
    _insert_rollup(conn, entity_id, "Football Helmet", "item", "protection", "item", "percent", 80, 80, "80%")
    _insert_rollup(conn, entity_id, "Football Helmet", "item", "water_resistance", "item", "percent", 20, 20, "20%")
    _insert_rollup(conn, entity_id, "Football Helmet", "item", "stack", "item", "items", None, None, "Does not stack")
    _insert_rollup(conn, entity_id, "Football Helmet", "item", "tier", "item", "level", 2, 2, "2")

    result = rebuild_entity_item_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, kind, durability_min, durability_max,
               protection_min, protection_max, water_resistance_min,
               stack_text, tier_min, tier_max, stat_count,
               has_weapon_stats, has_armor_stats, has_stack_stats
        from entity_item_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Football Helmet",
        "kind": "item",
        "durability_min": 315.0,
        "durability_max": 450.0,
        "protection_min": 80.0,
        "protection_max": 80.0,
        "water_resistance_min": 20.0,
        "stack_text": "Does not stack",
        "tier_min": 2.0,
        "tier_max": 2.0,
        "stat_count": 5,
        "has_weapon_stats": 0,
        "has_armor_stats": 1,
        "has_stack_stats": 1,
    }


def test_rebuild_entity_item_profiles_includes_combat_damage_for_weapons(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _source_id, _raw_page_id, entity_id = _seed_entity(conn, "Tentacle Spike", "item")
    _insert_rollup(conn, entity_id, "Tentacle Spike", "item", "damage", "combat", "points", 51, 51, "51")
    _insert_rollup(conn, entity_id, "Tentacle Spike", "item", "durability", "item", "uses", 100, 100, "100 uses")

    result = rebuild_entity_item_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select damage_min, damage_max, damage_text, durability_min,
               has_weapon_stats, has_armor_stats
        from entity_item_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "damage_min": 51.0,
        "damage_max": 51.0,
        "damage_text": "51",
        "durability_min": 100.0,
        "has_weapon_stats": 1,
        "has_armor_stats": 0,
    }


def test_rebuild_entity_item_profiles_skips_non_item_damage(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _source_id, _raw_page_id, entity_id = _seed_entity(conn, "Deerclops", "mob")
    _insert_rollup(conn, entity_id, "Deerclops", "mob", "damage", "combat", "points", 75, 75, "75")
    _insert_rollup(conn, entity_id, "Deerclops", "mob", "health", "combat", "points", 4000, 4000, "4000")

    assert rebuild_entity_item_profiles(conn) == 0
    assert conn.execute("select count(*) from entity_item_profiles").fetchone()[0] == 0


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
