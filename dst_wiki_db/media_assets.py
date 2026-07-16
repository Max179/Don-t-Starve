from __future__ import annotations

import re
import sqlite3


PRIMARY_INFOBOX_ROLES = {"image", "inventoryimage", "inventoryImage"}


def rebuild_entity_media_assets(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_media_assets")
    count = 0
    count += _insert_infobox_assets(conn)
    count += _insert_page_assets(conn)
    conn.commit()
    return count


def _insert_infobox_assets(conn: sqlite3.Connection) -> int:
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
                _slug_from_image_name(str(row["image_name"])),
                str(row["role"]),
                row["original_url"],
                row["description_url"],
                row["local_path"],
                row["width"],
                row["height"],
                row["mime"],
                row["sha1"],
                variant_key,
                variant_type,
                variant_label,
                int(bool(variant_key)),
                int(str(row["role"]) in PRIMARY_INFOBOX_ROLES),
            ),
        )
        count += 1
    return count


def _insert_page_assets(conn: sqlite3.Connection) -> int:
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
        conn.execute(
            """
            insert into entity_media_assets (
                entity_id, source_id, raw_page_id, asset_source,
                entity_image_id, page_image_id, image_name, image_slug,
                role, original_url, description_url, local_path, width,
                height, mime, sha1, variant_key, variant_type,
                variant_label, is_variant, is_primary, confidence
            )
            values (?, ?, ?, 'page_reference', null, ?, ?, ?, ?, null, ?, ?,
                    null, null, null, null, ?, ?, ?, ?, 0, ?)
            """,
            (
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["raw_page_id"]),
                int(row["page_image_id"]),
                str(row["image_name"]),
                str(row["image_slug"]),
                str(row["role"]),
                row["description_url"],
                row["local_path"],
                variant_key,
                str(row["variant_type"] or ""),
                str(row["variant_label"] or ""),
                int(bool(variant_key)),
                float(row["confidence"] if row["confidence"] is not None else 0.5),
            ),
        )
        count += 1
    return count


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
