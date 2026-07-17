import json
import pytest

from dst_wiki_db.entity_profiles import load_profile_json, rebuild_entity_profile_json
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_profile_json_aggregates_entity_evidence(tmp_path):
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
        summary="A harvestable bush.",
    )
    berries_id = upsert_entity(
        conn,
        canonical_title="Berries",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Berries",
        summary="",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, 'Berry Bush', 'https://example.test/Berry_Bush', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_coverage (
            entity_id, slug, canonical_title, kind, source_count,
            raw_page_count, attribute_count, stat_count, stat_value_count,
            infobox_image_count, page_image_count, variant_count,
            category_count, relation_count, resolved_relation_count,
            fact_count, resolved_fact_count, recipe_ingredient_count,
            resolved_recipe_ingredient_count, official_mention_count,
            has_source, has_attributes, has_stats, has_images,
            has_variants, has_categories, has_relations, has_facts,
            has_recipes, has_official_mentions, coverage_score,
            missing_summary
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant', 1, 1, 2, 1, 1,
                1, 1, 1, 1, 0, 0, 1, 0, 1, 0, 1,
                1, 1, 1, 1, 1, 1, 0, 1, 1, 1, 80,
                'relations')
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_media_assets (
            entity_id, source_id, raw_page_id, asset_source, image_name,
            image_slug, role, original_url, description_url, local_path,
            width, height, mime, sha1, variant_key, variant_type,
            variant_label, is_variant, is_primary, confidence
        )
        values (?, ?, ?, 'infobox', 'Berry Bush.png', 'berry-bush-png',
                'image', 'https://img.test/berry.png',
                'https://example.test/File:Berry_Bush.png',
                'data/images/berry.png', 64, 64, 'image/png', 'abc',
                'picked', 'growth_stage', 'Picked', 1, 1, 0.95)
        """,
        (entity_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, value_number, unit,
            variant_key
        )
        values (?, ?, ?, 0, 'Plant Infobox', 'regrowth time',
                'regrowth time', '3-5 days', null, 'days', '')
        """,
        (entity_id, source_id, raw_page_id),
    )
    attribute_id = conn.execute("select id from entity_attributes").fetchone()["id"]
    conn.execute(
        """
        insert into entity_stats (
            entity_id, source_id, raw_page_id, attribute_id, stat_name,
            stat_type, raw_name, value_text, value_number, unit, variant_key
        )
        values (?, ?, ?, ?, 'regrowth_time', 'world', 'regrowth time',
                '3-5 days', null, 'days', '')
        """,
        (entity_id, source_id, raw_page_id, attribute_id),
    )
    conn.execute(
        """
        insert into entity_variant_summary (
            entity_id, slug, canonical_title, kind, variant_key,
            variant_type, label, attribute_count, stat_count, fact_count,
            recipe_ingredient_count, entity_variant_count, media_asset_count,
            primary_media_asset_count, has_data, has_media, has_stats,
            has_facts, has_recipes, confidence, source_summary
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant', 'picked',
                'growth_stage', 'Picked', 1, 0, 0, 0, 1, 1, 1,
                1, 1, 0, 0, 0, 0.8, 'attributes|entity_variants|media')
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_categories (
            entity_id, source_id, raw_page_id, category_name, category_slug
        )
        values (?, ?, ?, 'Plants', 'plants')
        """,
        (entity_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_facts (
            entity_id, source_id, raw_page_id, template_index, fact_index,
            fact_type, raw_name, value_text, target_title, target_slug,
            quantity_text, quantity_number, variant_key
        )
        values (?, ?, ?, 0, 0, 'drops', 'drops', 'Berries',
                'Berries', 'berries', '1', 1, '')
        """,
        (entity_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into recipe_ingredients (
            entity_id, source_id, raw_page_id, template_index,
            ingredient_slot, ingredient_name, ingredient_slug,
            quantity_text, quantity_number, variant_key
        )
        values (?, ?, ?, 0, 1, 'Berries', 'berries', '1', 1, '')
        """,
        (entity_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into official_records (
            provider, record_type, external_id, title, url, status,
            summary, payload_json
        )
        values ('steam', 'news', '42', 'Berry Bush update',
                'https://steam.test/news/42', 'ok', 'Adds berry changes',
                '{}')
        """
    )
    official_record_id = conn.execute("select id from official_records").fetchone()["id"]
    conn.execute(
        """
        insert into official_record_mentions (
            official_record_id, entity_id, provider, record_type, external_id,
            entity_title, mention_text, match_field, match_method,
            confidence, context_text
        )
        values (?, ?, 'steam', 'news', '42', 'Berry Bush',
                'Berry Bush', 'title', 'title_phrase', 0.9,
                'Berry Bush update')
        """,
        (official_record_id, entity_id),
    )
    conn.execute(
        """
        insert into entity_gameplay_edges (
            entity_id, related_entity_id, source_id, source_table,
            source_row_id, edge_type, edge_group, direction, entity_title,
            entity_slug, entity_kind, related_title, related_slug,
            related_kind, quantity_text, quantity_number, probability_text,
            variant_key, confidence
        )
        values (?, ?, ?, 'entity_facts', 1, 'drops', 'fact', 'forward',
                'Berry Bush', 'berry-bush', 'plant', 'Berries', 'berries',
                'item', '1', 1, null, '', 0.9)
        """,
        (entity_id, berries_id, source_id),
    )
    conn.execute(
        """
        insert into entity_taxonomy (
            entity_id, slug, canonical_title, kind, taxonomy_type,
            taxonomy_key, label, confidence, evidence_source, evidence_count
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant', 'kind',
                'plant', 'Plant', 1.0, 'entities.kind', 1)
        """,
        (entity_id,),
    )

    result = rebuild_entity_profile_json(conn)

    assert result == 2
    row = conn.execute(
        """
        select entity_id, slug, canonical_title, kind, media_count,
               stat_count, variant_count, category_count, fact_count,
               recipe_ingredient_count, official_mention_count,
               relationship_count, taxonomy_count, profile_encoding,
               profile_json
        from entity_profile_json
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    with pytest.raises(json.JSONDecodeError):
        json.loads(row["profile_json"])
    profile = load_profile_json(row)
    assert dict(row) | {"profile_json": profile} == {
        "entity_id": entity_id,
        "slug": "berry-bush",
        "canonical_title": "Berry Bush",
        "kind": "plant",
        "media_count": 1,
        "stat_count": 1,
        "variant_count": 1,
        "category_count": 1,
        "fact_count": 1,
        "recipe_ingredient_count": 1,
        "official_mention_count": 1,
        "relationship_count": 1,
        "taxonomy_count": 1,
        "profile_encoding": "gzip+base64+json",
        "profile_json": profile,
    }
    assert profile["identity"] == {
        "id": entity_id,
        "slug": "berry-bush",
        "title": "Berry Bush",
        "kind": "plant",
        "canonical_url": "https://example.test/Berry_Bush",
        "summary": "A harvestable bush.",
    }
    assert profile["coverage"]["coverage_score"] == 80
    assert profile["media"][0]["image_name"] == "Berry Bush.png"
    assert profile["media"][0]["variant_key"] == "picked"
    assert profile["stats"][0]["stat_name"] == "regrowth_time"
    assert profile["variants"][0]["variant_key"] == "picked"
    assert profile["categories"] == [{"name": "Plants", "slug": "plants"}]
    assert profile["facts"][0]["fact_type"] == "drops"
    assert profile["recipes"][0]["ingredient_name"] == "Berries"
    assert profile["official_mentions"][0]["title"] == "Berry Bush update"
    assert profile["relationships"][0]["edge_type"] == "drops"
    assert profile["relationships"][0]["related_title"] == "Berries"
    assert profile["taxonomy"][0]["taxonomy_key"] == "plant"


def test_rebuild_entity_profile_json_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_entity_profile_json(conn)
    second = rebuild_entity_profile_json(conn)

    assert first == second == 0
