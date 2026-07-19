#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.facts import rebuild_entity_facts
from dst_wiki_db.alias_profiles import rebuild_entity_alias_profiles
from dst_wiki_db.categories import rebuild_entity_categories
from dst_wiki_db.character_profiles import rebuild_entity_character_profiles
from dst_wiki_db.combat_profiles import rebuild_entity_combat_profiles
from dst_wiki_db.creature_profiles import rebuild_entity_creature_profiles
from dst_wiki_db.entity_coverage import rebuild_entity_coverage
from dst_wiki_db.food_profiles import rebuild_entity_food_profiles
from dst_wiki_db.gameplay_edges import rebuild_entity_gameplay_edges
from dst_wiki_db.image_variants import rebuild_image_variants
from dst_wiki_db.identity import rebuild_identity_keys
from dst_wiki_db.item_profiles import rebuild_entity_item_profiles
from dst_wiki_db.link_profiles import rebuild_entity_link_profiles
from dst_wiki_db.media_assets import rebuild_entity_media_assets
from dst_wiki_db.media_coverage import rebuild_entity_media_coverage
from dst_wiki_db.media_downloads import rebuild_entity_media_downloads
from dst_wiki_db.media_profiles import rebuild_entity_media_profiles
from dst_wiki_db.official_mentions import rebuild_official_record_mentions
from dst_wiki_db.official_products import rebuild_official_products
from dst_wiki_db.official_updates import rebuild_official_update_events
from dst_wiki_db.official_update_sections import rebuild_official_update_sections
from dst_wiki_db.entity_profiles import rebuild_entity_profile_json
from dst_wiki_db.page_images import rebuild_page_images
from dst_wiki_db.prefab_profiles import rebuild_entity_prefab_profiles
from dst_wiki_db.recipes import rebuild_recipe_ingredients
from dst_wiki_db.recipe_profiles import rebuild_entity_recipe_profiles
from dst_wiki_db.source_catalog import rebuild_source_catalog
from dst_wiki_db.source_topic_probes import relink_source_topic_probes
from dst_wiki_db.source_page_gaps import rebuild_source_page_gaps
from dst_wiki_db.source_page_index import rebuild_source_page_entity_matches
from dst_wiki_db.source_coverage import rebuild_entity_source_coverage
from dst_wiki_db.source_gap_queue import rebuild_entity_source_gap_queue
from dst_wiki_db.source_profiles import rebuild_entity_source_profiles
from dst_wiki_db.stat_rollups import rebuild_entity_stat_rollups
from dst_wiki_db.stats import rebuild_entity_stat_values, rebuild_entity_stats
from dst_wiki_db.taxonomy import rebuild_entity_taxonomy
from dst_wiki_db.targets import rebuild_entity_targets
from dst_wiki_db.variant_summary import rebuild_entity_variant_summary
from dst_wiki_db.variants import rebuild_entity_variants
from dst_wiki_db.world_profiles import rebuild_entity_world_profiles
from dst_wiki_db.schema import connect, init_db


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Rebuild derived tables from parsed wiki attributes.")
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--report", type=Path, default=Path("reports/derived_tables.json"))
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    recipe_count = rebuild_recipe_ingredients(conn)
    stat_count = rebuild_entity_stats(conn)
    stat_value_count = rebuild_entity_stat_values(conn)
    stat_rollup_count = rebuild_entity_stat_rollups(conn)
    fact_count = rebuild_entity_facts(conn)
    variant_count = rebuild_entity_variants(conn)
    category_count = rebuild_entity_categories(conn)
    page_image_count = rebuild_page_images(conn)
    image_variant_count = rebuild_image_variants(conn)
    media_asset_count = rebuild_entity_media_assets(conn)
    media_download_count = rebuild_entity_media_downloads(conn)
    media_profile_count = rebuild_entity_media_profiles(conn)
    media_coverage_counts = rebuild_entity_media_coverage(conn)
    official_mention_count = rebuild_official_record_mentions(conn)
    official_product_counts = rebuild_official_products(conn)
    official_update_counts = rebuild_official_update_events(conn)
    official_update_section_counts = rebuild_official_update_sections(conn)
    source_catalog_counts = rebuild_source_catalog(conn)
    source_topic_probe_count = relink_source_topic_probes(conn)
    identity_count = rebuild_identity_keys(conn)
    target_counts = rebuild_entity_targets(conn)
    link_profile_count = rebuild_entity_link_profiles(conn)
    prefab_profile_count = rebuild_entity_prefab_profiles(conn)
    alias_profile_counts = rebuild_entity_alias_profiles(conn)
    source_page_match_count = rebuild_source_page_entity_matches(conn)
    entity_source_profile_count = rebuild_entity_source_profiles(conn)
    entity_source_coverage_count = rebuild_entity_source_coverage(conn)
    entity_source_gap_queue_count = rebuild_entity_source_gap_queue(conn)
    source_page_gap_count = rebuild_source_page_gaps(conn)
    gameplay_edge_count = rebuild_entity_gameplay_edges(conn)
    combat_profile_count = rebuild_entity_combat_profiles(conn)
    food_profile_count = rebuild_entity_food_profiles(conn)
    item_profile_count = rebuild_entity_item_profiles(conn)
    world_profile_count = rebuild_entity_world_profiles(conn)
    character_profile_count = rebuild_entity_character_profiles(conn)
    creature_profile_count = rebuild_entity_creature_profiles(conn)
    recipe_profile_count = rebuild_entity_recipe_profiles(conn)
    variant_summary_count = rebuild_entity_variant_summary(conn)
    coverage_count = rebuild_entity_coverage(conn)
    taxonomy_count = rebuild_entity_taxonomy(conn)
    profile_count = rebuild_entity_profile_json(conn)
    payload = {
        "recipe_ingredients": recipe_count,
        "recipe_ingredient_targets": target_counts["recipe_ingredient_targets"],
        "entity_stats": stat_count,
        "entity_stat_values": stat_value_count,
        "entity_stat_rollups": stat_rollup_count,
        "entity_facts": fact_count,
        "entity_fact_targets": target_counts["entity_fact_targets"],
        "entity_relation_targets": target_counts["entity_relation_targets"],
        "entity_gameplay_edges": gameplay_edge_count,
        "entity_combat_profiles": combat_profile_count,
        "entity_food_profiles": food_profile_count,
        "entity_item_profiles": item_profile_count,
        "entity_world_profiles": world_profile_count,
        "entity_character_profiles": character_profile_count,
        "entity_creature_profiles": creature_profile_count,
        "entity_recipe_profiles": recipe_profile_count,
        "entity_variants": variant_count,
        "entity_categories": category_count,
        "page_images": page_image_count,
        "image_variants": image_variant_count,
        "entity_media_assets": media_asset_count,
        "entity_media_downloads": media_download_count,
        "entity_media_profiles": media_profile_count,
        "entity_media_coverage": media_coverage_counts["entity_media_coverage"],
        "entity_media_gap_queue": media_coverage_counts["entity_media_gap_queue"],
        "official_record_mentions": official_mention_count,
        "official_products": official_product_counts["official_products"],
        "official_product_media": official_product_counts["official_product_media"],
        "official_update_events": official_update_counts["official_update_events"],
        "official_update_media": official_update_counts["official_update_media"],
        "official_update_sections": official_update_section_counts[
            "official_update_sections"
        ],
        "official_update_section_items": official_update_section_counts[
            "official_update_section_items"
        ],
        "source_catalog": source_catalog_counts["source_catalog"],
        "source_catalog_evidence": source_catalog_counts[
            "source_catalog_evidence"
        ],
        "source_topic_probes": source_topic_probe_count,
        "entity_identity_keys": identity_count,
        "entity_link_profiles": link_profile_count,
        "entity_prefab_profiles": prefab_profile_count,
        "entity_aliases": alias_profile_counts["entity_aliases"],
        "entity_alias_profiles": alias_profile_counts["entity_alias_profiles"],
        "source_page_entity_matches": source_page_match_count,
        "entity_source_profiles": entity_source_profile_count,
        "entity_source_coverage": entity_source_coverage_count,
        "entity_source_gap_queue": entity_source_gap_queue_count,
        "source_page_gaps": source_page_gap_count,
        "entity_variant_summary": variant_summary_count,
        "entity_coverage": coverage_count,
        "entity_taxonomy": taxonomy_count,
        "entity_profile_json": profile_count,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
