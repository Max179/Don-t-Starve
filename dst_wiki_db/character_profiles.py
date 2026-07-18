from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Any

from dst_wiki_db.identity import extract_spawn_codes


ATTRIBUTE_FIELDS = {
    "nick",
    "motto",
    "birthday",
    "gender",
    "species",
    "voice",
    "games",
    "perk",
    "survivability",
    "bio",
    "favorite_food",
    "start_item",
    "item",
}

@dataclass
class TextAggregate:
    values: set[str] = field(default_factory=set)

    def add(self, value: str) -> None:
        text = " ".join(str(value or "").split())
        if text:
            self.values.add(text)

    @property
    def text(self) -> str:
        return " | ".join(sorted(self.values))


@dataclass
class StatAggregate:
    minimum: float | None = None
    maximum: float | None = None
    texts: set[str] = field(default_factory=set)

    def add(self, row: sqlite3.Row) -> None:
        if row["value_min"] is not None:
            value = float(row["value_min"])
            self.minimum = value if self.minimum is None else min(self.minimum, value)
        if row["value_max"] is not None:
            value = float(row["value_max"])
            self.maximum = value if self.maximum is None else max(self.maximum, value)
        text = " ".join(str(row["value_texts"] or "").split())
        if text:
            self.texts.add(text)

    @property
    def text(self) -> str:
        return " | ".join(sorted(self.texts))


def rebuild_entity_character_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_character_profiles")
    grouped: dict[int, dict[str, Any]] = {}

    for row in _attribute_rows(conn):
        bucket = _bucket(grouped, row)
        bucket["attribute_count"] = int(bucket["attribute_count"]) + 1
        bucket["source_ids"].add(int(row["source_id"]))
        variant_key = str(row["variant_key"] or "").strip()
        if variant_key:
            bucket["variant_keys"].add(variant_key)
        field = str(row["canonical_name"])
        bucket["texts"].setdefault(field, TextAggregate()).add(str(row["value_text"]))

    for row in _spawn_code_rows(conn):
        bucket = _bucket(grouped, row)
        bucket["attribute_count"] = int(bucket["attribute_count"]) + 1
        bucket["source_ids"].add(int(row["source_id"]))
        for code in extract_spawn_codes(str(row["value_text"])):
            bucket["texts"].setdefault("spawn_code", TextAggregate()).add(code)

    for row in _stat_rows(conn):
        bucket = _bucket(grouped, row)
        field = str(row["stat_name"])
        bucket["stat_count"] = int(bucket["stat_count"]) + int(row["evidence_count"])
        bucket["rollup_source_count"] = int(bucket["rollup_source_count"]) + int(
            row["source_count"]
        )
        bucket["rollup_variant_count"] = int(bucket["rollup_variant_count"]) + int(
            row["variant_count"]
        )
        bucket["stats"].setdefault(field, StatAggregate()).add(row)

    count = 0
    for bucket in grouped.values():
        if not bucket["texts"] and not bucket["stats"]:
            continue
        identity = bucket["identity"]
        texts = bucket["texts"]
        stats = bucket["stats"]
        conn.execute(
            """
            insert into entity_character_profiles (
                entity_id, slug, canonical_title, kind,
                nick_text, motto_text, birthday_text, gender_text,
                species_text, voice_text, games_text, spawn_code_text,
                perk_text, survivability_text, bio_text, favorite_food_text,
                start_item_text, character_item_text,
                health_min, health_max, health_text,
                hunger_min, hunger_max, hunger_text,
                sanity_min, sanity_max, sanity_text,
                damage_min, damage_max, damage_text,
                attribute_count, stat_count, source_count, variant_count,
                has_core_stats, has_perks, has_start_items, has_bio,
                updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["slug"]),
                str(identity["canonical_title"]),
                str(identity["kind"]),
                _text(texts, "nick"),
                _text(texts, "motto"),
                _text(texts, "birthday"),
                _text(texts, "gender"),
                _text(texts, "species"),
                _text(texts, "voice"),
                _text(texts, "games"),
                _text(texts, "spawn_code"),
                _text(texts, "perk"),
                _text(texts, "survivability"),
                _text(texts, "bio"),
                _text(texts, "favorite_food"),
                _text(texts, "start_item"),
                _text(texts, "item"),
                _minimum(stats, "health"),
                _maximum(stats, "health"),
                _stat_text(stats, "health"),
                _minimum(stats, "hunger"),
                _maximum(stats, "hunger"),
                _stat_text(stats, "hunger"),
                _minimum(stats, "sanity"),
                _maximum(stats, "sanity"),
                _stat_text(stats, "sanity"),
                _minimum(stats, "damage"),
                _maximum(stats, "damage"),
                _stat_text(stats, "damage"),
                int(bucket["attribute_count"]),
                int(bucket["stat_count"]),
                len(bucket["source_ids"]) + int(bucket["rollup_source_count"]),
                len(bucket["variant_keys"]) + int(bucket["rollup_variant_count"]),
                int(all(name in stats for name in ("health", "hunger", "sanity"))),
                int(bool(_text(texts, "perk"))),
                int(bool(_text(texts, "start_item") or _text(texts, "item"))),
                int(bool(_text(texts, "bio"))),
            ),
        )
        count += 1
    conn.commit()
    return count


def _bucket(grouped: dict[int, dict[str, Any]], row: sqlite3.Row) -> dict[str, Any]:
    entity_id = int(row["entity_id"])
    return grouped.setdefault(
        entity_id,
        {
            "identity": row,
            "texts": {},
            "stats": {},
            "attribute_count": 0,
            "stat_count": 0,
            "source_ids": set(),
            "variant_keys": set(),
            "rollup_source_count": 0,
            "rollup_variant_count": 0,
        },
    )


def _attribute_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            a.source_id,
            a.canonical_name,
            a.value_text,
            a.variant_key
        from entities e
        join entity_attributes a on a.entity_id = e.id
        where e.kind = 'character'
          and a.canonical_name in (
            'nick', 'motto', 'birthday', 'gender', 'species', 'voice',
            'games', 'perk', 'survivability', 'bio', 'favorite_food',
            'start_item', 'item'
          )
          and a.value_text != ''
        order by e.slug, a.canonical_name, a.id
        """
    ).fetchall()


def _spawn_code_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            a.source_id,
            a.canonical_name,
            a.value_text,
            a.variant_key
        from entities e
        join entity_attributes a on a.entity_id = e.id
        where e.kind = 'character'
          and a.canonical_name in ('spawn_code', 'spawn_code1', 'spawn_code2')
          and a.value_text != ''
        order by e.slug, a.id
        """
    ).fetchall()


def _stat_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            entity_id,
            slug,
            canonical_title,
            kind,
            stat_name,
            value_min,
            value_max,
            evidence_count,
            source_count,
            variant_count,
            value_texts
        from entity_stat_rollups
        where kind = 'character'
          and stat_name in ('health', 'hunger', 'sanity', 'damage')
        order by slug, stat_name, id
        """
    ).fetchall()


def _text(texts: dict[str, TextAggregate], name: str) -> str:
    aggregate = texts.get(name)
    return aggregate.text if aggregate else ""


def _minimum(stats: dict[str, StatAggregate], name: str) -> float | None:
    aggregate = stats.get(name)
    return aggregate.minimum if aggregate else None


def _maximum(stats: dict[str, StatAggregate], name: str) -> float | None:
    aggregate = stats.get(name)
    return aggregate.maximum if aggregate else None


def _stat_text(stats: dict[str, StatAggregate], name: str) -> str:
    aggregate = stats.get(name)
    return aggregate.text if aggregate else ""
