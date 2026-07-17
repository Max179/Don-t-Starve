from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Mapping


COMBAT_STATS = {"health", "damage", "attack_range", "attack_period"}
MOVEMENT_STATS = {"walk_speed", "run_speed"}


@dataclass
class StatAggregate:
    values: list[float] = field(default_factory=list)
    texts: set[str] = field(default_factory=set)
    evidence_ids: set[int] = field(default_factory=set)
    source_ids: set[int] = field(default_factory=set)
    variant_keys: set[str] = field(default_factory=set)

    def add(self, row: Mapping[str, object]) -> None:
        self.evidence_ids.add(int(row["stat_id"]))
        self.source_ids.add(int(row["source_id"]))
        text = str(row["value_text"] or "").strip()
        if text:
            self.texts.add(text)
        variant_key = str(row["variant_key"] or "").strip()
        if variant_key:
            self.variant_keys.add(variant_key)
        value = row["parsed_value"]
        if value is not None:
            self.values.append(float(value))

    @property
    def minimum(self) -> float | None:
        return min(self.values) if self.values else None

    @property
    def maximum(self) -> float | None:
        return max(self.values) if self.values else None

    @property
    def text(self) -> str:
        return " | ".join(sorted(self.texts))

    @property
    def evidence_count(self) -> int:
        return len(self.evidence_ids)


def rebuild_entity_combat_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_combat_profiles")
    entities = conn.execute(
        """
        select distinct e.id as entity_id, e.slug, e.canonical_title, e.kind
        from entities e
        join entity_stats s on s.entity_id = e.id
        where s.stat_name in (
            'health', 'damage', 'attack_range', 'attack_period',
            'walk_speed', 'run_speed'
        )
          and s.stat_type in ('combat', 'movement')
        order by e.slug
        """
    ).fetchall()
    stat_rows = _stat_rows(conn)
    count = 0
    for entity in entities:
        entity_id = int(entity["entity_id"])
        aggregates = stat_rows.get(entity_id, {})
        if not aggregates:
            continue
        combat_stat_count = sum(
            aggregates[name].evidence_count
            for name in COMBAT_STATS
            if name in aggregates
        )
        movement_stat_count = sum(
            aggregates[name].evidence_count
            for name in MOVEMENT_STATS
            if name in aggregates
        )
        if combat_stat_count == 0 and movement_stat_count == 0:
            continue
        source_ids = set()
        variant_keys = set()
        for aggregate in aggregates.values():
            source_ids.update(aggregate.source_ids)
            variant_keys.update(aggregate.variant_keys)
        conn.execute(
            """
            insert into entity_combat_profiles (
                entity_id, slug, canonical_title, kind,
                health_min, health_max, health_text, health_evidence_count,
                damage_min, damage_max, damage_text, damage_evidence_count,
                attack_range_min, attack_range_max, attack_range_text,
                attack_range_evidence_count,
                attack_period_min, attack_period_max, attack_period_text,
                attack_period_evidence_count,
                walk_speed_min, walk_speed_max, walk_speed_text,
                walk_speed_evidence_count,
                run_speed_min, run_speed_max, run_speed_text,
                run_speed_evidence_count,
                combat_stat_count, movement_stat_count, source_count,
                variant_count
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                str(entity["slug"]),
                str(entity["canonical_title"]),
                str(entity["kind"]),
                _minimum(aggregates, "health"),
                _maximum(aggregates, "health"),
                _text(aggregates, "health"),
                _evidence_count(aggregates, "health"),
                _minimum(aggregates, "damage"),
                _maximum(aggregates, "damage"),
                _text(aggregates, "damage"),
                _evidence_count(aggregates, "damage"),
                _minimum(aggregates, "attack_range"),
                _maximum(aggregates, "attack_range"),
                _text(aggregates, "attack_range"),
                _evidence_count(aggregates, "attack_range"),
                _minimum(aggregates, "attack_period"),
                _maximum(aggregates, "attack_period"),
                _text(aggregates, "attack_period"),
                _evidence_count(aggregates, "attack_period"),
                _minimum(aggregates, "walk_speed"),
                _maximum(aggregates, "walk_speed"),
                _text(aggregates, "walk_speed"),
                _evidence_count(aggregates, "walk_speed"),
                _minimum(aggregates, "run_speed"),
                _maximum(aggregates, "run_speed"),
                _text(aggregates, "run_speed"),
                _evidence_count(aggregates, "run_speed"),
                combat_stat_count,
                movement_stat_count,
                len(source_ids),
                len(variant_keys),
            ),
        )
        count += 1
    conn.commit()
    return count


def _stat_rows(conn: sqlite3.Connection) -> dict[int, dict[str, StatAggregate]]:
    rows = conn.execute(
        """
        select
            s.id as stat_id,
            s.entity_id,
            s.source_id,
            s.stat_name,
            s.value_text,
            s.value_number,
            s.variant_key,
            v.value_number as stat_value_number
        from entity_stats s
        left join entity_stat_values v on v.entity_stat_id = s.id
        where s.stat_name in (
            'health', 'damage', 'attack_range', 'attack_period',
            'walk_speed', 'run_speed'
        )
          and s.stat_type in ('combat', 'movement')
        order by s.entity_id, s.stat_name, s.id, v.value_index
        """
    ).fetchall()
    grouped: dict[int, dict[str, StatAggregate]] = {}
    seen_numbers: set[tuple[int, str, float | None]] = set()
    for row in rows:
        entity_id = int(row["entity_id"])
        stat_name = str(row["stat_name"])
        parsed_value = row["stat_value_number"]
        if parsed_value is None:
            parsed_value = row["value_number"]
        dedupe_key = (int(row["stat_id"]), stat_name, parsed_value)
        if dedupe_key in seen_numbers:
            continue
        seen_numbers.add(dedupe_key)
        mutable = dict(row)
        mutable["parsed_value"] = parsed_value
        aggregate = grouped.setdefault(entity_id, {}).setdefault(
            stat_name, StatAggregate()
        )
        aggregate.add(mutable)
    return grouped


def _minimum(aggregates: dict[str, StatAggregate], name: str) -> float | None:
    aggregate = aggregates.get(name)
    return aggregate.minimum if aggregate else None


def _maximum(aggregates: dict[str, StatAggregate], name: str) -> float | None:
    aggregate = aggregates.get(name)
    return aggregate.maximum if aggregate else None


def _text(aggregates: dict[str, StatAggregate], name: str) -> str:
    aggregate = aggregates.get(name)
    return aggregate.text if aggregate else ""


def _evidence_count(aggregates: dict[str, StatAggregate], name: str) -> int:
    aggregate = aggregates.get(name)
    return aggregate.evidence_count if aggregate else 0
