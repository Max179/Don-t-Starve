from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from typing import Iterable


MIN_TITLE_LENGTH = 4
CORE_OFFICIAL_TITLES = {"Don't Starve", "Don't Starve Together"}
ALWAYS_MENTIONABLE_KINDS = {"boss", "character", "mob"}
ALIAS_MATCH_TYPES = {"source_title", "prefab_code"}
CHARACTER_PREFAB_ALIAS_TYPES = {"prefab_code"}
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


@dataclass(frozen=True)
class MentionCandidate:
    phrase: str
    pattern: re.Pattern[str]
    match_method: str
    confidence: float


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
            candidates = entity["mention_candidates"]
            for field_name, text in fields:
                inserted = False
                for candidate in candidates:
                    match = candidate.pattern.search(text)
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
                            candidate.match_method,
                            candidate.confidence,
                            _context(text, match.start(), match.end()),
                        ),
                    )
                    count += 1
                    inserted = True
                    break
                if inserted:
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
    aliases_by_entity = _alias_candidates_by_entity(conn)
    mentionable = []
    for row in rows:
        title = str(row["canonical_title"])
        kind = str(row["kind"])
        candidates = []
        if _is_mentionable(title, kind):
            candidates.append(
                MentionCandidate(
                    phrase=title,
                    pattern=_title_pattern(title),
                    match_method="canonical_title_phrase",
                    confidence=0.95,
                )
            )
        candidates.extend(aliases_by_entity.get(int(row["id"]), []))
        if candidates:
            mentionable.append(
                {
                    "id": int(row["id"]),
                    "canonical_title": title,
                    "kind": kind,
                    "mention_candidates": candidates,
                }
            )
    return mentionable


def _alias_candidates_by_entity(conn: sqlite3.Connection) -> dict[int, list[MentionCandidate]]:
    rows = conn.execute(
        """
        select
            ea.entity_id,
            e.canonical_title,
            e.kind,
            ea.alias_type,
            ea.alias_value,
            ea.confidence
        from entity_aliases ea
        join entities e on e.id = ea.entity_id
        where ea.alias_type in ('source_title', 'prefab_code')
          and ea.confidence >= 0.9
        order by ea.entity_id, length(ea.alias_value) desc, ea.alias_type
        """
    ).fetchall()
    buckets: dict[int, list[MentionCandidate]] = {}
    seen: set[tuple[int, str]] = set()
    for row in rows:
        entity_id = int(row["entity_id"])
        title = str(row["canonical_title"])
        kind = str(row["kind"])
        alias_type = str(row["alias_type"])
        alias_value = str(row["alias_value"])
        alias_key = _alias_key(alias_value)
        if (entity_id, alias_key) in seen:
            continue
        if not _is_official_alias_candidate(
            alias_value=alias_value,
            alias_type=alias_type,
            canonical_title=title,
            kind=kind,
        ):
            continue
        seen.add((entity_id, alias_key))
        buckets.setdefault(entity_id, []).append(
            MentionCandidate(
                phrase=alias_value,
                pattern=_alias_pattern(alias_value),
                match_method=f"alias_{alias_type}_phrase",
                confidence=0.9 if alias_type == "source_title" else 0.86,
            )
        )
    return buckets


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


def _alias_pattern(alias_value: str) -> re.Pattern[str]:
    tokens = re.findall(r"[A-Za-z0-9]+", alias_value)
    escaped = [re.escape(token) for token in tokens]
    phrase = r"[\s_-]+".join(escaped)
    return re.compile(
        rf"(?<![A-Za-z0-9]){phrase}(?![A-Za-z0-9])",
        re.IGNORECASE,
    )


def _is_mentionable(title: str, kind: str) -> bool:
    if title in SKIP_TITLES:
        return False
    if title in CORE_OFFICIAL_TITLES:
        return True
    if kind in ALWAYS_MENTIONABLE_KINDS:
        return True
    return _word_count(title) >= 2


def _is_official_alias_candidate(
    *,
    alias_value: str,
    alias_type: str,
    canonical_title: str,
    kind: str,
) -> bool:
    if alias_type not in ALIAS_MATCH_TYPES:
        return False
    if "/" in canonical_title:
        return False
    if canonical_title in SKIP_TITLES:
        return False
    if _alias_key(alias_value) == _alias_key(canonical_title):
        return False
    word_count = _word_count(alias_value)
    if word_count == 0:
        return False
    if alias_type == "source_title":
        return _is_mentionable(alias_value, kind)
    if alias_type in CHARACTER_PREFAB_ALIAS_TYPES and kind == "character":
        return len(alias_value) >= MIN_TITLE_LENGTH
    return word_count >= 2


def _word_count(title: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", title))


def _alias_key(value: str) -> str:
    return "-".join(token.lower() for token in re.findall(r"[A-Za-z0-9]+", value))


def _context(text: str, start: int, end: int, *, radius: int = 80) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    return " ".join(text[left:right].split())
