from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.stat_rollups import rebuild_entity_stat_rollups


def test_rebuild_entity_stat_rollups_groups_values_and_evidence(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn)
    attr_id = _insert_attribute(conn, entity_id, source_id, raw_page_id, "damage")
    _insert_stat(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        attr_id,
        stat_name="damage",
        stat_type="combat",
        value_text="75 to player / 150 to mobs",
        values=[75, 150],
        unit="points",
        variant_key="normal",
    )
    enraged_attr_id = _insert_attribute(
        conn, entity_id, source_id, raw_page_id, "damage enraged"
    )
    _insert_stat(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        enraged_attr_id,
        stat_name="damage",
        stat_type="combat",
        value_text="100 enraged",
        values=[100],
        unit="points",
        variant_key="enraged",
    )

    result = rebuild_entity_stat_rollups(conn)

    assert result == 1
    row = conn.execute(
        """
        select
            canonical_title,
            stat_name,
            stat_type,
            unit,
            value_min,
            value_max,
            value_count,
            evidence_count,
            source_count,
            variant_count,
            value_texts
        from entity_stat_rollups
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Dragonfly",
        "stat_name": "damage",
        "stat_type": "combat",
        "unit": "points",
        "value_min": 75.0,
        "value_max": 150.0,
        "value_count": 3,
        "evidence_count": 2,
        "source_count": 1,
        "variant_count": 2,
        "value_texts": "100 enraged | 75 to player / 150 to mobs",
    }


def test_rebuild_entity_stat_rollups_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_entity_stat_rollups(conn)
    second = rebuild_entity_stat_rollups(conn)

    assert first == second == 0


def _seed_entity(conn):
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
        canonical_title="Dragonfly",
        kind="boss",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Dragonfly",
        summary="",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, 'Dragonfly', 'https://example.test/Dragonfly', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id,),
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
    variant_key,
):
    cursor = conn.execute(
        """
        insert into entity_stats (
            entity_id, source_id, raw_page_id, attribute_id, template_index,
            stat_name, stat_type, raw_name, value_text, value_number,
            unit, variant_key
        )
        values (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?)
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
            variant_key,
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
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                variant_key,
            ),
        )
    return stat_id
