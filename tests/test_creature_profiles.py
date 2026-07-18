from dst_wiki_db.creature_profiles import rebuild_entity_creature_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_creature_profiles_pivots_boss_ecology_and_combat(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Deerclops", "boss")
    eyeball_id = upsert_entity(
        conn,
        canonical_title="Deerclops Eyeball",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Deerclops_Eyeball",
        summary="",
    )
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "spawn_code", '"deerclops"')
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "biome", "Forest")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "special_ability", "Destroys structures")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "drops", "Deerclops Eyeball")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "spawn_from", "Winter")
    _insert_rollup(conn, entity_id, "Deerclops", "boss", "health", 2000, 4000, "2000 | 4000")
    _insert_rollup(conn, entity_id, "Deerclops", "boss", "damage", 75, 150, "75 | 150")
    _insert_rollup(conn, entity_id, "Deerclops", "boss", "attack_range", 4, 6, "4 | 6")
    _insert_rollup(conn, entity_id, "Deerclops", "boss", "attack_period", 3, 3, "3")
    _insert_rollup(conn, entity_id, "Deerclops", "boss", "walk_speed", 3, 3, "3")
    _insert_edge(conn, entity_id, eyeball_id, source_id, "drops", "fact", "forward")

    result = rebuild_entity_creature_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, kind, spawn_code_text, biome_text,
               special_ability_text, drops_text, spawn_from_text,
               health_min, health_max, damage_max, attack_range_max,
               walk_speed_max, drop_edge_count, drop_related_titles,
               is_boss, has_combat_stats, has_movement_stats,
               has_drop_data, has_spawn_data
        from entity_creature_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Deerclops",
        "kind": "boss",
        "spawn_code_text": "deerclops",
        "biome_text": "Forest",
        "special_ability_text": "Destroys structures",
        "drops_text": "Deerclops Eyeball",
        "spawn_from_text": "Winter",
        "health_min": 2000.0,
        "health_max": 4000.0,
        "damage_max": 150.0,
        "attack_range_max": 6.0,
        "walk_speed_max": 3.0,
        "drop_edge_count": 1,
        "drop_related_titles": "Deerclops Eyeball",
        "is_boss": 1,
        "has_combat_stats": 1,
        "has_movement_stats": 1,
        "has_drop_data": 1,
        "has_spawn_data": 1,
    }


def test_rebuild_entity_creature_profiles_keeps_sanity_effects_for_mobs(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Shadow Creature", "mob")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "perk", "Nightmare aligned")
    _insert_rollup(conn, entity_id, "Shadow Creature", "mob", "sanityaura", -40, -25, "-25/min | -40/min")
    _insert_rollup(conn, entity_id, "Shadow Creature", "mob", "sanitydrain", -10, -10, "-10/min")

    assert rebuild_entity_creature_profiles(conn) == 1
    row = conn.execute(
        """
        select perk_text, sanityaura_min, sanityaura_max, sanitydrain_min,
               is_boss, has_sanity_effects, has_combat_stats
        from entity_creature_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "perk_text": "Nightmare aligned",
        "sanityaura_min": -40.0,
        "sanityaura_max": -25.0,
        "sanitydrain_min": -10.0,
        "is_boss": 0,
        "has_sanity_effects": 1,
        "has_combat_stats": 0,
    }


def test_rebuild_entity_creature_profiles_skips_non_creatures(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Spear", "item")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "spawn_code", '"spear"')
    _insert_rollup(conn, entity_id, "Spear", "item", "damage", 34, 34, "34")

    assert rebuild_entity_creature_profiles(conn) == 0
    assert conn.execute("select count(*) from entity_creature_profiles").fetchone()[0] == 0


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
        values (?, ?, ?, 0, 'Mob Infobox', ?, ?, ?, '')
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
        values (?, ?, ?, ?, ?, 'combat', 'points', ?, ?, 1, 1, 1, 0, ?)
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


def _insert_edge(
    conn,
    entity_id,
    related_entity_id,
    source_id,
    edge_type,
    edge_group,
    direction,
):
    conn.execute(
        """
        insert into entity_gameplay_edges (
            entity_id, related_entity_id, source_id, source_table,
            source_row_id, edge_type, edge_group, direction, entity_title,
            entity_slug, entity_kind, related_title, related_slug,
            related_kind, confidence
        )
        values (?, ?, ?, 'entity_facts', 1, ?, ?, ?, 'Deerclops',
                'deerclops', 'boss', 'Deerclops Eyeball',
                'deerclops-eyeball', 'item', 0.9)
        """,
        (entity_id, related_entity_id, source_id, edge_type, edge_group, direction),
    )
