from __future__ import annotations

import sqlite3
from typing import Any, Iterable

from dst_wiki_db.build import SOURCE_DEFINITIONS, register_reference_sources, source_url
from dst_wiki_db.mediawiki import MediaWikiClient
from dst_wiki_db.schema import slugify, upsert_source


ALIAS_TYPE_PRIORITY = {
    "canonical_title": 0,
    "canonical_slug": 1,
    "source_title": 2,
    "source_slug": 3,
    "prefab_code": 8,
    "image_stem": 9,
    "image_name": 10,
}

GAME_VARIANT_SUFFIXES = {
    "ds",
    "dst",
    "dont-starve",
    "dont-starve-together",
}


def fetch_source_page_index(
    conn: sqlite3.Connection,
    *,
    source_key: str,
    limit: int | None = None,
    sleep_seconds: float = 0.05,
    client: Any | None = None,
) -> dict[str, int | str]:
    register_reference_sources(conn)
    source = SOURCE_DEFINITIONS[source_key]
    source_id = _source_id(conn, source_key)
    mediawiki = client or MediaWikiClient(
        key=source.key,
        api_url=source.api_url,
        sleep_seconds=sleep_seconds,
    )
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
    rows = list(_iter_pages(mediawiki, limit=limit))
    conn.execute("delete from source_page_entity_matches where source_key = ?", (source_key,))
    conn.execute("delete from source_page_index where source_key = ?", (source_key,))
    inserted = 0
    for row in rows:
        title = str(row.get("title", "")).strip()
        if not title:
            continue
        cursor = conn.execute(
            """
            insert or ignore into source_page_index (
                source_id, source_key, source_pageid, ns, title, title_slug,
                page_url, index_status, fetched_at
            )
            values (?, ?, ?, ?, ?, ?, ?, 'listed', current_timestamp)
            """,
            (
                source_id,
                source_key,
                int(row.get("pageid", 0)),
                int(row.get("ns", 0)),
                title,
                slugify(title),
                source_url(source.base_url, title),
            ),
        )
        inserted += 1 if cursor.rowcount == 1 else 0
    matched = rebuild_source_page_entity_matches(conn, source_key=source_key)
    conn.commit()
    return {
        "source_key": source_key,
        "source_page_index": inserted,
        "source_page_entity_matches": matched,
    }


def rebuild_source_page_entity_matches(
    conn: sqlite3.Connection, *, source_key: str | None = None
) -> int:
    if source_key:
        conn.execute("delete from source_page_entity_matches where source_key = ?", (source_key,))
        rows = conn.execute(
            """
            select id, source_key, source_pageid, title, title_slug
            from source_page_index
            where source_key = ?
            order by source_key, title_slug, source_pageid
            """,
            (source_key,),
        ).fetchall()
    else:
        conn.execute("delete from source_page_entity_matches")
        rows = conn.execute(
            """
            select id, source_key, source_pageid, title, title_slug
            from source_page_index
            order by source_key, title_slug, source_pageid
            """
        ).fetchall()

    count = 0
    for row in rows:
        match = _best_match(conn, row)
        if match is None:
            continue
        conn.execute(
            """
            insert or ignore into source_page_entity_matches (
                source_page_index_id, source_key, source_pageid, source_title,
                source_title_slug, entity_id, entity_slug, entity_title,
                entity_kind, match_method, confidence, matched_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                int(row["id"]),
                str(row["source_key"]),
                int(row["source_pageid"]),
                str(row["title"]),
                str(row["title_slug"]),
                int(match["entity_id"]),
                str(match["entity_slug"]),
                str(match["entity_title"]),
                str(match["entity_kind"]),
                str(match["match_method"]),
                float(match["confidence"]),
            ),
        )
        count += 1
    conn.commit()
    return count


def _best_match(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any] | None:
    title = str(row["title"])
    title_slug = str(row["title_slug"])
    candidate_keys = [(title_slug, "alias", 1.0)]
    if "/" in title:
        base_title, suffix = title.rsplit("/", 1)
        suffix_slug = slugify(suffix)
        if base_title and suffix_slug in GAME_VARIANT_SUFFIXES:
            candidate_keys.append((slugify(base_title), "alias_game_variant_suffix", 0.88))

    for alias_key, method_prefix, confidence_cap in candidate_keys:
        match = _best_alias_key_match(
            conn,
            alias_key=alias_key,
            title=title,
            method_prefix=method_prefix,
            confidence_cap=confidence_cap,
        )
        if match is not None:
            return match
    return None


def _best_alias_key_match(
    conn: sqlite3.Connection,
    *,
    alias_key: str,
    title: str,
    method_prefix: str,
    confidence_cap: float,
) -> dict[str, Any] | None:
    matches = conn.execute(
        """
        select
            ea.alias_type,
            ea.alias_value,
            ea.alias_key,
            ea.confidence as alias_confidence,
            e.id as entity_id,
            e.slug as entity_slug,
            e.canonical_title as entity_title,
            e.kind as entity_kind
        from entity_aliases ea
        join entities e on e.id = ea.entity_id
        where ea.alias_key = ?
        """,
        (alias_key,),
    ).fetchall()
    if not matches:
        return None

    def score(candidate: sqlite3.Row) -> tuple[float, int, int, int, str]:
        alias_type = str(candidate["alias_type"])
        exact_title = str(candidate["alias_value"]).casefold() == title.casefold()
        exact_entity_slug = str(candidate["entity_slug"]) == alias_key
        return (
            -min(float(candidate["alias_confidence"]), confidence_cap),
            ALIAS_TYPE_PRIORITY.get(alias_type, 99),
            0 if exact_title else 1,
            0 if exact_entity_slug else 1,
            str(candidate["entity_slug"]),
        )

    winner = sorted(matches, key=score)[0]
    return {
        "entity_id": int(winner["entity_id"]),
        "entity_slug": str(winner["entity_slug"]),
        "entity_title": str(winner["entity_title"]),
        "entity_kind": str(winner["entity_kind"]),
        "match_method": f"{method_prefix}:{winner['alias_type']}",
        "confidence": min(float(winner["alias_confidence"]), confidence_cap),
    }


def _iter_pages(mediawiki: Any, *, limit: int | None) -> Iterable[dict]:
    if hasattr(mediawiki, "iter_main_pages"):
        yield from mediawiki.iter_main_pages(limit=limit)
        return
    rows = mediawiki.fetch_pages(limit=limit)
    yield from rows


def _source_id(conn: sqlite3.Connection, source_key: str) -> int:
    row = conn.execute("select id from sources where key = ?", (source_key,)).fetchone()
    if row is None:
        raise ValueError(f"Unknown source: {source_key}")
    return int(row["id"])


def _now_from_db(conn: sqlite3.Connection) -> str:
    row = conn.execute("select current_timestamp as value").fetchone()
    return str(row["value"])


def _json_dumps(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False)
