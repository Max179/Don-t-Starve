from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Any

from dst_wiki_db.identity import extract_spawn_codes


ATTRIBUTE_FIELDS = {
    "biome": "biome",
    "spawn_code": "spawn_code",
    "spawn_code1": "spawn_code",
    "spawn_code2": "spawn_code",
    "renew": "renew",
    "tool": "tool",
    "perk": "perk",
    "special_ability": "special_ability",
    "growth_formula": "growth_formula",
    "seasons": "seasons",
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


def rebuild_entity_world_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_world_profiles")
    grouped: dict[int, dict[str, Any]] = {}

    for row in _attribute_rows(conn):
        bucket = _bucket(grouped, row)
        field = ATTRIBUTE_FIELDS[str(row["canonical_name"])]
        bucket["attribute_count"] = int(bucket["attribute_count"]) + 1
        bucket["source_ids"].add(int(row["source_id"]))
        variant_key = str(row["variant_key"] or "").strip()
        if variant_key:
            bucket["variant_keys"].add(variant_key)
        texts = bucket["texts"]
        if field == "spawn_code":
            values = extract_spawn_codes(str(row["value_text"]))
            if values:
                for value in values:
                    texts.setdefault(field, TextAggregate()).add(value)
                continue
        texts.setdefault(field, TextAggregate()).add(str(row["value_text"]))

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
        if field == "renew":
            bucket["texts"].setdefault("renew", TextAggregate()).add(
                str(row["value_texts"])
            )

    count = 0
    for bucket in grouped.values():
        if not bucket["texts"] and not bucket["stats"]:
            continue
        identity = bucket["identity"]
        texts = bucket["texts"]
        stats = bucket["stats"]
        renew_text = _text(texts, "renew")
        conn.execute(
            """
            insert into entity_world_profiles (
                entity_id, slug, canonical_title, kind,
                biome_text, spawn_code_text, renew_text, resources_min,
                resources_max, resources_text, tool_text, perk_text,
                special_ability_text, growth_formula_text, seasons_text,
                health_min, health_max, health_text,
                damage_min, damage_max, damage_text,
                attack_range_min, attack_range_max, attack_range_text,
                attack_period_min, attack_period_max, attack_period_text,
                attribute_count, stat_count, source_count, variant_count,
                has_biome, has_spawn_code, is_renewable, has_resources,
                has_growth_data, has_combat_stats, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["slug"]),
                str(identity["canonical_title"]),
                str(identity["kind"]),
                _text(texts, "biome"),
                _text(texts, "spawn_code"),
                renew_text,
                _minimum(stats, "resources"),
                _maximum(stats, "resources"),
                _stat_text(stats, "resources"),
                _text(texts, "tool"),
                _text(texts, "perk"),
                _text(texts, "special_ability"),
                _text(texts, "growth_formula"),
                _text(texts, "seasons"),
                _minimum(stats, "health"),
                _maximum(stats, "health"),
                _stat_text(stats, "health"),
                _minimum(stats, "damage"),
                _maximum(stats, "damage"),
                _stat_text(stats, "damage"),
                _minimum(stats, "attack_range"),
                _maximum(stats, "attack_range"),
                _stat_text(stats, "attack_range"),
                _minimum(stats, "attack_period"),
                _maximum(stats, "attack_period"),
                _stat_text(stats, "attack_period"),
                int(bucket["attribute_count"]),
                int(bucket["stat_count"]),
                len(bucket["source_ids"]) + int(bucket["rollup_source_count"]),
                len(bucket["variant_keys"]) + int(bucket["rollup_variant_count"]),
                int(bool(_text(texts, "biome"))),
                int(bool(_text(texts, "spawn_code"))),
                int(_is_renewable(renew_text)),
                int("resources" in stats),
                int(bool(_text(texts, "growth_formula") or _text(texts, "seasons"))),
                int(
                    any(
                        name in stats
                        for name in (
                            "health",
                            "damage",
                            "attack_range",
                            "attack_period",
                        )
                    )
                ),
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
        where e.kind in ('plant', 'structure', 'biome')
          and a.canonical_name in (
            'biome', 'spawn_code', 'spawn_code1', 'spawn_code2', 'renew',
            'tool', 'perk', 'special_ability', 'growth_formula', 'seasons'
          )
          and a.value_text != ''
        order by e.slug, a.canonical_name, a.id
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
        where kind in ('plant', 'structure', 'biome')
          and stat_name in (
            'health', 'damage', 'attack_range', 'attack_period',
            'resources', 'renew'
          )
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


def _is_renewable(text: str) -> bool:
    lowered = text.lower()
    if not lowered:
        return False
    if any(token in lowered for token in ("world regrowth", "cave regeneration", "yes")):
        return True
    return False
