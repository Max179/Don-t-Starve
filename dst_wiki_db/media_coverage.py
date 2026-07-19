from __future__ import annotations

import json
import sqlite3
from typing import Any


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

REASON_PENALTY = {
    "missing_media": 0,
    "missing_primary_image": 5,
    "missing_direct_url": 10,
    "file_page_resolution_pending": 15,
    "missing_media_url": 20,
    "failed_download": 25,
    "pending_download": 30,
}


def rebuild_entity_media_coverage(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("delete from entity_media_gap_queue")
    conn.execute("delete from entity_media_coverage")
    rows = conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            emp.media_count,
            emp.primary_count,
            emp.variant_count,
            emp.direct_url_count,
            emp.file_page_only_count,
            emp.missing_url_count,
            emp.pending_download_count,
            emp.downloaded_count,
            emp.failed_download_count,
            emp.variant_type_count,
            emp.has_primary_image,
            emp.has_direct_url,
            emp.has_variants,
            emp.has_downloaded_media,
            emp.primary_image_name,
            emp.primary_download_url,
            emp.primary_file_page_url
        from entities e
        left join entity_media_profiles emp on emp.entity_id = e.id
        order by e.id
        """
    ).fetchall()
    coverage_count = 0
    gap_count = 0
    for row in rows:
        summary = _summary(row)
        conn.execute(
            """
            insert into entity_media_coverage (
                entity_id, slug, canonical_title, kind,
                media_count, primary_count, variant_count, direct_url_count,
                file_page_only_count, missing_url_count,
                pending_download_count, downloaded_count, failed_download_count,
                variant_type_count, has_media_profile, has_primary_image,
                has_direct_url, has_variants, has_downloaded_media,
                media_status, gap_reasons_json, priority, primary_image_name,
                primary_download_url, primary_file_page_url, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                int(row["entity_id"]),
                str(row["slug"]),
                str(row["canonical_title"]),
                str(row["kind"]),
                summary["media_count"],
                summary["primary_count"],
                summary["variant_count"],
                summary["direct_url_count"],
                summary["file_page_only_count"],
                summary["missing_url_count"],
                summary["pending_download_count"],
                summary["downloaded_count"],
                summary["failed_download_count"],
                summary["variant_type_count"],
                summary["has_media_profile"],
                summary["has_primary_image"],
                summary["has_direct_url"],
                summary["has_variants"],
                summary["has_downloaded_media"],
                summary["media_status"],
                json.dumps(summary["gap_reasons"], ensure_ascii=False),
                summary["priority"],
                summary["primary_image_name"],
                summary["primary_download_url"],
                summary["primary_file_page_url"],
            ),
        )
        coverage_count += 1
        for reason in summary["gap_reasons"]:
            conn.execute(
                """
                insert into entity_media_gap_queue (
                    entity_id, slug, canonical_title, kind, gap_reason,
                    media_status, priority, media_count, primary_count,
                    variant_count, direct_url_count, file_page_only_count,
                    missing_url_count, pending_download_count,
                    failed_download_count, primary_image_name,
                    primary_download_url, primary_file_page_url, detected_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        current_timestamp)
                """,
                (
                    int(row["entity_id"]),
                    str(row["slug"]),
                    str(row["canonical_title"]),
                    str(row["kind"]),
                    reason,
                    summary["media_status"],
                    _reason_priority(row, reason),
                    summary["media_count"],
                    summary["primary_count"],
                    summary["variant_count"],
                    summary["direct_url_count"],
                    summary["file_page_only_count"],
                    summary["missing_url_count"],
                    summary["pending_download_count"],
                    summary["failed_download_count"],
                    summary["primary_image_name"],
                    summary["primary_download_url"],
                    summary["primary_file_page_url"],
                ),
            )
            gap_count += 1
    conn.commit()
    return {
        "entity_media_coverage": coverage_count,
        "entity_media_gap_queue": gap_count,
    }


def _summary(row: sqlite3.Row) -> dict[str, Any]:
    counts = {
        "media_count": _int(row["media_count"]),
        "primary_count": _int(row["primary_count"]),
        "variant_count": _int(row["variant_count"]),
        "direct_url_count": _int(row["direct_url_count"]),
        "file_page_only_count": _int(row["file_page_only_count"]),
        "missing_url_count": _int(row["missing_url_count"]),
        "pending_download_count": _int(row["pending_download_count"]),
        "downloaded_count": _int(row["downloaded_count"]),
        "failed_download_count": _int(row["failed_download_count"]),
        "variant_type_count": _int(row["variant_type_count"]),
    }
    flags = {
        "has_media_profile": int(counts["media_count"] > 0),
        "has_primary_image": _int(row["has_primary_image"]),
        "has_direct_url": _int(row["has_direct_url"]),
        "has_variants": _int(row["has_variants"]),
        "has_downloaded_media": _int(row["has_downloaded_media"]),
    }
    gap_reasons = _gap_reasons(counts, flags)
    return {
        **counts,
        **flags,
        "media_status": _media_status(counts, flags),
        "gap_reasons": gap_reasons,
        "priority": _coverage_priority(row, gap_reasons),
        "primary_image_name": str(row["primary_image_name"] or ""),
        "primary_download_url": row["primary_download_url"],
        "primary_file_page_url": row["primary_file_page_url"],
    }


def _gap_reasons(counts: dict[str, int], flags: dict[str, int]) -> list[str]:
    if not flags["has_media_profile"]:
        return ["missing_media"]
    reasons: list[str] = []
    if not flags["has_primary_image"]:
        reasons.append("missing_primary_image")
    if not flags["has_direct_url"]:
        reasons.append("missing_direct_url")
    if counts["file_page_only_count"] > 0:
        reasons.append("file_page_resolution_pending")
    if counts["missing_url_count"] > 0:
        reasons.append("missing_media_url")
    if counts["failed_download_count"] > 0:
        reasons.append("failed_download")
    if counts["pending_download_count"] > 0:
        reasons.append("pending_download")
    return reasons


def _media_status(counts: dict[str, int], flags: dict[str, int]) -> str:
    if not flags["has_media_profile"]:
        return "no_media"
    if not flags["has_primary_image"]:
        return "missing_primary_image"
    if not flags["has_direct_url"]:
        return "missing_direct_url"
    if counts["file_page_only_count"] > 0 or counts["missing_url_count"] > 0:
        return "partial_url_coverage"
    if counts["failed_download_count"] > 0:
        return "download_errors"
    if counts["pending_download_count"] > 0:
        return "download_pending"
    if flags["has_downloaded_media"]:
        return "downloaded_media"
    return "metadata_ready"


def _coverage_priority(row: sqlite3.Row, reasons: list[str]) -> int:
    if not reasons:
        return 99
    return min(_reason_priority(row, reason) for reason in reasons)


def _reason_priority(row: sqlite3.Row, reason: str) -> int:
    return KIND_PRIORITY.get(str(row["kind"]), 50) + REASON_PENALTY.get(reason, 40)


def _int(value: Any) -> int:
    return 0 if value is None else int(value)
