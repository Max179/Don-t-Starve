from __future__ import annotations

import sqlite3
from typing import Any

from dst_wiki_db.build import (
    SOURCE_DEFINITIONS,
    register_reference_sources,
    source_url,
    write_parsed_page,
    write_raw_page,
)
from dst_wiki_db.mediawiki import MediaWikiClient, page_revision, page_wikitext
from dst_wiki_db.parser import parse_page
from dst_wiki_db.schema import upsert_source


def import_source_gap_pages(
    conn: sqlite3.Connection,
    *,
    source_key: str = "wiki.gg",
    gap_type: str = "potential_new_entity",
    limit: int = 10,
    batch_size: int = 10,
    sleep_seconds: float = 0.05,
    client: Any | None = None,
) -> dict[str, int | str]:
    register_reference_sources(conn)
    source = SOURCE_DEFINITIONS[source_key]
    mediawiki = client or MediaWikiClient(
        key=source.key,
        api_url=source.api_url,
        sleep_seconds=sleep_seconds,
    )
    source_id = _source_id(conn, source_key)
    siteinfo = mediawiki.fetch_siteinfo()
    upsert_source(
        conn,
        key=source.key,
        name=source.name,
        base_url=source.base_url,
        api_url=source.api_url,
        role=source.role,
        license=source.license,
        fetched_at=_now_from_db(conn),
        siteinfo_json=_json_dumps(siteinfo),
    )
    source_id = _source_id(conn, source_key)
    gap_rows = _gap_rows(conn, source_key=source_key, gap_type=gap_type, limit=limit)
    titles = [str(row["title"]) for row in gap_rows]
    pages_seen = 0
    pages_imported = 0
    entities_written = 0
    images_registered = 0
    imported_entity_ids: list[int] = []
    for title_batch in _batches(titles, max(1, batch_size)):
        pages = mediawiki.fetch_page_batch(title_batch)
        for page in pages:
            if page.get("missing"):
                continue
            pages_seen += 1
            raw_page_id = write_raw_page(conn, source_id, source, page)
            title = str(page.get("title", ""))
            text = page_wikitext(page)
            parsed = parse_page(title, text)
            revision = page_revision(page)
            entity_id = write_parsed_page(
                conn,
                source_id=source_id,
                raw_page_id=raw_page_id,
                source_title=title,
                source_pageid=int(page.get("pageid", 0)),
                source_revid=_optional_int(revision.get("revid")),
                source_timestamp=_optional_str(revision.get("timestamp")),
                page_url=source_url(source.base_url, title),
                parsed=parsed,
                primary=source.role == "canonical",
            )
            pages_imported += 1
            entities_written += 1
            images_registered += len(parsed.images)
            imported_entity_ids.append(entity_id)
        conn.commit()
    verification_count = _write_source_presence_checks(
        conn,
        source_key=source_key,
        source_id=source_id,
        entity_ids=imported_entity_ids,
    )
    return {
        "source_key": source_key,
        "gap_type": gap_type,
        "selected_gaps": len(titles),
        "pages_seen": pages_seen,
        "pages_imported": pages_imported,
        "entities_written": entities_written,
        "images_registered": images_registered,
        "verification_checks": verification_count,
    }


def _gap_rows(
    conn: sqlite3.Connection, *, source_key: str, gap_type: str, limit: int
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select title
        from source_page_gaps
        where source_key = ?
          and gap_type = ?
        order by priority, title
        limit ?
        """,
        (source_key, gap_type, limit),
    ).fetchall()


def _source_id(conn: sqlite3.Connection, source_key: str) -> int:
    row = conn.execute("select id from sources where key = ?", (source_key,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown source: {source_key}")
    return int(row["id"])


def _write_source_presence_checks(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    source_id: int,
    entity_ids: list[int],
) -> int:
    import json

    count = 0
    for entity_id in sorted(set(entity_ids)):
        cursor = conn.execute(
            """
            insert into verification_checks (
                entity_id, check_type, source_key, target_key, status, details_json
            )
            values (?, 'source_presence', ?, ?, 'present', ?)
            on conflict(entity_id, check_type, source_key, target_key) do update set
                status=excluded.status,
                details_json=excluded.details_json,
                checked_at=current_timestamp
            """,
            (
                entity_id,
                source_key,
                source_key,
                json.dumps({"source_id": source_id}, ensure_ascii=False),
            ),
        )
        count += 1 if cursor.rowcount == 1 else 0
    conn.commit()
    return count


def _now_from_db(conn: sqlite3.Connection) -> str:
    row = conn.execute("select current_timestamp as value").fetchone()
    return str(row["value"])


def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)


def _batches(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
