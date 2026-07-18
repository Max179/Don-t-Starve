from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any

import requests

from dst_wiki_db.mediawiki import MediaWikiClient


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
                entity_media_asset_id, entity_id, source_id, download_url,
                file_page_url, url_status, download_status, priority,
                queue_reason
            )
            values (?, ?, ?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                int(row["entity_media_asset_id"]),
                int(row["entity_id"]),
                int(row["source_id"]),
                row["original_url"],
                row["description_url"],
                url_status,
                priority,
                _queue_reason(
                    is_primary=bool(row["is_primary"]),
                    is_variant=bool(row["is_variant"]),
                    url_status=url_status,
                ),
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


def resolve_file_page_download_urls(
    conn: sqlite3.Connection,
    *,
    source_key: str | None = None,
    limit: int | None = None,
    client: Any | None = None,
    batch_size: int = 50,
    dry_run: bool = False,
) -> dict[str, int | bool]:
    rows = _file_page_only_rows(conn, source_key=source_key, limit=limit)
    result = {
        "attempted": len(rows),
        "resolved": 0,
        "missing": 0,
        "skipped": 0,
        "dry_run": dry_run,
    }
    if not rows:
        return result
    if dry_run:
        result["skipped"] = len(rows)
        return result

    clients: dict[str, Any] = {}
    if client is not None:
        for row in rows:
            clients[str(row["source_key"])] = client

    for group in _chunks(rows, max(1, batch_size)):
        by_source: dict[str, list[sqlite3.Row]] = {}
        for row in group:
            by_source.setdefault(str(row["source_key"]), []).append(row)
        for key, source_rows in by_source.items():
            source_client = clients.get(key)
            if source_client is None:
                first = source_rows[0]
                source_client = MediaWikiClient(
                    key=key,
                    api_url=str(first["api_url"]),
                )
                clients[key] = source_client
            info_by_title = source_client.fetch_imageinfo(
                [str(row["image_name"]) for row in source_rows]
            )
            for row in source_rows:
                info = _imageinfo_for_row(info_by_title, str(row["image_name"]))
                download_url = (info.get("url") or info.get("thumburl")) if info else None
                if not download_url:
                    result["missing"] += 1
                    continue
                url_status = "direct_url"
                priority = _priority(
                    is_primary=bool(row["is_primary"]),
                    is_variant=bool(row["is_variant"]),
                    url_status=url_status,
                )
                queue_reason = _queue_reason(
                    is_primary=bool(row["is_primary"]),
                    is_variant=bool(row["is_variant"]),
                    url_status=url_status,
                )
                conn.execute(
                    """
                    update entity_media_downloads
                    set download_url = ?,
                        url_status = ?,
                        priority = ?,
                        queue_reason = ?,
                        error_text = ''
                    where id = ?
                    """,
                    (
                        str(download_url),
                        url_status,
                        priority,
                        queue_reason,
                        int(row["id"]),
                    ),
                )
                conn.execute(
                    """
                    update entity_media_assets
                    set original_url = coalesce(original_url, ?),
                        width = coalesce(width, ?),
                        height = coalesce(height, ?),
                        mime = coalesce(mime, ?),
                        sha1 = coalesce(sha1, ?)
                    where id = ?
                    """,
                    (
                        str(download_url),
                        _optional_int(info.get("width")),
                        _optional_int(info.get("height")),
                        info.get("mime"),
                        info.get("sha1"),
                        int(row["entity_media_asset_id"]),
                    ),
                )
                result["resolved"] += 1
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
        from entity_media_download_manifest
        where download_status = 'pending'
          and url_status = 'direct_url'
          and download_url is not null
          and download_url != ''
        order by priority, id
        {limit_clause}
        """,
        params,
    ).fetchall()


def _file_page_only_rows(
    conn: sqlite3.Connection, *, source_key: str | None, limit: int | None
) -> list[sqlite3.Row]:
    filters = [
        "emd.url_status = 'file_page_only'",
        "(emd.download_url is null or emd.download_url = '')",
        "emd.file_page_url is not null",
        "emd.file_page_url != ''",
    ]
    params: list[object] = []
    if source_key:
        filters.append("s.key = ?")
        params.append(source_key)
    limit_clause = ""
    if limit is not None:
        limit_clause = "limit ?"
        params.append(limit)
    return conn.execute(
        f"""
        select
            emd.id,
            emd.entity_media_asset_id,
            s.key as source_key,
            ema.image_name,
            ema.is_primary,
            ema.is_variant,
            s.api_url
        from entity_media_downloads emd
        join entity_media_assets ema on ema.id = emd.entity_media_asset_id
        join sources s on s.id = emd.source_id
        where {" and ".join(filters)}
        order by emd.priority, emd.id
        {limit_clause}
        """,
        tuple(params),
    ).fetchall()


def _imageinfo_for_row(info_by_title: dict[str, dict], image_name: str) -> dict:
    candidates = [
        image_name,
        _file_title(image_name),
        _file_title(image_name).replace(" ", "_"),
    ]
    for candidate in candidates:
        info = info_by_title.get(candidate)
        if info:
            return info
    return {}


def _file_title(name: str) -> str:
    if name.lower().startswith(("file:", "image:")):
        return "File:" + name.split(":", 1)[1].strip()
    return "File:" + name.strip()


def _optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _chunks(rows: list[sqlite3.Row], size: int) -> list[list[sqlite3.Row]]:
    return [rows[index : index + size] for index in range(0, len(rows), size)]


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
