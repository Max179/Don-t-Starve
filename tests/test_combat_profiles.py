from dst_wiki_db.combat_profiles import rebuild_entity_combat_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_combat_profiles_pivots_combat_and_movement_stats(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn)
    health_attr = _insert_attribute(conn, entity_id, source_id, raw_page_id, "health")
    damage_attr = _insert_attribute(conn, entity_id, source_id, raw_page_id, "damage")
    range_attr = _insert_attribute(conn, entity_id, source_id, raw_page_id, "attack_range")
    run_attr = _insert_attribute(conn, entity_id, source_id, raw_page_id, "run_speed")
    _insert_stat(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        health_attr,
        stat_name="health",
        stat_type="combat",
        value_text="2500 / 10000",
        values=[2500, 10000],
        unit="points",
    )
    _insert_stat(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        damage_attr,
        stat_name="damage",
        stat_type="combat",
        value_text="100 to player / 200 to mobs",
        values=[100, 200],
        unit="points",
    )
    _insert_stat(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        range_attr,
        stat_name="attack_range",
        stat_type="combat",
        value_text="4.5 (melee), 18 (spin)",
        values=[4.5, 18],
        unit="tiles",
    )
    _insert_stat(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        run_attr,
        stat_name="run_speed",
        stat_type="movement",
        value_text="6",
        values=[6],
        unit="units_per_second",
    )

    result = rebuild_entity_combat_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select
            canonical_title,
            kind,
            health_min,
            health_max,
            health_text,
            health_evidence_count,
            damage_min,
            damage_max,
            damage_text,
            damage_evidence_count,
            attack_range_min,
            attack_range_max,
            attack_range_text,
            run_speed_min,
            run_speed_max,
            combat_stat_count,
            movement_stat_count,
            source_count
        from entity_combat_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Ancient Guardian",
        "kind": "boss",
        "health_min": 2500.0,
        "health_max": 10000.0,
        "health_text": "2500 / 10000",
        "health_evidence_count": 1,
        "damage_min": 100.0,
        "damage_max": 200.0,
        "damage_text": "100 to player / 200 to mobs",
        "damage_evidence_count": 1,
        "attack_range_min": 4.5,
        "attack_range_max": 18.0,
        "attack_range_text": "4.5 (melee), 18 (spin)",
        "run_speed_min": 6.0,
        "run_speed_max": 6.0,
        "combat_stat_count": 3,
        "movement_stat_count": 1,
        "source_count": 1,
    }


def test_rebuild_entity_combat_profiles_skips_entities_without_combat_data(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(
        conn, canonical_title="Cut Grass", kind="item"
    )
    attr_id = _insert_attribute(conn, entity_id, source_id, raw_page_id, "stack")
    _insert_stat(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        attr_id,
        stat_name="stack",
        stat_type="item",
        value_text="40",
        values=[40],
        unit="items",
    )

    result = rebuild_entity_combat_profiles(conn)

    assert result == 0
    assert conn.execute("select count(*) from entity_combat_profiles").fetchone()[0] == 0


def test_rebuild_entity_combat_profiles_ignores_food_health_stats(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(
        conn, canonical_title="Pierogi", kind="food"
    )
    attr_id = _insert_attribute(conn, entity_id, source_id, raw_page_id, "health")
    _insert_stat(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        attr_id,
        stat_name="health",
        stat_type="food",
        value_text="40",
        values=[40],
        unit="points",
    )

    result = rebuild_entity_combat_profiles(conn)

    assert result == 0
    assert conn.execute("select count(*) from entity_combat_profiles").fetchone()[0] == 0


def _seed_entity(conn, *, canonical_title="Ancient Guardian", kind="boss"):
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


def _insert_attribute(conn, entity_id, source_id, raw_page_id, name):
    cursor = conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, value_number, unit, variant_key
        )
        values (?, ?, ?, 0, 'Infobox', ?, ?, '', null, '', '')
        """,
        (entity_id, source_id, raw_page_id, name, name),
    )
    return cursor.lastrowid


def _insert_stat(
    conn,
    entity_id,
    source_id,
    raw_page_id,
    attribute_id,
    *,
    stat_name,
    stat_type,
    value_text,
    values,
    unit,
):
    cursor = conn.execute(
        """
        insert into entity_stats (
            entity_id, source_id, raw_page_id, attribute_id, template_index,
            stat_name, stat_type, raw_name, value_text, value_number,
            unit, variant_key
        )
        values (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, '')
        """,
        (
            entity_id,
            source_id,
            raw_page_id,
            attribute_id,
            stat_name,
            stat_type,
            stat_name,
            value_text,
            values[0],
            unit,
        ),
    )
    stat_id = cursor.lastrowid
    for index, value in enumerate(values):
        conn.execute(
            """
            insert into entity_stat_values (
                entity_stat_id, entity_id, source_id, raw_page_id, attribute_id,
                stat_name, value_index, raw_value, value_number, context_text,
                unit, variant_key
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (
                stat_id,
                entity_id,
                source_id,
                raw_page_id,
                attribute_id,
                stat_name,
                index,
                str(value),
                value,
                value_text,
                unit,
            ),
        )
    return stat_id
