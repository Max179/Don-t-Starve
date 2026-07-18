from __future__ import annotations

import re
import sqlite3
from typing import Any

from dst_wiki_db.schema import slugify
from dst_wiki_db.source_page_index import GAME_VARIANT_SUFFIXES


GUIDE_RE = re.compile(r"(^guides/|guide|overview|sandbox)", re.IGNORECASE)
COSMETIC_RE = re.compile(
    r"(skin|skins|curio|curios|costume|costumes|belonging|belongings|figure|sketch)",
    re.IGNORECASE,
)
EVENT_RE = re.compile(
    r"(year of|winter'?s feast|hallowed nights|midsummer cawnival|beefalo pageant|cawnival|carnival|event)",
    re.IGNORECASE,
)


def rebuild_source_page_gaps(
    conn: sqlite3.Connection, *, source_key: str | None = None
) -> int:
    if source_key:
        conn.execute("delete from source_page_gaps where source_key = ?", (source_key,))
        params: tuple[object, ...] = (source_key,)
        source_filter = "and spi.source_key = ?"
    else:
        conn.execute("delete from source_page_gaps")
        params = ()
        source_filter = ""
    rows = conn.execute(
        f"""
        select
            spi.id,
            spi.source_key,
            spi.source_pageid,
            spi.title,
            spi.title_slug,
            spi.page_url
        from source_page_index spi
        left join source_page_entity_matches spm
          on spm.source_page_index_id = spi.id
        where spm.id is null
          {source_filter}
        order by spi.source_key, spi.title
        """,
        params,
    ).fetchall()
    count = 0
    for row in rows:
        gap = _classify_gap(row)
        conn.execute(
            """
            insert or ignore into source_page_gaps (
                source_page_index_id, source_key, source_pageid, title,
                title_slug, page_url, gap_type, priority, suggested_title,
                suggested_slug, notes, detected_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                int(row["id"]),
                str(row["source_key"]),
                int(row["source_pageid"]),
                str(row["title"]),
                str(row["title_slug"]),
                str(row["page_url"]),
                gap["gap_type"],
                gap["priority"],
                gap["suggested_title"],
                gap["suggested_slug"],
                gap["notes"],
            ),
        )
        count += 1
    conn.commit()
    return count


def _classify_gap(row: sqlite3.Row) -> dict[str, Any]:
    title = str(row["title"])
    suggested_title = ""
    suggested_slug = ""
    if "/" in title:
        base_title, suffix = title.rsplit("/", 1)
        suffix_slug = slugify(suffix)
        if base_title and suffix_slug in GAME_VARIANT_SUFFIXES:
            suggested_title = base_title
            suggested_slug = slugify(base_title)
            return {
                "gap_type": "unmatched_game_variant_page",
                "priority": 20,
                "suggested_title": suggested_title,
                "suggested_slug": suggested_slug,
                "notes": f"Game-version subpage has no matched base entity: {suffix}",
            }
        if GUIDE_RE.search(title):
            return _gap("guide_or_reference_page", 70, "Guide/reference subpage")
        if EVENT_RE.search(title):
            return _gap("event_or_seasonal_page", 55, "Event or seasonal subpage")
        return _gap("unmatched_subpage", 45, "Unmatched wiki subpage")
    if GUIDE_RE.search(title):
        return _gap("guide_or_reference_page", 70, "Guide/reference page")
    if EVENT_RE.search(title):
        return _gap("event_or_seasonal_page", 50, "Event or seasonal page")
    if COSMETIC_RE.search(title):
        return _gap("cosmetic_or_curio_page", 60, "Cosmetic, curio, figure, or sketch page")
    return _gap("potential_new_entity", 10, "Unmatched top-level page; review for new entity ingestion")


def _gap(gap_type: str, priority: int, notes: str) -> dict[str, Any]:
    return {
        "gap_type": gap_type,
        "priority": priority,
        "suggested_title": "",
        "suggested_slug": "",
        "notes": notes,
    }
