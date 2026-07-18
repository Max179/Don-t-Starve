from __future__ import annotations

import json
import sqlite3
from typing import Any


PAGE_LIMIT = 12


def rebuild_entity_source_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_source_profiles")
    rows = conn.execute(
        """
        select
            spm.entity_id,
            spm.source_key,
            spm.source_pageid,
            spm.source_title,
            spm.source_title_slug,
            spm.entity_slug,
            spm.entity_title,
            spm.entity_kind,
            spm.match_method,
            spm.confidence,
            spi.page_url
        from source_page_entity_matches spm
        join source_page_index spi on spi.id = spm.source_page_index_id
        order by spm.source_key, spm.entity_slug, spm.confidence desc, spm.source_title
        """
    ).fetchall()
    buckets: dict[tuple[int, str], dict[str, Any]] = {}
    for row in rows:
        bucket = _bucket(buckets, row)
        method = str(row["match_method"])
        page = _page_summary(row)
        bucket["pages"].append(page)
        bucket["method_counts"][method] = int(bucket["method_counts"].get(method, 0)) + 1
        if method.startswith("alias_game_variant_suffix:"):
            bucket["game_variant_page_count"] += 1
        if method.endswith(":prefab_code"):
            bucket["prefab_page_count"] += 1
        if method.endswith(":image_stem") or method.endswith(":image_name"):
            bucket["image_page_count"] += 1
        if method in ("alias:canonical_title", "alias:canonical_slug"):
            bucket["exact_page_count"] += 1

    count = 0
    for bucket in buckets.values():
        identity = bucket["identity"]
        pages = sorted(bucket["pages"], key=_page_rank)
        primary = pages[0] if pages else {}
        method_counts = [
            {"method": method, "count": count}
            for method, count in sorted(
                bucket["method_counts"].items(),
                key=lambda item: (-int(item[1]), item[0]),
            )
        ]
        conn.execute(
            """
            insert into entity_source_profiles (
                entity_id, source_key, slug, canonical_title, kind,
                matched_page_count, exact_page_count, game_variant_page_count,
                prefab_page_count, image_page_count, method_count,
                match_methods_json, primary_page_title, primary_page_url,
                matched_pages_json, has_exact_page, has_game_variant_pages,
                has_prefab_page, has_image_page, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["source_key"]),
                str(identity["entity_slug"]),
                str(identity["entity_title"]),
                str(identity["entity_kind"]),
                len(pages),
                int(bucket["exact_page_count"]),
                int(bucket["game_variant_page_count"]),
                int(bucket["prefab_page_count"]),
                int(bucket["image_page_count"]),
                len(method_counts),
                json.dumps(method_counts, ensure_ascii=False, sort_keys=True),
                str(primary.get("title", "")),
                str(primary.get("url", "")),
                json.dumps(pages[:PAGE_LIMIT], ensure_ascii=False, sort_keys=True),
                int(bool(bucket["exact_page_count"])),
                int(bool(bucket["game_variant_page_count"])),
                int(bool(bucket["prefab_page_count"])),
                int(bool(bucket["image_page_count"])),
            ),
        )
        count += 1
    conn.commit()
    return count


def _bucket(
    grouped: dict[tuple[int, str], dict[str, Any]], row: sqlite3.Row
) -> dict[str, Any]:
    key = (int(row["entity_id"]), str(row["source_key"]))
    return grouped.setdefault(
        key,
        {
            "identity": row,
            "pages": [],
            "method_counts": {},
            "exact_page_count": 0,
            "game_variant_page_count": 0,
            "prefab_page_count": 0,
            "image_page_count": 0,
        },
    )


def _page_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "pageid": int(row["source_pageid"]),
        "title": str(row["source_title"]),
        "slug": str(row["source_title_slug"]),
        "url": str(row["page_url"]),
        "match_method": str(row["match_method"]),
        "confidence": float(row["confidence"]),
    }


def _page_rank(page: dict[str, Any]) -> tuple[int, int, float, str]:
    method = str(page["match_method"])
    exact = 0 if method in ("alias:canonical_title", "alias:canonical_slug") else 1
    game_variant = 0 if method.startswith("alias_game_variant_suffix:") else 1
    return (
        exact,
        game_variant,
        -float(page["confidence"]),
        str(page["title"]),
    )
