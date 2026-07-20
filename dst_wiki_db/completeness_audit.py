from __future__ import annotations

import json
import sqlite3
from typing import Any


REQUIREMENTS = (
    ("source_mapping", "has_source_mapping"),
    ("core_source_pair", "has_core_source_pair"),
    ("attributes", "has_attributes"),
    ("stats", "has_stats"),
    ("media", "has_media"),
    ("primary_direct_media", "has_primary_direct_media"),
    ("variants", "has_variants"),
    ("categories", "has_categories"),
    ("relationships", "has_relationships"),
    ("official_mentions", "has_official_mentions"),
)


def rebuild_entity_completeness_audit(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_completeness_audit")
    rows = conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            coalesce(ec.coverage_score, 0) as evidence_coverage_score,
            coalesce(ec.attribute_count, 0) as attribute_count,
            coalesce(ec.stat_count, 0) as stat_count,
            coalesce(ec.stat_value_count, 0) as stat_value_count,
            coalesce(ec.variant_count, 0) as variant_count,
            coalesce(ec.category_count, 0) as category_count,
            coalesce(ec.resolved_relation_count, 0) as resolved_relation_count,
            coalesce(ec.resolved_fact_count, 0) as resolved_fact_count,
            coalesce(ec.resolved_recipe_ingredient_count, 0) as resolved_recipe_ingredient_count,
            coalesce(ec.official_mention_count, 0) as official_mention_count,
            coalesce(ec.has_source, 0) as has_source,
            coalesce(ec.has_attributes, 0) as has_attributes,
            coalesce(ec.has_stats, 0) as has_stats,
            coalesce(ec.has_variants, 0) as has_variants,
            coalesce(ec.has_categories, 0) as has_categories,
            coalesce(ec.has_relations, 0) as has_relations,
            coalesce(ec.has_facts, 0) as has_facts,
            coalesce(ec.has_recipes, 0) as has_recipes,
            coalesce(ec.has_official_mentions, 0) as has_official_mentions,
            coalesce(esc.coverage_status, '') as source_coverage_status,
            coalesce(esc.source_profile_count, 0) as source_profile_count,
            coalesce(esc.matched_page_count, 0) as matched_source_page_count,
            coalesce(esc.has_both_core_wikis, 0) as has_both_core_wikis,
            coalesce(emc.media_status, '') as media_status,
            coalesce(emc.media_count, 0) as media_count,
            coalesce(emc.variant_count, 0) as variant_media_count,
            coalesce(emc.has_media_profile, 0) as has_media_profile,
            coalesce(emc.has_primary_image, 0) as has_primary_image,
            coalesce(emc.has_direct_url, 0) as has_direct_url,
            coalesce(esg.source_gap_count, 0) as source_gap_count,
            coalesce(emg.media_gap_count, 0) as media_gap_count
        from entities e
        left join entity_coverage ec on ec.entity_id = e.id
        left join entity_source_coverage esc on esc.entity_id = e.id
        left join entity_media_coverage emc on emc.entity_id = e.id
        left join (
            select entity_id, count(*) as source_gap_count
            from entity_source_gap_queue
            group by entity_id
        ) esg on esg.entity_id = e.id
        left join (
            select entity_id, count(*) as media_gap_count
            from entity_media_gap_queue
            group by entity_id
        ) emg on emg.entity_id = e.id
        order by e.id
        """
    ).fetchall()
    count = 0
    for row in rows:
        flags = _flags(row)
        missing = [
            requirement
            for requirement, flag_name in REQUIREMENTS
            if not flags[flag_name]
        ]
        score = sum(flags.values()) * 10
        next_actions = _next_actions(row, missing)
        conn.execute(
            """
            insert into entity_completeness_audit (
                entity_id, slug, canonical_title, kind, readiness_score,
                readiness_status, source_coverage_status, media_status,
                evidence_coverage_score, source_gap_count, media_gap_count,
                source_profile_count, matched_source_page_count, media_count,
                variant_media_count, attribute_count, stat_count,
                stat_value_count, variant_count, category_count,
                relationship_count, official_mention_count, has_source_mapping,
                has_core_source_pair, has_attributes, has_stats, has_media,
                has_primary_direct_media, has_variants, has_categories,
                has_relationships, has_official_mentions,
                missing_requirements_json, next_actions_json, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                int(row["entity_id"]),
                str(row["slug"]),
                str(row["canonical_title"]),
                str(row["kind"]),
                score,
                _readiness_status(score, missing),
                str(row["source_coverage_status"] or ""),
                str(row["media_status"] or ""),
                int(row["evidence_coverage_score"]),
                int(row["source_gap_count"]),
                int(row["media_gap_count"]),
                int(row["source_profile_count"]),
                int(row["matched_source_page_count"]),
                int(row["media_count"]),
                int(row["variant_media_count"]),
                int(row["attribute_count"]),
                int(row["stat_count"]),
                int(row["stat_value_count"]),
                int(row["variant_count"]),
                int(row["category_count"]),
                _relationship_count(row),
                int(row["official_mention_count"]),
                flags["has_source_mapping"],
                flags["has_core_source_pair"],
                flags["has_attributes"],
                flags["has_stats"],
                flags["has_media"],
                flags["has_primary_direct_media"],
                flags["has_variants"],
                flags["has_categories"],
                flags["has_relationships"],
                flags["has_official_mentions"],
                json.dumps(missing, ensure_ascii=False),
                json.dumps(next_actions, ensure_ascii=False, sort_keys=True),
            ),
        )
        count += 1
    conn.commit()
    return count


