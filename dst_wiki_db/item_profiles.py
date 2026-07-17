from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Any


@dataclass
class ItemAggregate:
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
        text = str(row["value_texts"] or "").strip()
        if text:
            self.texts.add(text)

    @property
    def text(self) -> str:
        return " | ".join(sorted(self.texts))


def rebuild_entity_item_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_item_profiles")
    grouped: dict[int, dict[str, Any]] = {}
    for row in _rows(conn):
        entity_id = int(row["entity_id"])
        bucket = grouped.setdefault(
            entity_id,
            {
                "identity": row,
                "stats": {},
                "stat_count": 0,
                "source_count": 0,
                "variant_count": 0,
            },
        )
        bucket["stat_count"] = int(bucket["stat_count"]) + int(row["evidence_count"])
        bucket["source_count"] = int(bucket["source_count"]) + int(row["source_count"])
        bucket["variant_count"] = int(bucket["variant_count"]) + int(row["variant_count"])
        stats = bucket["stats"]
        aggregate = stats.setdefault(str(row["stat_name"]), ItemAggregate())
        aggregate.add(row)

    count = 0
    for bucket in grouped.values():
        stats = bucket["stats"]
        if not stats:
            continue
        identity = bucket["identity"]
        conn.execute(
            """
            insert into entity_item_profiles (
                entity_id, slug, canonical_title, kind,
                damage_min, damage_max, damage_text,
                durability_min, durability_max, durability_text,
                protection_min, protection_max, protection_text,
                water_resistance_min, water_resistance_max, water_resistance_text,
                stack_min, stack_max, stack_text,
                stacklimit_min, stacklimit_max, stacklimit_text,
                burn_time_seconds_min, burn_time_seconds_max, burn_time_text,
                tier_min, tier_max, tier_text,
                resources_min, resources_max, resources_text,
                renew_min, renew_max, renew_text,
                priority_min, priority_max, priority_text,
                stat_count, source_count, variant_count,
                has_weapon_stats, has_armor_stats, has_stack_stats, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["slug"]),
                str(identity["canonical_title"]),
                str(identity["kind"]),
                _minimum(stats, "damage"),
                _maximum(stats, "damage"),
                _text(stats, "damage"),
                _minimum(stats, "durability"),
                _maximum(stats, "durability"),
                _text(stats, "durability"),
                _minimum(stats, "protection"),
                _maximum(stats, "protection"),
                _text(stats, "protection"),
                _minimum(stats, "water_resistance"),
                _maximum(stats, "water_resistance"),
                _text(stats, "water_resistance"),
                _minimum(stats, "stack"),
                _maximum(stats, "stack"),
                _text(stats, "stack"),
                _minimum(stats, "stacklimit"),
                _maximum(stats, "stacklimit"),
                _text(stats, "stacklimit"),
                _minimum(stats, "burn_time"),
                _maximum(stats, "burn_time"),
                _text(stats, "burn_time"),
                _minimum(stats, "tier"),
                _maximum(stats, "tier"),
                _text(stats, "tier"),
                _minimum(stats, "resources"),
                _maximum(stats, "resources"),
                _text(stats, "resources"),
                _minimum(stats, "renew"),
                _maximum(stats, "renew"),
                _text(stats, "renew"),
                _minimum(stats, "priority"),
                _maximum(stats, "priority"),
                _text(stats, "priority"),
                int(bucket["stat_count"]),
                int(bucket["source_count"]),
                int(bucket["variant_count"]),
                int("damage" in stats),
                int(any(name in stats for name in ("protection", "water_resistance"))),
                int(any(name in stats for name in ("stack", "stacklimit"))),
            ),
        )
        count += 1
    conn.commit()
    return count


def _rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            entity_id,
            slug,
            canonical_title,
            kind,
            stat_name,
            stat_type,
            unit,
            value_min,
            value_max,
            evidence_count,
            source_count,
            variant_count,
            value_texts
        from entity_stat_rollups
        where stat_name in (
            'damage', 'durability', 'protection', 'water_resistance',
            'stack', 'stacklimit', 'burn_time', 'tier', 'resources',
            'renew', 'priority'
        )
          and kind in ('item', 'food')
          and (
            stat_type = 'item'
            or (stat_name = 'damage' and stat_type = 'combat')
          )
        order by slug, stat_name, stat_type, unit
        """
    ).fetchall()


def _minimum(stats: dict[str, ItemAggregate], name: str) -> float | None:
    aggregate = stats.get(name)
    return aggregate.minimum if aggregate else None


def _maximum(stats: dict[str, ItemAggregate], name: str) -> float | None:
    aggregate = stats.get(name)
    return aggregate.maximum if aggregate else None


def _text(stats: dict[str, ItemAggregate], name: str) -> str:
    aggregate = stats.get(name)
    return aggregate.text if aggregate else ""
