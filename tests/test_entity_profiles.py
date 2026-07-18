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
        insert into entity_media_profiles (
            entity_id, slug, canonical_title, kind,
            media_count, primary_count, variant_count, direct_url_count,
            file_page_only_count, missing_url_count, pending_download_count,
            downloaded_count, failed_download_count, variant_type_count,
            variant_types_text, primary_image_name, primary_role,
            primary_asset_source, primary_download_url, primary_file_page_url,
            primary_target_path, primary_local_path, primary_width,
            primary_height, primary_mime, primary_assets_json,
            variant_assets_json, has_primary_image, has_direct_url,
            has_variants, has_downloaded_media
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                1, 1, 1, 1, 0, 0, 1, 0, 0, 1, 'growth_stage',
                'Berry Bush.png', 'image', 'infobox',
                'https://img.test/berry.png',
                'https://example.test/File:Berry_Bush.png',
                'data/images/fandom/berry-bush/berry-bush-png',
                null, 64, 64, 'image/png',
                '[{"image_name":"Berry Bush.png","download_url":"https://img.test/berry.png"}]',
                '[{"image_name":"Berry Bush Picked.png","variant_key":"picked","variant_type":"growth_stage"}]',
                1, 1, 1, 0)
        """,
        (entity_id,),
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
        insert into entity_stat_rollups (
            entity_id, slug, canonical_title, kind, stat_name, stat_type,
            unit, value_min, value_max, value_count, evidence_count,
            source_count, variant_count, value_texts
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                'regrowth_time', 'world', 'days', 3, 5, 2, 1, 1, 0,
                '3-5 days')
        """,
        (entity_id,),
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
        insert into entity_link_profiles (
            entity_id, slug, canonical_title, kind, wiki_link_count,
            resolved_link_count, unresolved_link_count, unique_target_count,
            unique_resolved_target_count, unique_unresolved_target_count,
            target_kind_count, target_kind_counts_json,
            top_resolved_targets_json, top_unresolved_targets_json,
            has_wiki_links, has_resolved_links, has_unresolved_links
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant', 2, 1, 1, 2, 1,
                1, 1, '[{"kind":"item","count":1}]',
                '[{"entity_id":%d,"title":"Berries","slug":"berries","kind":"item","link_count":1,"target_title":"Berries","target_slug":"berries"}]',
                '[{"title":"Missing Thing","slug":"missing-thing","link_count":1}]',
                1, 1, 1)
        """
        % berries_id,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_prefab_profiles (
            entity_id, slug, canonical_title, kind, prefab_count,
            primary_prefab, prefab_codes_json, source_fields_text,
            category_count, code_categories_text, upgraded_prefab_count,
            reskin_prefab_count, mast_upgrade_prefab_count,
            chest_upgrade_prefab_count, merm_upgrade_prefab_count,
            has_prefabs, has_upgraded_prefab, has_reskin_prefab,
            has_mast_upgrade_prefab, has_chest_upgrade_prefab,
            has_merm_upgrade_prefab
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant', 2, 'berrybush',
                '[{"code":"berrybush","categories":["standard"],"source_id":1,"source_key":"fandom","raw_page_id":1,"source_field":"spawnCode","confidence":0.98},{"code":"berrybush_upgraded","categories":["upgraded"],"source_id":1,"source_key":"fandom","raw_page_id":1,"source_field":"spawnCode","confidence":0.98}]',
                'spawnCode', 2, 'standard | upgraded', 1, 0, 0, 0, 0,
                1, 1, 0, 0, 0, 0)
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_alias_profiles (
            entity_id, slug, canonical_title, kind, alias_count,
            title_alias_count, source_title_count, identity_key_count,
            prefab_alias_count, image_alias_count, search_key_count,
            source_count, source_keys_text, primary_search_key,
            aliases_json, search_keys_json, has_source_titles,
            has_prefab_aliases, has_image_aliases
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant', 4, 2, 1, 2,
                1, 1, 3, 1, 'fandom', 'berry-bush',
                '[{"type":"canonical_title","value":"Berry Bush","key":"berry-bush","source_key":"fandom","source_field":"entities.canonical_title","confidence":1.0},{"type":"prefab_code","value":"berrybush","key":"berrybush","source_key":"fandom","source_field":"spawnCode","confidence":0.98}]',
                '["berry-bush","berrybush","berry-bush-png"]',
                1, 1, 1)
        """,
        (entity_id,),
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
    conn.execute(
        """
        insert into entity_combat_profiles (
            entity_id, slug, canonical_title, kind,
            health_min, health_max, health_text, health_evidence_count,
            damage_min, damage_max, damage_text, damage_evidence_count,
            combat_stat_count, movement_stat_count, source_count,
            variant_count
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                100, 100, '100', 1, 10, 20, '10 / 20', 1,
                2, 0, 1, 0)
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_food_profiles (
            entity_id, slug, canonical_title, kind,
            health_min, health_max, health_text,
            hunger_min, hunger_max, hunger_text,
            sanity_min, sanity_max, sanity_text,
            spoil_days_min, spoil_days_max, spoil_text,
            stat_count, source_count, variant_count, has_restore_stats,
            has_food_value
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                1, 1, '1', 12.5, 12.5, '12.5', 0, 0, '0',
                3, 5, '3-5 days', 4, 1, 0, 1, 0)
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_item_profiles (
            entity_id, slug, canonical_title, kind,
            durability_min, durability_max, durability_text,
            stack_text, tier_min, tier_max, tier_text,
            stat_count, source_count, variant_count, has_weapon_stats,
            has_armor_stats, has_stack_stats
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                5, 10, '5 / 10', 'Does not stack', 1, 2, '1 / 2',
                3, 1, 0, 1, 0, 1)
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_world_profiles (
            entity_id, slug, canonical_title, kind,
            biome_text, spawn_code_text, renew_text,
            resources_min, resources_max, resources_text,
            perk_text, health_min, health_max, health_text,
            attribute_count, stat_count, source_count, variant_count,
            has_biome, has_spawn_code, is_renewable, has_resources,
            has_growth_data, has_combat_stats
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                'Grassland', 'berrybush | berrybush2',
                'Yes:Cave RegenerationWorld Regrowth',
                1, 3, 'Berries x1 | x3', 'Can be replanted',
                10, 20, '10 / 20', 4, 2, 1, 0,
                1, 1, 1, 1, 0, 1)
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_character_profiles (
            entity_id, slug, canonical_title, kind,
            nick_text, motto_text, birthday_text, spawn_code_text,
            perk_text, start_item_text, health_min, health_max, health_text,
            hunger_min, hunger_max, hunger_text, sanity_min, sanity_max,
            sanity_text, attribute_count, stat_count, source_count,
            variant_count, has_core_stats, has_perks, has_start_items,
            has_bio
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                'The Bush', 'Stay berry ready.', 'April 1',
                'berrybush', 'Can be replanted', 'Berries',
                10, 20, '10 / 20', 50, 75, '50 / 75',
                100, 100, '100', 6, 3, 1, 0, 1, 1, 1, 0)
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_creature_profiles (
            entity_id, slug, canonical_title, kind,
            biome_text, spawn_code_text, special_ability_text, drops_text,
            health_min, health_max, health_text, damage_min, damage_max,
            damage_text, attack_range_min, attack_range_max, attack_range_text,
            drop_edge_count, drop_related_titles, attribute_count,
            stat_count, source_count, variant_count, is_boss,
            has_combat_stats, has_movement_stats, has_sanity_effects,
            has_drop_data, has_spawn_data
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                'Forest', 'berrybush', 'Rustles ominously', 'Berries',
                10, 20, '10 / 20', 3, 5, '3 / 5', 2, 4, '2 / 4',
                1, 'Berries', 4, 3, 1, 0, 0, 1, 0, 0, 1, 0)
        """,
        (entity_id,),
    )
    conn.execute(
        """
        insert into entity_recipe_profiles (
            entity_id, slug, canonical_title, kind,
            recipe_count, ingredient_count, resolved_ingredient_count,
            unresolved_ingredient_count, used_in_count, source_count,
            variant_count, ingredient_names_text, ingredient_targets_text,
            used_in_titles_text, ingredient_summary_json,
            used_in_summary_json, has_recipe, has_resolved_ingredients,
            is_ingredient
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                1, 1, 1, 0, 1, 1, 0, 'Rot', 'Rot',
                'Compost Wrap',
                '[{"name":"Rot","quantity_number":1.0,"quantity_text":"1","slot":1,"slug":"rot","variant_key":""}]',
                '[{"entity_id":999,"kind":"item","quantity_number":1.0,"quantity_text":"1","slug":"compost-wrap","title":"Compost Wrap","variant_key":"","confidence":1.0}]',
                1, 1, 1)
        """,
        (entity_id,),
    )

    result = rebuild_entity_profile_json(conn)

    assert result == 2
    row = conn.execute(
        """
        select entity_id, slug, canonical_title, kind, attribute_count,
               media_count, stat_count, variant_count, category_count,
               fact_count, recipe_ingredient_count, official_mention_count,
               relationship_count, wiki_link_count, prefab_count, alias_count,
               taxonomy_count,
               profile_encoding,
               profile_json
        from entity_profile_json
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    assert isinstance(row["profile_json"], bytes)
    profile = load_profile_json(row)
    assert dict(row) | {"profile_json": profile} == {
        "entity_id": entity_id,
        "slug": "berry-bush",
        "canonical_title": "Berry Bush",
        "kind": "plant",
        "attribute_count": 1,
        "media_count": 1,
        "stat_count": 1,
        "variant_count": 1,
        "category_count": 1,
        "fact_count": 1,
        "recipe_ingredient_count": 1,
        "official_mention_count": 1,
        "relationship_count": 1,
        "wiki_link_count": 2,
        "prefab_count": 2,
        "alias_count": 4,
        "taxonomy_count": 1,
        "profile_encoding": "gzip+json",
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
    assert profile["counts"]["attributes"] == 1
    assert profile["attributes"][0] == {
        "id": attribute_id,
        "source_id": source_id,
        "source_key": "fandom",
        "raw_page_id": raw_page_id,
        "template_index": 0,
        "template_name": "Plant Infobox",
        "raw_name": "regrowth time",
        "canonical_name": "regrowth time",
        "value_text": "3-5 days",
        "value_number": None,
        "unit": "days",
        "variant_key": "",
    }
    assert profile["media"][0]["image_name"] == "Berry Bush.png"
    assert profile["media"][0]["variant_key"] == "picked"
    assert profile["media_profile"]["primary"]["image_name"] == "Berry Bush.png"
    assert profile["media_profile"]["counts"]["direct_url"] == 1
    assert profile["media_profile"]["variant_assets"][0]["variant_key"] == "picked"
    assert profile["stats"][0]["stat_name"] == "regrowth_time"
    assert profile["stat_rollups"][0]["stat_name"] == "regrowth_time"
    assert profile["stat_rollups"][0]["value_range"] == {"min": 3.0, "max": 5.0}
    assert profile["variants"][0]["variant_key"] == "picked"
    assert profile["categories"] == [{"name": "Plants", "slug": "plants"}]
    assert profile["facts"][0]["fact_type"] == "drops"
    assert profile["recipes"][0]["ingredient_name"] == "Berries"
    assert profile["official_mentions"][0]["title"] == "Berry Bush update"
    assert profile["relationships"][0]["edge_type"] == "drops"
    assert profile["relationships"][0]["related_title"] == "Berries"
    assert profile["link_profile"]["counts"]["wiki_links"] == 2
    assert profile["link_profile"]["counts"]["resolved_links"] == 1
    assert profile["link_profile"]["top_resolved_targets"][0]["title"] == "Berries"
    assert profile["link_profile"]["top_unresolved_targets"][0]["title"] == "Missing Thing"
    assert profile["prefab_profile"]["primary_prefab"] == "berrybush"
    assert profile["prefab_profile"]["counts"]["prefabs"] == 2
    assert profile["prefab_profile"]["counts"]["upgraded_prefabs"] == 1
    assert profile["prefab_profile"]["flags"]["has_upgraded_prefab"] is True
    assert profile["alias_profile"]["counts"]["aliases"] == 4
    assert profile["alias_profile"]["primary_search_key"] == "berry-bush"
    assert profile["alias_profile"]["search_keys"] == [
        "berry-bush",
        "berrybush",
        "berry-bush-png",
    ]
    assert profile["taxonomy"][0]["taxonomy_key"] == "plant"
    assert profile["combat_profile"]["health"]["max"] == 100.0
    assert profile["combat_profile"]["damage"]["text"] == "10 / 20"
    assert profile["food_profile"]["hunger"]["max"] == 12.5
    assert profile["food_profile"]["spoil_days"]["text"] == "3-5 days"
    assert profile["item_profile"]["durability"]["max"] == 10.0
    assert profile["item_profile"]["stack"]["text"] == "Does not stack"
    assert profile["item_profile"]["flags"]["has_stack_stats"] is True
    assert profile["world_profile"]["biome_text"] == "Grassland"
    assert profile["world_profile"]["spawn_code_text"] == "berrybush | berrybush2"
    assert profile["world_profile"]["resources"]["max"] == 3.0
    assert profile["world_profile"]["flags"]["is_renewable"] is True
    assert profile["character_profile"]["nick_text"] == "The Bush"
    assert profile["character_profile"]["health"]["max"] == 20.0
    assert profile["character_profile"]["flags"]["has_perks"] is True
    assert profile["creature_profile"]["spawn_code_text"] == "berrybush"
    assert profile["creature_profile"]["damage"]["max"] == 5.0
    assert profile["creature_profile"]["relationships"]["drop_edge_count"] == 1
    assert profile["recipe_profile"]["counts"]["ingredients"] == 1
    assert profile["recipe_profile"]["ingredients"][0]["name"] == "Rot"
    assert profile["recipe_profile"]["used_in"][0]["title"] == "Compost Wrap"


def test_rebuild_entity_profile_json_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_entity_profile_json(conn)
    second = rebuild_entity_profile_json(conn)

    assert first == second == 0
