from __future__ import annotations

import re
import sqlite3


PRIMARY_INFOBOX_ROLES = {"image", "inventoryimage", "inventoryImage"}
MediaAssetMetadata = tuple[
    dict[tuple[object, ...], dict[str, object]],
    dict[tuple[object, ...], dict[str, object]],
]


def capture_entity_media_asset_metadata(conn: sqlite3.Connection) -> MediaAssetMetadata:
    return _existing_asset_metadata(conn)


def rebuild_entity_media_assets(
    conn: sqlite3.Connection,
    preserved_metadata: MediaAssetMetadata | None = None,
) -> int:
    if preserved_metadata is None:
        existing_metadata, loose_metadata = _existing_asset_metadata(conn)
    else:
        existing_metadata, loose_metadata = preserved_metadata
    conn.execute("delete from entity_media_assets")
    count = 0
    count += _insert_infobox_assets(conn, existing_metadata, loose_metadata)
    count += _insert_page_assets(conn, existing_metadata, loose_metadata)
    conn.commit()
    return count


def _insert_infobox_assets(
    conn: sqlite3.Connection,
    existing_metadata: dict[tuple[object, ...], dict[str, object]],
    loose_metadata: dict[tuple[object, ...], dict[str, object]],
) -> int:
    rows = conn.execute(
        """
        select
            id as entity_image_id,
            entity_id,
            source_id,
            raw_page_id,
            image_name,
            role,
            original_url,
            description_url,
            local_path,
            width,
            height,
            mime,
            sha1,
            coalesce(variant_key, '') as variant_key
        from entity_images
        order by entity_id, id
        """
    ).fetchall()
    count = 0
    for row in rows:
        variant_key = str(row["variant_key"] or "")
        variant_type = _infobox_variant_type(variant_key)
        variant_label = _variant_label(variant_key)
        image_slug = _slug_from_image_name(str(row["image_name"]))
        preserved = _preserved_metadata(
            existing_metadata,
            loose_metadata,
            exact_key=_asset_key(
                entity_id=int(row["entity_id"]),
                source_id=int(row["source_id"]),
                asset_source="infobox",
                image_slug=image_slug,
                role=str(row["role"]),
                description_url=row["description_url"],
            ),
            loose_key=_loose_asset_key(
                entity_id=int(row["entity_id"]),
                source_id=int(row["source_id"]),
                asset_source="infobox",
                image_slug=image_slug,
            ),
        )
        conn.execute(
            """
            insert into entity_media_assets (
                entity_id, source_id, raw_page_id, asset_source,
                entity_image_id, page_image_id, image_name, image_slug,
                role, original_url, description_url, local_path, width,
                height, mime, sha1, variant_key, variant_type,
                variant_label, is_variant, is_primary, confidence
            )
            values (?, ?, ?, 'infobox', ?, null, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, 1.0)
            """,
            (
                int(row["entity_id"]),
                int(row["source_id"]),
                None if row["raw_page_id"] is None else int(row["raw_page_id"]),
                int(row["entity_image_id"]),
                str(row["image_name"]),
                image_slug,
                str(row["role"]),
                row["original_url"] or preserved.get("original_url"),
                row["description_url"],
                row["local_path"] or preserved.get("local_path"),
                row["width"] if row["width"] is not None else preserved.get("width"),
                row["height"] if row["height"] is not None else preserved.get("height"),
                row["mime"] or preserved.get("mime"),
                row["sha1"] or preserved.get("sha1"),
                variant_key,
                variant_type,
                variant_label,
                int(bool(variant_key)),
                int(str(row["role"]) in PRIMARY_INFOBOX_ROLES),
            ),
        )
        count += 1
    return count


