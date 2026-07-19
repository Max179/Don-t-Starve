from __future__ import annotations

import sqlite3
from typing import Dict, List


COUNT_TABLES = [
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
    "entity_media_profiles",
    "entity_media_coverage",
    "entity_media_gap_queue",
    "entity_relations",
    "entity_link_profiles",
    "entity_prefab_profiles",
    "entity_aliases",
    "entity_alias_profiles",
    "verification_checks",
    "official_records",
    "official_record_mentions",
    "official_products",
    "official_product_media",
    "official_update_events",
    "official_update_media",
    "official_update_sections",
    "official_update_section_items",
    "source_audits",
    "source_catalog",
    "source_catalog_evidence",
    "source_topic_probes",
    "source_page_index",
    "source_page_entity_matches",
    "entity_source_profiles",
    "entity_source_coverage",
    "entity_source_gap_queue",
    "source_page_gaps",
    "community_guide_sources",
    "community_guide_topics",
    "community_guide_topic_index",
    "recipe_ingredients",
    "recipe_ingredient_targets",
    "entity_facts",
    "entity_fact_targets",
    "entity_gameplay_edges",
    "entity_combat_profiles",
    "entity_food_profiles",
    "entity_item_profiles",
    "entity_world_profiles",
    "entity_character_profiles",
    "entity_creature_profiles",
    "entity_recipe_profiles",
    "entity_variants",
    "entity_variant_summary",
    "entity_categories",
    "entity_identity_keys",
    "cross_source_matches",
    "entity_coverage",
    "entity_taxonomy",
    "entity_profile_json",
]


def database_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for table in COUNT_TABLES:
        row = conn.execute(f"select count(*) as count from {table}").fetchone()
        counts[table] = int(row["count"] if hasattr(row, "keys") else row[0])
    return counts


def sample_entities(conn: sqlite3.Connection, *, limit: int = 10) -> List[dict]:
    rows = conn.execute(
        """
        select
            e.canonical_title,
            e.kind,
            count(distinct a.id) as attribute_count,
            count(distinct i.id) as image_count
        from entities e
        left join entity_attributes a on a.entity_id = e.id
        left join entity_images i on i.entity_id = e.id
        group by e.id
        order by e.canonical_title
        limit ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "canonical_title": row["canonical_title"],
            "kind": row["kind"],
            "attribute_count": int(row["attribute_count"]),
            "image_count": int(row["image_count"]),
        }
        for row in rows
    ]
