from dst_wiki_db.prefab_profiles import rebuild_entity_prefab_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_prefab_profiles_groups_spawn_codes_and_upgrade_flags(tmp_path):
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
    chest_id = upsert_entity(
        conn,
        canonical_title="Chest",
        kind="structure",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Chest",
        summary="",
    )
    _key(conn, chest_id, source_id, "treasurechest", "spawnCode")
    _key(conn, chest_id, source_id, "treasurechest_upgraded", "spawnCode")
    _key(conn, chest_id, source_id, "chestupgrade_stacksize", "spawnCode")

    result = rebuild_entity_prefab_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select prefab_count, primary_prefab, source_fields_text,
               category_count, code_categories_text, upgraded_prefab_count,
               chest_upgrade_prefab_count, has_prefabs,
               has_upgraded_prefab, has_chest_upgrade_prefab
        from entity_prefab_profiles
        """
    ).fetchone()
    assert row["prefab_count"] == 3
    assert row["primary_prefab"] == "treasurechest"
    assert row["source_fields_text"] == "spawnCode"
    assert row["category_count"] == 3
    assert row["code_categories_text"] == "chest_upgrade | standard | upgraded"
    assert row["upgraded_prefab_count"] == 2
    assert row["chest_upgrade_prefab_count"] == 1
    assert row["has_prefabs"] == 1
    assert row["has_upgraded_prefab"] == 1
    assert row["has_chest_upgrade_prefab"] == 1


def test_rebuild_entity_prefab_profiles_is_idempotent_without_spawn_codes(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    assert rebuild_entity_prefab_profiles(conn) == 0
    assert rebuild_entity_prefab_profiles(conn) == 0


def _key(conn, entity_id, source_id, key_value, source_field):
    conn.execute(
        """
        insert into entity_identity_keys (
            entity_id, source_id, raw_page_id, key_type, key_value,
            source_field, confidence
        )
        values (?, ?, null, 'spawn_code', ?, ?, 0.98)
        """,
        (entity_id, source_id, key_value, source_field),
    )
