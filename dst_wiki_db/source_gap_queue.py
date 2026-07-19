from __future__ import annotations

import json
import sqlite3


KIND_PRIORITY = {
    "boss": 5,
    "character": 10,
    "mob": 15,
    "plant": 20,
    "food": 25,
    "item": 30,
    "structure": 35,
    "biome": 40,
    "page": 60,
}


def rebuild_entity_source_gap_queue(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_source_gap_queue")
    rows = conn.execute(
        """
        select
            entity_id,
            slug,
            canonical_title,
            kind,
            source_profile_count,
            matched_page_count,
            source_keys_json,
            missing_sources_json,
            coverage_status,
            best_source_key,
            best_page_title,
            best_page_url
        from entity_source_coverage
        order by entity_id
        """
    ).fetchall()
    count = 0
    for row in rows:
        missing_sources = json.loads(str(row["missing_sources_json"] or "[]"))
        for missing_source_key in missing_sources:
            conn.execute(
                """
                insert into entity_source_gap_queue (
                    entity_id, slug, canonical_title, kind, missing_source_key,
                    coverage_status, priority, source_profile_count,
                    matched_page_count, available_source_keys_json,
                    best_available_source_key, best_available_page_title,
                    best_available_page_url, gap_reason, detected_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'missing_core_source_profile', current_timestamp)
                """,
                (
                    int(row["entity_id"]),
                    str(row["slug"]),
                    str(row["canonical_title"]),
                    str(row["kind"]),
                    str(missing_source_key),
                    str(row["coverage_status"]),
                    _priority(row, str(missing_source_key)),
                    int(row["source_profile_count"]),
                    int(row["matched_page_count"]),
                    str(row["source_keys_json"] or "[]"),
                    str(row["best_source_key"] or ""),
                    str(row["best_page_title"] or ""),
                    str(row["best_page_url"] or ""),
                ),
            )
            count += 1
    conn.commit()
    return count


def _priority(row: sqlite3.Row, missing_source_key: str) -> int:
    kind_score = KIND_PRIORITY.get(str(row["kind"]), 50)
    source_penalty = 0 if missing_source_key == "wiki.gg" else 5
    evidence_bonus = 0 if int(row["matched_page_count"]) > 0 else 20
    return kind_score + source_penalty + evidence_bonus
