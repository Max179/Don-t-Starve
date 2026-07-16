from __future__ import annotations

import re
import sqlite3
from typing import Iterable, List


QUOTED_CODE_RE = re.compile(r'"([^"]+)"')
BARE_CODE_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_./-]*")


def extract_spawn_codes(value: str) -> List[str]:
    quoted = [match.strip() for match in QUOTED_CODE_RE.findall(value or "") if match.strip()]
    if quoted:
        return _dedupe(quoted)
    return _dedupe(BARE_CODE_RE.findall(value or ""))


def rebuild_identity_keys(conn: sqlite3.Connection) -> int:
    conn.execute("delete from cross_source_matches")
    conn.execute("delete from entity_identity_keys")
    count = 0
    count += _insert_title_keys(conn)
    count += _insert_spawn_code_keys(conn)
    count += _insert_image_keys(conn)
    _insert_cross_source_matches(conn)
    conn.commit()
    return count


def _insert_title_keys(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select es.entity_id, es.source_id, es.raw_page_id, e.slug
        from entity_sources es
        join entities e on e.id = es.entity_id
        where e.slug != ''
        """
    ).fetchall()
    count = 0
    for row in rows:
        count += _insert_key(
            conn,
            int(row["entity_id"]),
            int(row["source_id"]),
            int(row["raw_page_id"]),
            "title_slug",
            str(row["slug"]),
            "entities.slug",
            0.7,
        )
    return count


def _insert_spawn_code_keys(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select entity_id, source_id, raw_page_id, raw_name, value_text
        from entity_attributes
        where canonical_name in ('spawn_code', 'spawn_code1', 'spawn_code2')
          and value_text is not null
          and value_text != ''
        """
    ).fetchall()
    count = 0
    for row in rows:
        for code in extract_spawn_codes(str(row["value_text"])):
            count += _insert_key(
                conn,
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["raw_page_id"]),
                "spawn_code",
                code.lower(),
                str(row["raw_name"]),
                0.98,
            )
    return count


def _insert_image_keys(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select entity_id, source_id, raw_page_id, image_name, sha1
        from entity_images
        where image_name is not null and image_name != ''
        """
    ).fetchall()
    count = 0
    for row in rows:
        image_name = str(row["image_name"])
        count += _insert_key(
            conn,
            int(row["entity_id"]),
            int(row["source_id"]),
            int(row["raw_page_id"] or 0),
            "image_name",
            image_name.strip().lower(),
            "entity_images.image_name",
            0.75,
        )
        sha1 = row["sha1"]
        if sha1:
            count += _insert_key(
                conn,
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["raw_page_id"] or 0),
                "image_sha1",
                str(sha1).strip().lower(),
                "entity_images.sha1",
                0.95,
            )
    return count


def _insert_cross_source_matches(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select
            a.entity_id as left_entity_id,
            b.entity_id as right_entity_id,
            a.key_type,
            a.key_value,
            max(min(a.confidence, b.confidence)) as confidence
        from entity_identity_keys a
        join entity_identity_keys b
          on b.key_type = a.key_type
         and b.key_value = a.key_value
         and b.entity_id > a.entity_id
         and b.source_id != a.source_id
        group by a.entity_id, b.entity_id, a.key_type, a.key_value
        """
    ).fetchall()
    count = 0
    for row in rows:
        conn.execute(
            """
            insert or ignore into cross_source_matches (
                left_entity_id, right_entity_id, key_type, key_value, confidence, match_method
            )
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["left_entity_id"]),
                int(row["right_entity_id"]),
                str(row["key_type"]),
                str(row["key_value"]),
                float(row["confidence"]),
                "shared_identity_key",
            ),
        )
        count += 1
    return count


def _insert_key(
    conn: sqlite3.Connection,
    entity_id: int,
    source_id: int,
    raw_page_id: int,
    key_type: str,
    key_value: str,
    source_field: str,
    confidence: float,
) -> int:
    if not key_value:
        return 0
    cursor = conn.execute(
        """
        insert or ignore into entity_identity_keys (
            entity_id, source_id, raw_page_id, key_type, key_value, source_field, confidence
        )
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, source_id, raw_page_id or None, key_type, key_value, source_field, confidence),
    )
    return 1 if cursor.rowcount == 1 else 0


def _dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = value.strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result