def _flags(row: sqlite3.Row) -> dict[str, int]:
    return {
        "has_source_mapping": int(row["has_source"]),
        "has_core_source_pair": int(row["has_both_core_wikis"]),
        "has_attributes": int(row["has_attributes"]),
        "has_stats": int(row["has_stats"]),
        "has_media": int(row["has_media_profile"]),
        "has_primary_direct_media": int(
            int(row["has_primary_image"]) and int(row["has_direct_url"])
        ),
        "has_variants": int(row["has_variants"]),
        "has_categories": int(row["has_categories"]),
        "has_relationships": int(
            int(row["has_relations"]) or int(row["has_facts"]) or int(row["has_recipes"])
        ),
        "has_official_mentions": int(row["has_official_mentions"]),
    }


def _relationship_count(row: sqlite3.Row) -> int:
    return (
        int(row["resolved_relation_count"])
        + int(row["resolved_fact_count"])
        + int(row["resolved_recipe_ingredient_count"])
    )


def _readiness_status(score: int, missing: list[str]) -> str:
    if not missing:
        return "complete_profile"
    if score >= 80:
        return "strong_profile"
    if score >= 60:
        return "usable_profile"
    if score >= 40:
        return "partial_profile"
    return "sparse_profile"


def _next_actions(row: sqlite3.Row, missing: list[str]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if "source_mapping" in missing or "core_source_pair" in missing:
        actions.append(
            {
                "action": "fill_source_alignment",
                "status": str(row["source_coverage_status"] or ""),
                "gap_count": int(row["source_gap_count"]),
            }
        )
    if "media" in missing or "primary_direct_media" in missing:
        actions.append(
            {
                "action": "fill_media_evidence",
                "status": str(row["media_status"] or ""),
                "gap_count": int(row["media_gap_count"]),
            }
        )
    if "attributes" in missing or "stats" in missing:
        actions.append(
            {
                "action": "parse_infobox_stats",
                "attribute_count": int(row["attribute_count"]),
                "stat_count": int(row["stat_count"]),
            }
        )
    if "variants" in missing:
        actions.append(
            {
                "action": "expand_variant_evidence",
                "variant_count": int(row["variant_count"]),
                "variant_media_count": int(row["variant_media_count"]),
            }
        )
    if "relationships" in missing:
        actions.append(
            {
                "action": "resolve_gameplay_relationships",
                "relationship_count": _relationship_count(row),
            }
        )
    if "official_mentions" in missing:
        actions.append(
            {
                "action": "verify_against_official_sources",
                "official_mention_count": int(row["official_mention_count"]),
            }
        )
    return actions
