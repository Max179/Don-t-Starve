from __future__ import annotations

import json
import sqlite3
from typing import Any


ASSET_SUMMARY_LIMIT = 25


def rebuild_entity_media_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_media_profiles")
    grouped: dict[int, dict[str, Any]] = {}
    for row in _rows(conn):
        bucket = _bucket(grouped, row)
        bucket["media_count"] += 1
        if int(row["is_primary"]):
            bucket["primary_assets"].append(_asset_summary(row))
            bucket["primary_count"] += 1
        if int(row["is_variant"]):
            bucket["variant_assets"].append(_asset_summary(row))
            bucket["variant_count"] += 1
            variant_type = str(row["variant_type"] or "")
            if variant_type:
                bucket["variant_types"].add(variant_type)
        url_status = str(row["url_status"] or "")
        if url_status:
            bucket["url_status_counts"][url_status] = (
                bucket["url_status_counts"].get(url_status, 0) + 1
            )
        download_status = str(row["download_status"] or "")
        if download_status:
            bucket["download_status_counts"][download_status] = (
                bucket["download_status_counts"].get(download_status, 0) + 1
            )

    count = 0
    for bucket in grouped.values():
        identity = bucket["identity"]
        primary_assets = sorted(
            bucket["primary_assets"],
            key=lambda item: (
                item["url_status"] != "direct_url",
                item["asset_source"],
                item["role"],
                item["image_name"],
            ),
        )
        variant_assets = sorted(
            bucket["variant_assets"],
            key=lambda item: (item["variant_type"], item["variant_key"], item["image_name"]),
        )
        primary = primary_assets[0] if primary_assets else {}
        primary_asset_summaries = primary_assets[:ASSET_SUMMARY_LIMIT]
        variant_asset_summaries = variant_assets[:ASSET_SUMMARY_LIMIT]
        url_counts = bucket["url_status_counts"]
        download_counts = bucket["download_status_counts"]
        conn.execute(
            """
            insert into entity_media_profiles (
                entity_id, slug, canonical_title, kind,
                media_count, primary_count, variant_count, direct_url_count,
                file_page_only_count, missing_url_count, pending_download_count,
                downloaded_count, failed_download_count, variant_type_count,
                variant_types_text, primary_image_name, primary_role,
                primary_asset_source, primary_download_url, primary_file_page_url,
                primary_target_path, primary_local_path, primary_width,
                primary_height, primary_mime, primary_assets_json,
                variant_assets_json, has_primary_image, has_direct_url,
                has_variants, has_downloaded_media, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["slug"]),
                str(identity["canonical_title"]),
                str(identity["kind"]),
                int(bucket["media_count"]),
                int(bucket["primary_count"]),
                int(bucket["variant_count"]),
                int(url_counts.get("direct_url", 0)),
                int(url_counts.get("file_page_only", 0)),
                int(url_counts.get("missing_url", 0)),
                int(download_counts.get("pending", 0)),
                int(download_counts.get("downloaded", 0)),
                int(download_counts.get("failed", 0)),
                len(bucket["variant_types"]),
                " | ".join(sorted(bucket["variant_types"])),
                primary.get("image_name", ""),
                primary.get("role", ""),
                primary.get("asset_source", ""),
                primary.get("download_url"),
                primary.get("file_page_url"),
                primary.get("target_path"),
                primary.get("local_path"),
                primary.get("width"),
                primary.get("height"),
                primary.get("mime"),
                json.dumps(primary_asset_summaries, ensure_ascii=False, sort_keys=True),
                json.dumps(variant_asset_summaries, ensure_ascii=False, sort_keys=True),
                int(bool(primary_assets)),
                int(bool(url_counts.get("direct_url", 0))),
                int(bool(variant_assets)),
                int(bool(download_counts.get("downloaded", 0))),
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
            "media_count": 0,
            "primary_count": 0,
            "variant_count": 0,
            "primary_assets": [],
            "variant_assets": [],
            "variant_types": set(),
            "url_status_counts": {},
            "download_status_counts": {},
        },
    )


def _rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            ema.entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            s.key as source_key,
            ema.asset_source,
            ema.image_name,
            ema.image_slug,
            ema.role,
            ema.original_url,
            ema.description_url,
            ema.local_path as asset_local_path,
            ema.width,
            ema.height,
            ema.mime,
            ema.variant_key,
            ema.variant_type,
            ema.variant_label,
            ema.is_primary,
            ema.is_variant,
            ema.confidence,
            emd.download_url,
            emd.file_page_url,
            emd.url_status,
            emd.download_status,
            emd.local_path as download_local_path,
            emd.content_length
        from entity_media_assets ema
        join entities e on e.id = ema.entity_id
        join sources s on s.id = ema.source_id
        left join entity_media_downloads emd
          on emd.entity_media_asset_id = ema.id
        order by e.slug, ema.is_primary desc, ema.is_variant desc, ema.id
        """
    ).fetchall()


def _asset_summary(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "asset_source": str(row["asset_source"]),
        "image_name": str(row["image_name"]),
        "image_slug": str(row["image_slug"]),
        "role": str(row["role"]),
        "download_url": row["download_url"] or row["original_url"],
        "file_page_url": row["file_page_url"] or row["description_url"],
        "target_path": _target_path(row),
        "local_path": row["download_local_path"] or row["asset_local_path"],
        "width": _optional_int(row["width"]),
        "height": _optional_int(row["height"]),
        "mime": row["mime"],
        "content_length": _optional_int(row["content_length"]),
        "url_status": str(row["url_status"] or ""),
        "download_status": str(row["download_status"] or ""),
        "variant_key": str(row["variant_key"] or ""),
        "variant_type": str(row["variant_type"] or ""),
        "variant_label": str(row["variant_label"] or ""),
        "is_primary": bool(row["is_primary"]),
        "is_variant": bool(row["is_variant"]),
        "confidence": _optional_float(row["confidence"]),
    }


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


def _target_path(row: sqlite3.Row) -> str:
    return "/".join(
        (
            "data/images",
            str(row["source_key"]),
            str(row["slug"]),
            str(row["image_slug"]),
        )
    )
