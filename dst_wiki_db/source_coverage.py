from __future__ import annotations

import json
import sqlite3
from typing import Any


CORE_SOURCE_KEYS = ("wiki.gg", "fandom")


def rebuild_entity_source_coverage(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_source_coverage")
    rows = conn.execute(
        """
        select id as entity_id, slug, canonical_title, kind
        from entities
        order by id
        """
    ).fetchall()
    profiles = _profiles_by_entity(conn)
    count = 0
    for row in rows:
        entity_id = int(row["entity_id"])
        entity_profiles = profiles.get(entity_id, [])
        summary = _summarize_profiles(entity_profiles)
        conn.execute(
            """
            insert into entity_source_coverage (
                entity_id, slug, canonical_title, kind,
                source_profile_count, matched_page_count,
                wiki_gg_page_count, fandom_page_count, other_page_count,
                exact_page_count, game_variant_page_count, prefab_page_count,
                image_page_count, method_count,
                has_wiki_gg, has_fandom, has_both_core_wikis,
                has_exact_page, has_game_variant_pages, has_prefab_page,
                has_image_page, source_keys_json, missing_sources_json,
                coverage_status, best_source_key, best_page_title,
                best_page_url, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                entity_id,
                str(row["slug"]),
                str(row["canonical_title"]),
                str(row["kind"]),
                summary["source_profile_count"],
                summary["matched_page_count"],
                summary["wiki_gg_page_count"],
                summary["fandom_page_count"],
                summary["other_page_count"],
                summary["exact_page_count"],
                summary["game_variant_page_count"],
                summary["prefab_page_count"],
                summary["image_page_count"],
                summary["method_count"],
                summary["has_wiki_gg"],
                summary["has_fandom"],
                summary["has_both_core_wikis"],
                summary["has_exact_page"],
                summary["has_game_variant_pages"],
                summary["has_prefab_page"],
                summary["has_image_page"],
                json.dumps(summary["source_keys"], ensure_ascii=False),
                json.dumps(summary["missing_sources"], ensure_ascii=False),
                summary["coverage_status"],
                summary["best_source_key"],
                summary["best_page_title"],
                summary["best_page_url"],
            ),
        )
        count += 1
    conn.commit()
    return count


def _profiles_by_entity(conn: sqlite3.Connection) -> dict[int, list[sqlite3.Row]]:
    rows = conn.execute(
        """
        select
            entity_id,
            source_key,
            matched_page_count,
            exact_page_count,
            game_variant_page_count,
            prefab_page_count,
            image_page_count,
            method_count,
            primary_page_title,
            primary_page_url,
            has_exact_page,
            has_game_variant_pages,
            has_prefab_page,
            has_image_page
        from entity_source_profiles
        order by entity_id, source_key
        """
    ).fetchall()
    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(int(row["entity_id"]), []).append(row)
    return grouped


def _summarize_profiles(rows: list[sqlite3.Row]) -> dict[str, Any]:
    source_keys = sorted({str(row["source_key"]) for row in rows})
    missing_sources = [key for key in CORE_SOURCE_KEYS if key not in source_keys]
    has_wiki_gg = int("wiki.gg" in source_keys)
    has_fandom = int("fandom" in source_keys)
    matched_page_count = sum(int(row["matched_page_count"]) for row in rows)
    best = _best_profile(rows)
    return {
        "source_profile_count": len(rows),
        "matched_page_count": matched_page_count,
        "wiki_gg_page_count": _page_count(rows, "wiki.gg"),
        "fandom_page_count": _page_count(rows, "fandom"),
        "other_page_count": sum(
            int(row["matched_page_count"])
            for row in rows
            if str(row["source_key"]) not in CORE_SOURCE_KEYS
        ),
        "exact_page_count": sum(int(row["exact_page_count"]) for row in rows),
        "game_variant_page_count": sum(
            int(row["game_variant_page_count"]) for row in rows
        ),
        "prefab_page_count": sum(int(row["prefab_page_count"]) for row in rows),
        "image_page_count": sum(int(row["image_page_count"]) for row in rows),
        "method_count": sum(int(row["method_count"]) for row in rows),
        "has_wiki_gg": has_wiki_gg,
        "has_fandom": has_fandom,
        "has_both_core_wikis": int(has_wiki_gg and has_fandom),
        "has_exact_page": int(any(int(row["has_exact_page"]) for row in rows)),
        "has_game_variant_pages": int(
            any(int(row["has_game_variant_pages"]) for row in rows)
        ),
        "has_prefab_page": int(any(int(row["has_prefab_page"]) for row in rows)),
        "has_image_page": int(any(int(row["has_image_page"]) for row in rows)),
        "source_keys": source_keys,
        "missing_sources": missing_sources,
        "coverage_status": _coverage_status(source_keys),
        "best_source_key": str(best["source_key"]) if best is not None else "",
        "best_page_title": str(best["primary_page_title"] or "")
        if best is not None
        else "",
        "best_page_url": str(best["primary_page_url"] or "")
        if best is not None
        else "",
    }


def _page_count(rows: list[sqlite3.Row], source_key: str) -> int:
    return sum(
        int(row["matched_page_count"])
        for row in rows
        if str(row["source_key"]) == source_key
    )


def _coverage_status(source_keys: list[str]) -> str:
    if "wiki.gg" in source_keys and "fandom" in source_keys:
        return "both_sources"
    if "wiki.gg" in source_keys:
        return "wiki.gg_only"
    if "fandom" in source_keys:
        return "fandom_only"
    if source_keys:
        return "other_sources_only"
    return "missing_source_profiles"


def _best_profile(rows: list[sqlite3.Row]) -> sqlite3.Row | None:
    if not rows:
        return None
    source_rank = {"wiki.gg": 0, "fandom": 1}
    return sorted(
        rows,
        key=lambda row: (
            source_rank.get(str(row["source_key"]), 9),
            -int(row["has_exact_page"]),
            -int(row["matched_page_count"]),
            str(row["source_key"]),
        ),
    )[0]
