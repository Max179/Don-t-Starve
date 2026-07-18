import json

from dst_wiki_db.alias_profiles import rebuild_entity_alias_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_alias_profiles_collects_titles_prefabs_and_images(tmp_path):
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
    entity_id = upsert_entity(
        conn,
        canonical_title="Berry Bush",
        kind="plant",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Berry_Bush",
        summary="",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, 'Berry Bushes', 'https://example.test/Berry_Bushes',
                '', '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_sources (
            entity_id, source_id, raw_page_id, source_title, source_pageid,
            source_url, match_method, confidence
        )
        values (?, ?, ?, 'Berry Bushes', 1,
                'https://example.test/Berry_Bushes', 'title', 0.9)
        """,
        (entity_id, source_id, raw_page_id),
    )
    _key(conn, entity_id, source_id, raw_page_id, "title_slug", "berry-bush", "entities.slug", 0.7)
    _key(conn, entity_id, source_id, raw_page_id, "spawn_code", "berrybush", "spawnCode", 0.98)
    _key(conn, entity_id, source_id, raw_page_id, "spawn_code", "berrybush2", "spawnCode2", 0.98)
    _key(
        conn,
        entity_id,
        source_id,
        raw_page_id,
        "image_name",
        "Berry Bush DS.png",
        "entity_images.image_name",
        0.75,
    )
    _key(conn, entity_id, source_id, raw_page_id, "image_sha1", "abc123", "entity_images.sha1", 0.95)

    result = rebuild_entity_alias_profiles(conn)

    assert result == {"entity_aliases": 8, "entity_alias_profiles": 1}
    row = conn.execute(
        """
        select alias_count, title_alias_count, source_title_count,
               identity_key_count, prefab_alias_count, image_alias_count,
               search_key_count, source_count, source_keys_text,
               primary_search_key, aliases_json, search_keys_json,
               has_source_titles, has_prefab_aliases, has_image_aliases
        from entity_alias_profiles
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    assert row["alias_count"] == 8
    assert row["title_alias_count"] == 4
    assert row["source_title_count"] == 1
    assert row["identity_key_count"] == 6
    assert row["prefab_alias_count"] == 2
    assert row["image_alias_count"] == 2
    assert row["search_key_count"] == 6
    assert row["source_count"] == 1
    assert row["source_keys_text"] == "fandom"
    assert row["primary_search_key"] == "berry-bush"
    assert row["has_source_titles"] == 1
    assert row["has_prefab_aliases"] == 1
    assert row["has_image_aliases"] == 1
    aliases = json.loads(row["aliases_json"])
    assert {alias["type"] for alias in aliases} == {
        "canonical_title",
        "canonical_slug",
        "source_title",
        "source_slug",
        "prefab_code",
        "image_name",
        "image_stem",
    }
    assert set(json.loads(row["search_keys_json"])) == {
        "berry-bush",
        "berry-bushes",
        "berrybush",
        "berrybush2",
        "berry-bush-ds",
        "berry-bush-ds-png",
    }
    assert (
        conn.execute(
            "select count(*) from entity_aliases where alias_key = 'berrybush'"
        ).fetchone()[0]
        == 1
    )


def test_rebuild_entity_alias_profiles_is_idempotent_without_entities(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    assert rebuild_entity_alias_profiles(conn) == {
        "entity_aliases": 0,
        "entity_alias_profiles": 0,
    }
    assert rebuild_entity_alias_profiles(conn) == {
        "entity_aliases": 0,
        "entity_alias_profiles": 0,
    }


def _key(conn, entity_id, source_id, raw_page_id, key_type, key_value, source_field, confidence):
    conn.execute(
        """
        insert into entity_identity_keys (
            entity_id, source_id, raw_page_id, key_type, key_value,
            source_field, confidence
        )
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, source_id, raw_page_id, key_type, key_value, source_field, confidence),
    )
