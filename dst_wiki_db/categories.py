from __future__ import annotations

import json
import sqlite3
from typing import Iterable, Mapping

from dst_wiki_db.schema import slugify


def rebuild_entity_categories(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_categories")
    rows = conn.execute(
        """
        select
            es.entity_id,
            es.source_id,
            es.raw_page_id,
            rp.categories_json
        from entity_sources es
        join raw_pages rp on rp.id = es.raw_page_id
        where rp.categories_json is not null and rp.categories_json != ''
        order by es.entity_id, es.source_id, es.raw_page_id
        """
    ).fetchall()

    count = 0
    seen = set()
    for row in rows:
        for category_name in _category_names(row["categories_json"]):
            category_slug = slugify(category_name)
            key = (
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["raw_page_id"]),
                category_slug,
            )
            if key in seen:
                continue
            seen.add(key)
            conn.execute(
                """
                insert into entity_categories (
                    entity_id, source_id, raw_page_id, category_name, category_slug
                )
                values (?, ?, ?, ?, ?)
                """,
                (
                    int(row["entity_id"]),
                    int(row["source_id"]),
                    int(row["raw_page_id"]),
                    category_name,
                    category_slug,
                ),
            )
            count += 1
    conn.commit()
    return count


def _category_names(categories_json: str) -> Iterable[str]:
    try:
        rows = json.loads(categories_json or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(rows, list):
        return []
    names = []
    for row in rows:
        name = _category_name(row)
        if name:
            names.append(name)
    return names


def _category_name(row: object) -> str:
    if isinstance(row, str):
        title = row
    elif isinstance(row, Mapping):
        title = str(row.get("title") or row.get("*") or "")
    else:
        return ""
    if title.lower().startswith("category:"):
        title = title.split(":", 1)[1]
    return " ".join(title.split()).strip()
