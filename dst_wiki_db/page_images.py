from __future__ import annotations

import json
import sqlite3
from typing import Iterable, Mapping
from urllib.parse import quote

from dst_wiki_db.schema import slugify


PAGE_IMAGE_ROLE = "page_reference"


def rebuild_page_images(conn: sqlite3.Connection) -> int:
    conn.execute("delete from page_images")
    rows = conn.execute(
        """
        select
            es.entity_id,
            es.source_id,
            es.raw_page_id,
            rp.images_json,
            s.base_url
        from entity_sources es
        join raw_pages rp on rp.id = es.raw_page_id
        join sources s on s.id = es.source_id
        where rp.images_json is not null and rp.images_json != ''
        order by es.entity_id, es.source_id, es.raw_page_id
        """
    ).fetchall()

    count = 0
    seen = set()
    for row in rows:
        entity_id = int(row["entity_id"])
        source_id = int(row["source_id"])
        raw_page_id = int(row["raw_page_id"])
        for image_title, image_name in _page_image_entries(row["images_json"]):
            image_slug = slugify(image_name)
            if not image_slug:
                continue
            key = (entity_id, source_id, raw_page_id, image_slug, PAGE_IMAGE_ROLE)
            if key in seen:
                continue
            seen.add(key)
            conn.execute(
                """
                insert into page_images (
                    entity_id, source_id, raw_page_id, image_title, image_name,
                    image_slug, role, description_url
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    source_id,
                    raw_page_id,
                    image_title,
                    image_name,
                    image_slug,
                    PAGE_IMAGE_ROLE,
                    _description_url(str(row["base_url"] or ""), image_title),
                ),
            )
            count += 1
    conn.commit()
    return count


def _page_image_entries(images_json: str) -> Iterable[tuple[str, str]]:
    try:
        rows = json.loads(images_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list):
        return []
    entries = []
    for row in rows:
        title = _image_title(row)
        if not title:
            continue
        image_title, image_name = _normalize_image_title(title)
        if image_name:
            entries.append((image_title, image_name))
    return entries


def _image_title(row: object) -> str:
    if isinstance(row, str):
        title = row
    elif isinstance(row, Mapping):
        ns = row.get("ns")
        title = str(row.get("title") or row.get("*") or row.get("name") or "")
        if ns is not None and not _is_file_namespace(ns) and not _has_file_prefix(title):
            return ""
    else:
        return ""
    return " ".join(title.split()).strip()


def _normalize_image_title(title: str) -> tuple[str, str]:
    if ":" in title and _has_file_prefix(title):
        image_name = title.split(":", 1)[1].strip()
    else:
        image_name = title.strip()
    return f"File:{image_name}", image_name


def _has_file_prefix(title: str) -> bool:
    lowered = title.lower()
    return lowered.startswith("file:") or lowered.startswith("image:")


def _is_file_namespace(ns: object) -> bool:
    try:
        return int(ns) == 6
    except (TypeError, ValueError):
        return False


def _description_url(base_url: str, image_title: str) -> str | None:
    if not base_url:
        return None
    encoded = quote(image_title.replace(" ", "_"), safe=":")
    return f"{base_url.rstrip('/')}/wiki/{encoded}"
