from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Any


RESTORE_MAP = {
    "health": "health",
    "hp_restored": "health",
    "hunger": "hunger",
    "hunger_restored": "hunger",
    "sanity": "sanity",
    "sanity_restored": "sanity",
}


@dataclass
class FoodAggregate:
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


def rebuild_entity_food_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_food_profiles")
    rows = _rows(conn)
    grouped: dict[int, dict[str, Any]] = {}
    for row in rows:
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
        key = _profile_key(str(row["stat_name"]))
        if key is None:
            continue
        stats = bucket["stats"]
        aggregate = stats.setdefault(key, FoodAggregate())
        aggregate.add(row)

    count = 0
    for bucket in grouped.values():
        stats = bucket["stats"]
        if not stats:
            continue
        identity = bucket["identity"]
        conn.execute(
            """
            insert into entity_food_profiles (
                entity_id, slug, canonical_title, kind,
                health_min, health_max, health_text,
                hunger_min, hunger_max, hunger_text,
                sanity_min, sanity_max, sanity_text,
                food_value_min, food_value_max, food_value_text,
                spoil_days_min, spoil_days_max, spoil_text,
                cooktime_seconds_min, cooktime_seconds_max, cooktime_text,
                priority_min, priority_max, priority_text,
                stat_count, source_count, variant_count,
                has_restore_stats, has_food_value, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["slug"]),
                str(identity["canonical_title"]),
                str(identity["kind"]),
                _minimum(stats, "health"),
                _maximum(stats, "health"),
                _text(stats, "health"),
                _minimum(stats, "hunger"),
                _maximum(stats, "hunger"),
                _text(stats, "hunger"),
                _minimum(stats, "sanity"),
                _maximum(stats, "sanity"),
                _text(stats, "sanity"),
                _minimum(stats, "food_value"),
                _maximum(stats, "food_value"),
                _text(stats, "food_value"),
                _minimum(stats, "spoil"),
                _maximum(stats, "spoil"),
                _text(stats, "spoil"),
                _minimum(stats, "cooktime"),
                _maximum(stats, "cooktime"),
                _text(stats, "cooktime"),
                _minimum(stats, "priority"),
                _maximum(stats, "priority"),
                _text(stats, "priority"),
                int(bucket["stat_count"]),
                int(bucket["source_count"]),
                int(bucket["variant_count"]),
                int(
                    any(name in stats for name in ("health", "hunger", "sanity"))
                ),
                int("food_value" in stats),
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
            'health', 'hp_restored', 'hunger', 'hunger_restored',
            'sanity', 'sanity_restored', 'food_value', 'spoil',
            'cooktime', 'priority'
        )
          and stat_type in ('food', 'survival', 'stat', 'item')
        order by slug, stat_name, stat_type, unit
        """
    ).fetchall()


def _profile_key(stat_name: str) -> str | None:
    if stat_name in RESTORE_MAP:
        return RESTORE_MAP[stat_name]
    if stat_name in {"food_value", "spoil", "cooktime", "priority"}:
        return stat_name
    return None


def _minimum(stats: dict[str, FoodAggregate], name: str) -> float | None:
    aggregate = stats.get(name)
    return aggregate.minimum if aggregate else None


def _maximum(stats: dict[str, FoodAggregate], name: str) -> float | None:
    aggregate = stats.get(name)
    return aggregate.maximum if aggregate else None


def _text(stats: dict[str, FoodAggregate], name: str) -> str:
    aggregate = stats.get(name)
    return aggregate.text if aggregate else ""
