from __future__ import annotations

import json
import re
import sqlite3
from typing import Iterable


MIN_TITLE_LENGTH = 4
CORE_OFFICIAL_TITLES = {"Don't Starve", "Don't Starve Together"}
ALWAYS_MENTIONABLE_KINDS = {"boss", "character", "mob"}
SKIP_TITLES = {
    "Abyss",
    "Adventure Mode",
    "Art",
    "Caves",
    "Food",
    "Inventory",
    "Items",
    "Map",
    "Mobs",
    "Night",
    "Seasons",
    "Structures",
}


def rebuild_official_record_mentions(conn: sqlite3.Connection) -> int:
    conn.execute("delete from official_record_mentions")
    records = conn.execute(
        """
        select id, provider, record_type, external_id, title, summary, payload_json
        from official_records
        where status in ('ok', 'listed')
        order by id
        """
    ).fetchall()
    entities = _mentionable_entities(conn)

    count = 0
    seen = set()
    for record in records:
        fields = _record_fields(record)
        for entity in entities:
            entity_title = str(entity["canonical_title"])
            pattern = _title_pattern(entity_title)
            for field_name, text in fields:
                match = pattern.search(text)
                if not match:
                    continue
                mention_text = match.group(0)
                key = (int(record["id"]), int(entity["id"]), field_name, mention_text)
                if key in seen:
                    continue
                seen.add(key)
                conn.execute(
                    """
                    insert into official_record_mentions (
                        official_record_id, entity_id, provider, record_type, external_id,
                        entity_title, mention_text, match_field, match_method,
                        confidence, context_text
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(record["id"]),
                        int(entity["id"]),
                        str(record["provider"]),
                        str(record["record_type"]),
                        str(record["external_id"]),
                        entity_title,
                        mention_text,
                        field_name,
                        "canonical_title_phrase",
                        0.95,
                        _context(text, match.start(), match.end()),
                    ),
                )
                count += 1
                break
    conn.commit()
    return count


def _mentionable_entities(conn: sqlite3.Connection):
    rows = conn.execute(
        """
        select id, canonical_title, kind
        from entities
        where length(canonical_title) >= ?
        order by length(canonical_title) desc, canonical_title
        """,
        (MIN_TITLE_LENGTH,),
    ).fetchall()
    return [row for row in rows if _is_mentionable(row["canonical_title"], row["kind"])]


def _record_fields(record) -> list[tuple[str, str]]:
    fields = [
        ("title", str(record["title"] or "")),
        ("summary", str(record["summary"] or "")),
    ]
    payload_text = _payload_text(str(record["payload_json"] or "{}"))
    if payload_text:
        fields.append(("payload", payload_text))
    return [(name, text) for name, text in fields if text]


def _payload_text(payload_json: str) -> str:
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError:
        return payload_json
    parts = list(_string_values(payload))
    return " ".join(parts)


def _string_values(value: object) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _string_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _string_values(child)


def _title_pattern(title: str) -> re.Pattern[str]:
    if title in SKIP_TITLES:
        return re.compile(r"a^")
    escaped = re.escape(title)
    return re.compile(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])", re.IGNORECASE)


def _is_mentionable(title: str, kind: str) -> bool:
    if title in SKIP_TITLES:
        return False
    if title in CORE_OFFICIAL_TITLES:
        return True
    if kind in ALWAYS_MENTIONABLE_KINDS:
        return True
    return _word_count(title) >= 2


def _word_count(title: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", title))


def _context(text: str, start: int, end: int, *, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())
