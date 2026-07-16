from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.variant_summary import rebuild_entity_variant_summary


def test_rebuild_entity_variant_summary_merges_data_and_media_evidence(tmp_path):
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
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Bee",
        summary="",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, 'Bee', 'https://example.test/Bee', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()[0]
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, variant_key
        )
        values (?, ?, ?, 0, 'Mob Infobox', 'health dst', 'health',
                '100', 'dst')
        """,
        (entity_id, source_id, raw_page_id),
    )
    attribute_id = conn.execute("select id from entity_attributes").fetchone()[0]
    conn.execute(
        """
        insert into entity_stats (
            entity_id, source_id, raw_page_id, attribute_id, stat_name,
            stat_type, raw_name, value_text, value_number, unit, variant_key
        )
        values (?, ?, ?, ?, 'health', 'combat', 'health dst',
                '100', 100, 'hp', 'dst')
        """,
        (entity_id, source_id, raw_page_id, attribute_id),
    )
    conn.execute(
        """
        insert into entity_variants (
            entity_id, source_id, raw_page_id, template_index,
            variant_key, variant_type, label, source_field
        )
        values (?, ?, ?, 0, 'dst', 'game_scope',
                'Don''t Starve Together', 'health dst')
        """,
        (entity_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_media_assets (
            entity_id, source_id, raw_page_id, asset_source, image_name,
            image_slug, role, variant_key, variant_type, variant_label,
            is_variant, is_primary, confidence
        )
        values (?, ?, ?, 'infobox', 'Bee DST.png', 'bee-dst-png',
                'image', 'dst', 'game_scope', 'Don''t Starve Together',
                1, 1, 1.0)
        """,
        (entity_id, source_id, raw_page_id),
    )

    result = rebuild_entity_variant_summary(conn)

    assert result == 1
    row = conn.execute(
        """
        select entity_id, variant_key, variant_type, label, attribute_count,
               stat_count, entity_variant_count, media_asset_count,
               primary_media_asset_count, has_data, has_media, has_stats,
               confidence, source_summary
        from entity_variant_summary
        """
    ).fetchone()
    assert dict(row) == {
        "entity_id": entity_id,
        "variant_key": "dst",
        "variant_type": "game_scope",
        "label": "Don't Starve Together",
        "attribute_count": 1,
        "stat_count": 1,
        "entity_variant_count": 1,
        "media_asset_count": 1,
        "primary_media_asset_count": 1,
        "has_data": 1,
        "has_media": 1,
        "has_stats": 1,
        "confidence": 1.0,
        "source_summary": "attributes|stats|entity_variants|media",
    }


def test_rebuild_entity_variant_summary_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_entity_variant_summary(conn)
    second = rebuild_entity_variant_summary(conn)

    assert first == second == 0
