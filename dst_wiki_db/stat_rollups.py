from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Mapping


@dataclass
class Rollup:
    entity_id: int
    slug: str
    canonical_title: str
    kind: str
    stat_name: str
    stat_type: str
    unit: str
    values: list[float] = field(default_factory=list)
    value_texts: set[str] = field(default_factory=set)
    stat_ids: set[int] = field(default_factory=set)
    source_ids: set[int] = field(default_factory=set)
    variant_keys: set[str] = field(default_factory=set)

    def add(self, row: Mapping[str, object]) -> None:
        self.stat_ids.add(int(row["stat_id"]))
        self.source_ids.add(int(row["source_id"]))
        text = str(row["value_text"] or "").strip()
        if text:
            self.value_texts.add(text)
        variant_key = str(row["variant_key"] or "").strip()
        if variant_key:
            self.variant_keys.add(variant_key)
        value = row["parsed_value"]
        if value is not None:
            self.values.append(float(value))

    @property
    def value_min(self) -> float | None:
        return min(self.values) if self.values else None

    @property
    def value_max(self) -> float | None:
        return max(self.values) if self.values else None

    @property
    def value_text_summary(self) -> str:
        return " | ".join(sorted(self.value_texts))


def rebuild_entity_stat_rollups(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_stat_rollups")
    rollups = _rollups(conn)
    count = 0
    for rollup in rollups.values():
        conn.execute(
            """
            insert into entity_stat_rollups (
                entity_id, slug, canonical_title, kind, stat_name, stat_type,
                unit, value_min, value_max, value_count, evidence_count,
                source_count, variant_count, value_texts, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                rollup.entity_id,
                rollup.slug,
                rollup.canonical_title,
                rollup.kind,
                rollup.stat_name,
                rollup.stat_type,
                rollup.unit,
                rollup.value_min,
                rollup.value_max,
                len(rollup.values),
                len(rollup.stat_ids),
                len(rollup.source_ids),
                len(rollup.variant_keys),
                rollup.value_text_summary,
            ),
        )
        count += 1
    conn.commit()
    return count


def _rollups(conn: sqlite3.Connection) -> dict[tuple[int, str, str, str], Rollup]:
    rows = conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            s.id as stat_id,
            s.source_id,
            s.stat_name,
            s.stat_type,
            s.unit,
            s.value_text,
            s.value_number,
            s.variant_key,
            v.value_number as stat_value_number
        from entity_stats s
        join entities e on e.id = s.entity_id
        left join entity_stat_values v on v.entity_stat_id = s.id
        order by e.slug, s.stat_type, s.stat_name, s.unit, s.id, v.value_index
        """
    ).fetchall()
    rollups: dict[tuple[int, str, str, str], Rollup] = {}
    seen_values: set[tuple[int, float | None]] = set()
    for row in rows:
        key = (
            int(row["entity_id"]),
            str(row["stat_name"]),
            str(row["stat_type"]),
            str(row["unit"]),
        )
        rollup = rollups.get(key)
        if rollup is None:
            rollup = Rollup(
                entity_id=int(row["entity_id"]),
                slug=str(row["slug"]),
                canonical_title=str(row["canonical_title"]),
                kind=str(row["kind"]),
                stat_name=str(row["stat_name"]),
                stat_type=str(row["stat_type"]),
                unit=str(row["unit"]),
            )
            rollups[key] = rollup
        parsed_value = row["stat_value_number"]
        if parsed_value is None:
            parsed_value = row["value_number"]
        dedupe_key = (int(row["stat_id"]), parsed_value)
        if dedupe_key in seen_values:
            continue
        seen_values.add(dedupe_key)
        mutable = dict(row)
        mutable["parsed_value"] = parsed_value
        rollup.add(mutable)
    return dict(sorted(rollups.items()))
