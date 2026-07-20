from __future__ import annotations

import json
import sqlite3
from typing import Any


KIND_PRIORITY = {
    "boss": 0,
    "character": 5,
    "mob": 10,
    "plant": 15,
    "food": 20,
    "item": 25,
    "structure": 30,
    "biome": 35,
    "page": 50,
}

REQUIREMENT_PRIORITY = {
    "core_source_pair": 0,
    "media": 5,
    "primary_direct_media": 10,
    "attributes": 15,
    "stats": 20,
    "variants": 25,
    "relationships": 30,
    "official_mentions": 35,
    "categories": 40,
    "source_mapping": 45,
}

REQUIREMENT_ACTION = {
    "source_mapping": "fill_source_alignment",
    "core_source_pair": "fill_source_alignment",
    "media": "fill_media_evidence",
    "primary_direct_media": "fill_media_evidence",
    "attributes": "parse_infobox_stats",
    "stats": "parse_infobox_stats",
    "variants": "expand_variant_evidence",
    "relationships": "resolve_gameplay_relationships",
    "official_mentions": "verify_against_official_sources",
    "categories": "expand_category_taxonomy",
}


def rebuild_entity_completeness_gap_queue(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_completeness_gap_queue")
    rows = conn.execute(
        """
        select
            entity_id,
            slug,
            canonical_title,
            kind,
            readiness_score,
            readiness_status,
            source_coverage_status,
            media_status,
            source_gap_count,
            media_gap_count,
            attribute_count,
            stat_count,
            media_count,
            variant_count,
            relationship_count,
            official_mention_count,
            missing_requirements_json,
            next_actions_json
        from entity_completeness_audit
        order by entity_id
        """
    ).fetchall()
    count = 0
    for row in rows:
        missing = json.loads(str(row["missing_requirements_json"] or "[]"))
        actions = json.loads(str(row["next_actions_json"] or "[]"))
        for requirement in missing:
            detail = _detail(row, str(requirement), actions)
            conn.execute(
                """
                insert into entity_completeness_gap_queue (
                    entity_id, slug, canonical_title, kind, missing_requirement,
                    readiness_score, readiness_status, priority, next_action,
                    source_coverage_status, media_status, source_gap_count,
                    media_gap_count, attribute_count, stat_count, media_count,
                    variant_count, relationship_count, official_mention_count,
                    detail_json, detected_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, current_timestamp)
                """,
                (
                    int(row["entity_id"]),
                    str(row["slug"]),
                    str(row["canonical_title"]),
                    str(row["kind"]),
                    str(requirement),
                    int(row["readiness_score"]),
                    str(row["readiness_status"]),
                    _priority(row, str(requirement)),
                    detail["next_action"],
                    str(row["source_coverage_status"] or ""),
                    str(row["media_status"] or ""),
                    int(row["source_gap_count"]),
                    int(row["media_gap_count"]),
                    int(row["attribute_count"]),
                    int(row["stat_count"]),
                    int(row["media_count"]),
                    int(row["variant_count"]),
                    int(row["relationship_count"]),
                    int(row["official_mention_count"]),
                    json.dumps(detail, ensure_ascii=False, sort_keys=True),
                ),
            )
            count += 1
    conn.commit()
    return count


def _priority(row: sqlite3.Row, requirement: str) -> int:
    kind = KIND_PRIORITY.get(str(row["kind"]), 45)
    requirement_score = REQUIREMENT_PRIORITY.get(requirement, 45)
    score_bonus = max(0, 100 - int(row["readiness_score"])) // 10
    return kind + requirement_score + score_bonus


def _detail(
    row: sqlite3.Row, requirement: str, actions: list[dict[str, Any]]
) -> dict[str, Any]:
    next_action = REQUIREMENT_ACTION.get(requirement, "review_entity")
    action_detail = next(
        (action for action in actions if action.get("action") == next_action),
        {},
    )
    return {
        "missing_requirement": requirement,
        "next_action": next_action,
        "action_detail": action_detail,
        "readiness": {
            "score": int(row["readiness_score"]),
            "status": str(row["readiness_status"]),
        },
        "source": {
            "status": str(row["source_coverage_status"] or ""),
            "gap_count": int(row["source_gap_count"]),
        },
        "media": {
            "status": str(row["media_status"] or ""),
            "gap_count": int(row["media_gap_count"]),
            "media_count": int(row["media_count"]),
        },
    }
