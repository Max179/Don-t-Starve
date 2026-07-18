import sqlite3

from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_schema_can_upsert_sources_and_entities(tmp_path):
    db_path = tmp_path / "wiki.sqlite"
    conn = connect(db_path)
    init_db(conn)

    source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg/",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=18907,
        canonical_url="https://dontstarve.wiki.gg/wiki/Wilson",
        summary="Wilson is playable.",
    )

    row = conn.execute(
        "select canonical_title, kind from entities where id=?", (entity_id,)
    ).fetchone()
    assert tuple(row) == ("Wilson", "character")


def test_upsert_source_preserves_fetch_metadata_when_not_reprovided(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
        fetched_at="2026-07-16T00:00:00+00:00",
        siteinfo_json='{"statistics":{"articles":2252}}',
    )

    upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )

    row = conn.execute(
        "select fetched_at, siteinfo_json from sources where key='fandom'"
    ).fetchone()
    assert tuple(row) == (
        "2026-07-16T00:00:00+00:00",
        '{"statistics":{"articles":2252}}',
    )


def test_schema_has_auditable_raw_tables(tmp_path):
    conn = sqlite3.connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    tables = {
        row[0] for row in conn.execute("select name from sqlite_master where type='table'")
    }

    assert {
        "sources",
        "raw_pages",
        "entities",
        "entity_sources",
        "entity_attributes",
        "entity_stats",
        "entity_stat_values",
        "entity_stat_rollups",
        "entity_images",
        "page_images",
        "image_variants",
        "entity_media_assets",
        "entity_media_downloads",
        "entity_relations",
        "verification_checks",
        "official_record_mentions",
        "official_products",
        "official_product_media",
        "official_update_events",
        "official_update_media",
        "official_update_sections",
        "official_update_section_items",
        "source_catalog",
        "source_catalog_evidence",
        "community_guide_sources",
        "community_guide_topics",
        "community_guide_topic_index",
        "entity_coverage",
        "entity_variant_summary",
        "entity_profile_json",
        "entity_gameplay_edges",
        "entity_combat_profiles",
        "entity_food_profiles",
        "entity_item_profiles",
        "entity_world_profiles",
        "entity_character_profiles",
        "entity_creature_profiles",
        "entity_taxonomy",
        "run_metadata",
    }.issubset(tables)
