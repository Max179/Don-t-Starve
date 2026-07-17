from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

import requests


def rebuild_entity_media_downloads(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_media_downloads")
    rows = conn.execute(
        """
        select
            ema.id as entity_media_asset_id,
            ema.entity_id,
            ema.source_id,
            s.key as source_key,
            e.slug,
            e.canonical_title,
            e.kind,
            ema.image_name,
            ema.image_slug,
            ema.role,
            ema.asset_source,
            ema.original_url,
            ema.description_url,
            ema.variant_key,
            ema.variant_type,
            ema.variant_label,
            ema.is_primary,
            ema.is_variant,
            ema.confidence
        from entity_media_assets ema
        join entities e on e.id = ema.entity_id
        join sources s on s.id = ema.source_id
        order by e.slug, ema.is_primary desc, ema.is_variant desc, ema.id
        """
    ).fetchall()
    count = 0
    for row in rows:
        url_status = _url_status(row["original_url"], row["description_url"])
        priority = _priority(
            is_primary=bool(row["is_primary"]),
            is_variant=bool(row["is_variant"]),
            url_status=url_status,
        )
        cursor = conn.execute(
            """
            insert or ignore into entity_media_downloads (
                entity_media_asset_id, entity_id, source_id, source_key, slug,
                canonical_title, kind, image_name, image_slug, role,
                asset_source, download_url, file_page_url, url_status,
                target_path, download_status, priority, queue_reason,
                variant_key, variant_type, variant_label, is_primary,
                is_variant, confidence
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending',
                    ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["entity_media_asset_id"]),
                int(row["entity_id"]),
                int(row["source_id"]),
                str(row["source_key"]),
                str(row["slug"]),
                str(row["canonical_title"]),
                str(row["kind"]),
                str(row["image_name"]),
                str(row["image_slug"]),
                str(row["role"]),
                str(row["asset_source"]),
                row["original_url"],
                row["description_url"],
                url_status,
                _target_path(row),
                priority,
                _queue_reason(
                    is_primary=bool(row["is_primary"]),
                    is_variant=bool(row["is_variant"]),
                    url_status=url_status,
                ),
                str(row["variant_key"] or ""),
                str(row["variant_type"] or ""),
                str(row["variant_label"] or ""),
                int(row["is_primary"]),
                int(row["is_variant"]),
                float(row["confidence"]),
            ),
        )
        count += 1 if cursor.rowcount == 1 else 0
    conn.commit()
    return count


def download_pending_media(
    conn: sqlite3.Connection,
    *,
    output_root: Path | str = Path("."),
    limit: int | None = None,
    session: Any | None = None,
    timeout: int = 30,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    rows = _pending_direct_downloads(conn, limit=limit)
    result = {
        "attempted": len(rows),
        "downloaded": 0,
        "failed": 0,
        "skipped": 0,
        "dry_run": dry_run,
    }
    if dry_run:
        result["skipped"] = len(rows)
        return result

    root = Path(output_root)
    http = session or requests.Session()
    for row in rows:
        destination = root / str(row["target_path"])
        try:
            response = http.get(str(row["download_url"]), timeout=timeout)
            response.raise_for_status()
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(response.content)
        except Exception as exc:  # pragma: no cover - exact request errors vary
            conn.execute(
                """
                update entity_media_downloads
                set download_status = 'failed',
                    error_text = ?
                where id = ?
                """,
                (str(exc), int(row["id"])),
            )
            result["failed"] += 1
            continue
        conn.execute(
            """
            update entity_media_downloads
            set download_status = 'downloaded',
                local_path = ?,
                content_length = ?,
                downloaded_at = current_timestamp,
                error_text = ''
            where id = ?
            """,
            (str(destination), len(response.content), int(row["id"])),
        )
        result["downloaded"] += 1
    conn.commit()
    return result


def _pending_direct_downloads(
    conn: sqlite3.Connection, *, limit: int | None
) -> list[sqlite3.Row]:
    limit_clause = "" if limit is None else "limit ?"
    params: tuple[int, ...] = () if limit is None else (limit,)
    return conn.execute(
        f"""
        select id, download_url, target_path
        from entity_media_downloads
        where download_status = 'pending'
          and url_status = 'direct_url'
          and download_url is not null
          and download_url != ''
        order by priority, id
        {limit_clause}
        """,
        params,
    ).fetchall()


def _url_status(download_url: str | None, file_page_url: str | None) -> str:
    if download_url:
        return "direct_url"
    if file_page_url:
        return "file_page_only"
    return "missing_url"


def _priority(*, is_primary: bool, is_variant: bool, url_status: str) -> int:
    if is_primary and url_status == "direct_url":
        return 10
    if is_primary:
        return 15
    if url_status == "direct_url":
        return 20
    if is_variant:
        return 35
    if url_status == "file_page_only":
        return 45
    return 90


def _queue_reason(*, is_primary: bool, is_variant: bool, url_status: str) -> str:
    reasons = []
    if is_primary:
        reasons.append("primary")
    if is_variant:
        reasons.append("variant")
    if not reasons:
        reasons.append("page_reference")
    reasons.append(url_status)
    return "|".join(reasons)


def _target_path(row: sqlite3.Row) -> str:
    return "/".join(
        (
            "data/images",
            str(row["source_key"]),
            str(row["slug"]),
            str(row["image_slug"]),
        )
    )
