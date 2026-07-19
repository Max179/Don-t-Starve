from __future__ import annotations

import json
import re
import sqlite3
from typing import Iterable, Mapping
from urllib.parse import quote

from dst_wiki_db.schema import slugify


PAGE_IMAGE_ROLE = "page_reference"
GENERIC_PAGE_IMAGE_LIMIT = 80


def rebuild_page_images(conn: sqlite3.Connection) -> int:
    conn.execute("delete from page_images")
    rows = conn.execute(
        """
        select
            es.entity_id,
            es.source_id,
            es.raw_page_id,
            e.canonical_title,
            es.source_title,
            rp.title as raw_title,
            rp.images_json,
            s.base_url
        from entity_sources es
        join entities e on e.id = es.entity_id
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
        title_slugs = _title_slugs(
            str(row["canonical_title"] or ""),
            str(row["source_title"] or ""),
            str(row["raw_title"] or ""),
        )
        entries = _selected_page_image_entries(
            _page_image_entries(row["images_json"]),
            title_slugs=title_slugs,
        )
        for image_title, image_name in entries:
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


def _selected_page_image_entries(
    entries: Iterable[tuple[str, str]], *, title_slugs: set[str]
) -> list[tuple[str, str]]:
    selected: list[tuple[str, str]] = []
    generic_count = 0
    for image_title, image_name in entries:
        if _is_title_matched_image(image_name, title_slugs):
            selected.append((image_title, image_name))
            continue
        if generic_count < GENERIC_PAGE_IMAGE_LIMIT:
            selected.append((image_title, image_name))
            generic_count += 1
    return selected


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


def _title_slugs(*titles: str) -> set[str]:
    slugs: set[str] = set()
    for title in titles:
        for part in _title_parts(title):
            slug = slugify(part)
            if len(slug) >= 2:
                slugs.add(slug)
    return slugs


def _title_parts(title: str) -> list[str]:
    compact = " ".join(title.split()).strip()
    if not compact:
        return []
    parts = [compact]
    if "/" in compact:
        pieces = [part.strip() for part in compact.split("/") if part.strip()]
        parts.extend(pieces)
        if pieces and pieces[-1].lower() in {"ds", "dst"}:
            parts.append("/".join(pieces[:-1]))
    return parts


def _is_title_matched_image(image_name: str, title_slugs: set[str]) -> bool:
    image_slug = slugify(_image_stem(image_name))
    if not image_slug:
        return False
    return any(
        image_slug == title_slug
        or image_slug.startswith(f"{title_slug}-")
        or title_slug.startswith(f"{image_slug}-")
        for title_slug in title_slugs
    )


def _image_stem(image_name: str) -> str:
    return re.sub(r"\.(?:png|jpe?g|gif|webp|avif)$", "", image_name, flags=re.I)


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
