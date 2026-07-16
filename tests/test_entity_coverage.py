from dst_wiki_db.entity_coverage import rebuild_entity_coverage
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_coverage_summarizes_complete_and_missing_entries(tmp_path):
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
    full_id = upsert_entity(
        conn,
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Bee",
        summary="",
    )
    missing_id = upsert_entity(
        conn,
        canonical_title="Mystery",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Mystery",
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
        insert into entity_sources (
            entity_id, source_id, raw_page_id, source_title, source_pageid,
            source_url, match_method
        )
        values (?, ?, ?, 'Bee', 1, 'https://example.test/Bee', 'title_slug')
        """,
        (full_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index,
            template_name, raw_name, canonical_name, value_text
        )
        values (?, ?, ?, 0, 'Mob Infobox', 'health', 'health', '100')
        """,
        (full_id, source_id, raw_page_id),
    )
    attribute_id = conn.execute("select id from entity_attributes").fetchone()[0]
    conn.execute(
        """
        insert into entity_stats (
            entity_id, source_id, raw_page_id, attribute_id, stat_name,
            stat_type, raw_name, value_text, value_number, unit, variant_key
        )
        values (?, ?, ?, ?, 'health', 'combat', 'health', '100', 100, 'hp', '')
        """,
        (full_id, source_id, raw_page_id, attribute_id),
    )
    conn.execute(
        """
        insert into entity_images (
            entity_id, source_id, raw_page_id, image_name, role, original_url
        )
        values (?, ?, ?, 'Bee.png', 'image', 'https://example.test/Bee.png')
        """,
        (full_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into page_images (
            entity_id, source_id, raw_page_id, image_title, image_name, image_slug
        )
        values (?, ?, ?, 'File:Bee.png', 'Bee.png', 'bee-png')
        """,
        (full_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_variants (
            entity_id, source_id, raw_page_id, template_index,
            variant_key, variant_type, label, source_field
        )
        values (?, ?, ?, 0, 'dst', 'game_scope', 'DST', 'health dst')
        """,
        (full_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_categories (
            entity_id, source_id, raw_page_id, category_name, category_slug
        )
        values (?, ?, ?, 'Mobs', 'mobs')
        """,
        (full_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into official_records (
            provider, record_type, external_id, title, url, status, summary, payload_json
        )
        values ('steam', 'news', 'bee-news', 'Bee Update',
                'https://example.test/news', 'ok', '', '{}')
        """
    )
    official_record_id = conn.execute("select id from official_records").fetchone()[0]
    conn.execute(
        """
        insert into official_record_mentions (
            official_record_id, entity_id, provider, record_type, external_id,
            entity_title, mention_text, match_field, match_method, confidence,
            context_text
        )
        values (?, ?, 'steam', 'news', 'bee-news', 'Bee', 'Bee',
                'payload', 'canonical_title_phrase', 0.95, 'Bee Update')
        """,
        (official_record_id, full_id),
    )

    result = rebuild_entity_coverage(conn)

    assert result == 2
    rows = {
        row["canonical_title"]: dict(row)
        for row in conn.execute(
            """
            select canonical_title, has_source, has_attributes, has_stats,
                   has_images, has_variants, has_categories, has_official_mentions,
                   coverage_score, missing_summary
            from entity_coverage
            """
        )
    }
    assert rows["Bee"] == {
        "canonical_title": "Bee",
        "has_source": 1,
        "has_attributes": 1,
        "has_stats": 1,
        "has_images": 1,
        "has_variants": 1,
        "has_categories": 1,
        "has_official_mentions": 1,
        "coverage_score": 70,
        "missing_summary": "relations|facts|recipes",
    }
    assert rows["Mystery"] == {
        "canonical_title": "Mystery",
        "has_source": 0,
        "has_attributes": 0,
        "has_stats": 0,
        "has_images": 0,
        "has_variants": 0,
        "has_categories": 0,
        "has_official_mentions": 0,
        "coverage_score": 0,
        "missing_summary": (
            "source|attributes|stats|images|variants|categories|relations|"
            "facts|recipes|official_mentions"
        ),
    }