def _insert_page_assets(
    conn: sqlite3.Connection,
    existing_metadata: dict[tuple[object, ...], dict[str, object]],
    loose_metadata: dict[tuple[object, ...], dict[str, object]],
) -> int:
    rows = conn.execute(
        """
        select
            pi.id as page_image_id,
            pi.entity_id,
            pi.source_id,
            pi.raw_page_id,
            pi.image_name,
            pi.image_slug,
            pi.role,
            pi.description_url,
            pi.local_path,
            iv.variant_key,
            iv.variant_type,
            iv.label as variant_label,
            iv.confidence
        from page_images pi
        left join image_variants iv on iv.page_image_id = pi.id
        order by pi.entity_id, pi.id
        """
    ).fetchall()
    count = 0
    for row in rows:
        variant_key = str(row["variant_key"] or "")
        preserved = _preserved_metadata(
            existing_metadata,
            loose_metadata,
            exact_key=_asset_key(
                entity_id=int(row["entity_id"]),
                source_id=int(row["source_id"]),
                asset_source="page_reference",
                image_slug=str(row["image_slug"]),
                role=str(row["role"]),
                description_url=row["description_url"],
            ),
            loose_key=_loose_asset_key(
                entity_id=int(row["entity_id"]),
                source_id=int(row["source_id"]),
                asset_source="page_reference",
                image_slug=str(row["image_slug"]),
            ),
        )
        conn.execute(
            """
            insert into entity_media_assets (
                entity_id, source_id, raw_page_id, asset_source,
                entity_image_id, page_image_id, image_name, image_slug,
                role, original_url, description_url, local_path, width,
                height, mime, sha1, variant_key, variant_type,
                variant_label, is_variant, is_primary, confidence
            )
            values (?, ?, ?, 'page_reference', null, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["raw_page_id"]),
                int(row["page_image_id"]),
                str(row["image_name"]),
                str(row["image_slug"]),
                str(row["role"]),
                preserved.get("original_url"),
                row["description_url"],
                row["local_path"] or preserved.get("local_path"),
                preserved.get("width"),
                preserved.get("height"),
                preserved.get("mime"),
                preserved.get("sha1"),
                variant_key,
                str(row["variant_type"] or ""),
                str(row["variant_label"] or ""),
                int(bool(variant_key)),
                float(row["confidence"] if row["confidence"] is not None else 0.5),
            ),
        )
        count += 1
    return count


def _existing_asset_metadata(
    conn: sqlite3.Connection,
) -> tuple[dict[tuple[object, ...], dict[str, object]], dict[tuple[object, ...], dict[str, object]]]:
    rows = conn.execute(
        """
        select
            entity_id, source_id, asset_source, image_slug, role,
            description_url, original_url, local_path, width, height, mime, sha1
        from entity_media_assets
        where coalesce(original_url, '') != ''
           or coalesce(local_path, '') != ''
           or width is not null
           or height is not null
           or coalesce(mime, '') != ''
           or coalesce(sha1, '') != ''
        """
    ).fetchall()
    exact = {
        _asset_key(
            entity_id=int(row["entity_id"]),
            source_id=int(row["source_id"]),
            asset_source=str(row["asset_source"]),
            image_slug=str(row["image_slug"]),
            role=str(row["role"]),
            description_url=row["description_url"],
        ): {
            "original_url": row["original_url"],
            "local_path": row["local_path"],
            "width": row["width"],
            "height": row["height"],
            "mime": row["mime"],
            "sha1": row["sha1"],
        }
        for row in rows
    }
    loose: dict[tuple[object, ...], dict[str, object]] = {}
    for row in rows:
        loose.setdefault(
            _loose_asset_key(
                entity_id=int(row["entity_id"]),
                source_id=int(row["source_id"]),
                asset_source=str(row["asset_source"]),
                image_slug=str(row["image_slug"]),
            ),
            {
                "original_url": row["original_url"],
                "local_path": row["local_path"],
                "width": row["width"],
                "height": row["height"],
                "mime": row["mime"],
                "sha1": row["sha1"],
            },
        )
    return exact, loose


def _preserved_metadata(
    existing_metadata: dict[tuple[object, ...], dict[str, object]],
    loose_metadata: dict[tuple[object, ...], dict[str, object]],
    *,
    exact_key: tuple[object, ...],
    loose_key: tuple[object, ...],
) -> dict[str, object]:
    return existing_metadata.get(exact_key) or loose_metadata.get(loose_key, {})


def _asset_key(
    *,
    entity_id: int,
    source_id: int,
    asset_source: str,
    image_slug: str,
    role: str,
    description_url: object,
) -> tuple[object, ...]:
    return (
        entity_id,
        source_id,
        asset_source,
        image_slug,
        role,
        str(description_url or ""),
    )


def _loose_asset_key(
    *,
    entity_id: int,
    source_id: int,
    asset_source: str,
    image_slug: str,
) -> tuple[object, ...]:
    return (entity_id, source_id, asset_source, image_slug)


def _slug_from_image_name(image_name: str) -> str:
    stem = image_name.strip().lower()
    stem = re.sub(r"\.(?:png|jpe?g|gif|webp|avif)$", "", stem)
    stem = stem.replace("&", " and ").replace("'", "")
    return re.sub(r"[^a-z0-9]+", "-", stem).strip("-") + _extension_suffix(image_name)


def _extension_suffix(image_name: str) -> str:
    match = re.search(r"\.([a-z0-9]+)$", image_name.lower())
    return f"-{match.group(1)}" if match else ""


def _infobox_variant_type(variant_key: str) -> str:
    if not variant_key:
        return ""
    if variant_key in {"ds", "dst"}:
        return "game_scope"
    if variant_key in {"seed", "sprout", "small", "med", "medium", "large", "bolting", "picked"}:
        return "growth_stage"
    return "infobox_variant"


def _variant_label(variant_key: str) -> str:
    labels = {
        "ds": "Don't Starve",
        "dst": "Don't Starve Together",
        "med": "Medium",
    }
    if not variant_key:
        return ""
    return labels.get(
        variant_key,
        " ".join(part.capitalize() for part in variant_key.split("-") if part),
    )
