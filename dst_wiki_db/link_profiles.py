from __future__ import annotations

import json
import sqlite3
from typing import Any


TOP_TARGET_LIMIT = 5


def rebuild_entity_link_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_link_profiles")
    rows = conn.execute(
        """
        select
            er.entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            er.target_title,
            er.target_slug,
            er.target_entity_id,
            target.slug as resolved_slug,
            target.canonical_title as resolved_title,
            target.kind as resolved_kind,
            count(*) as link_count
        from entity_relations er
        join entities e on e.id = er.entity_id
        left join entities target on target.id = er.target_entity_id
        group by
            er.entity_id,
            er.target_slug,
            er.target_entity_id,
            er.target_title
        order by e.slug, link_count desc, er.target_slug
        """
    ).fetchall()
    buckets: dict[int, dict[str, Any]] = {}
    for row in rows:
        bucket = _bucket(buckets, row)
        link_count = int(row["link_count"])
        bucket["wiki_link_count"] += link_count
        bucket["unique_target_count"] += 1
        if row["target_entity_id"] is None:
            bucket["unresolved_link_count"] += link_count
            bucket["unique_unresolved_target_count"] += 1
            bucket["unresolved_targets"].append(_unresolved_target(row, link_count))
            continue
        bucket["resolved_link_count"] += link_count
        bucket["unique_resolved_target_count"] += 1
        resolved_kind = str(row["resolved_kind"] or "")
        if resolved_kind:
            bucket["target_kind_counts"][resolved_kind] = (
                int(bucket["target_kind_counts"].get(resolved_kind, 0)) + link_count
            )
        bucket["resolved_targets"].append(_resolved_target(row, link_count))

    count = 0
    for bucket in buckets.values():
        identity = bucket["identity"]
        resolved_targets = _top_targets(bucket["resolved_targets"])
        unresolved_targets = _top_targets(bucket["unresolved_targets"])
        kind_counts = [
            {"kind": kind, "count": count}
            for kind, count in sorted(
                bucket["target_kind_counts"].items(),
                key=lambda item: (-int(item[1]), item[0]),
            )
        ]
        conn.execute(
            """
            insert into entity_link_profiles (
                entity_id, slug, canonical_title, kind,
                wiki_link_count, resolved_link_count, unresolved_link_count,
                unique_target_count, unique_resolved_target_count,
                unique_unresolved_target_count, target_kind_count,
                target_kind_counts_json, top_resolved_targets_json,
                top_unresolved_targets_json, has_wiki_links,
                has_resolved_links, has_unresolved_links, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["slug"]),
                str(identity["canonical_title"]),
                str(identity["kind"]),
                int(bucket["wiki_link_count"]),
                int(bucket["resolved_link_count"]),
                int(bucket["unresolved_link_count"]),
                int(bucket["unique_target_count"]),
                int(bucket["unique_resolved_target_count"]),
                int(bucket["unique_unresolved_target_count"]),
                len(kind_counts),
                json.dumps(kind_counts, ensure_ascii=False, sort_keys=True),
                json.dumps(resolved_targets, ensure_ascii=False, sort_keys=True),
                json.dumps(unresolved_targets, ensure_ascii=False, sort_keys=True),
                int(bucket["wiki_link_count"] > 0),
                int(bucket["resolved_link_count"] > 0),
                int(bucket["unresolved_link_count"] > 0),
            ),
        )
        count += 1
    conn.commit()
    return count


def _bucket(grouped: dict[int, dict[str, Any]], row: sqlite3.Row) -> dict[str, Any]:
    entity_id = int(row["entity_id"])
    return grouped.setdefault(
        entity_id,
        {
            "identity": row,
            "wiki_link_count": 0,
            "resolved_link_count": 0,
            "unresolved_link_count": 0,
            "unique_target_count": 0,
            "unique_resolved_target_count": 0,
            "unique_unresolved_target_count": 0,
            "target_kind_counts": {},
            "resolved_targets": [],
            "unresolved_targets": [],
        },
    )


def _resolved_target(row: sqlite3.Row, link_count: int) -> dict[str, Any]:
    return {
        "entity_id": int(row["target_entity_id"]),
        "title": str(row["resolved_title"] or row["target_title"]),
        "slug": str(row["resolved_slug"] or row["target_slug"]),
        "kind": str(row["resolved_kind"] or ""),
        "link_count": link_count,
        "target_title": str(row["target_title"]),
        "target_slug": str(row["target_slug"]),
    }


def _unresolved_target(row: sqlite3.Row, link_count: int) -> dict[str, Any]:
    return {
        "title": str(row["target_title"]),
        "slug": str(row["target_slug"]),
        "link_count": link_count,
    }


def _top_targets(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        targets,
        key=lambda item: (-int(item["link_count"]), str(item["slug"]), str(item["title"])),
    )[:TOP_TARGET_LIMIT]
