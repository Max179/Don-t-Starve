from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Any

from dst_wiki_db.identity import extract_spawn_codes


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


def rebuild_entity_creature_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_creature_profiles")
    grouped: dict[int, dict[str, Any]] = {}

    for row in _attribute_rows(conn):
        bucket = _bucket(grouped, row)
        bucket["attribute_count"] = int(bucket["attribute_count"]) + 1
        bucket["source_ids"].add(int(row["source_id"]))
        variant_key = str(row["variant_key"] or "").strip()
        if variant_key:
            bucket["variant_keys"].add(variant_key)
        field = _text_field(str(row["canonical_name"]))
        texts = bucket["texts"]
        if field == "spawn_code":
            codes = extract_spawn_codes(str(row["value_text"]))
            if codes:
                for code in codes:
                    texts.setdefault(field, TextAggregate()).add(code)
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

    for row in _edge_rows(conn):
        bucket = _bucket(grouped, row)
        edge_type = str(row["edge_type"])
        bucket["edge_counts"][edge_type] = int(row["edge_count"])
        bucket["edge_related_titles"][edge_type] = str(row["related_titles"] or "")

    count = 0
    for bucket in grouped.values():
        if not bucket["texts"] and not bucket["stats"] and not bucket["edge_counts"]:
            continue
        identity = bucket["identity"]
        texts = bucket["texts"]
        stats = bucket["stats"]
        edge_counts = bucket["edge_counts"]
        edge_titles = bucket["edge_related_titles"]
        values = {
            "entity_id": int(identity["entity_id"]),
            "slug": str(identity["slug"]),
            "canonical_title": str(identity["canonical_title"]),
            "kind": str(identity["kind"]),
            "biome_text": _text(texts, "biome"),
            "spawn_code_text": _text(texts, "spawn_code"),
            "special_ability_text": _text(texts, "special_ability"),
            "perk_text": _text(texts, "perk"),
            "drops_text": _text(texts, "drops"),
            "dropped_by_text": _text(texts, "dropped_by"),
            "spawn_from_text": _text(texts, "spawn_from"),
            "spawns_text": _text(texts, "spawns"),
            "health_min": _minimum(stats, "health"),
            "health_max": _maximum(stats, "health"),
            "health_text": _stat_text(stats, "health"),
            "damage_min": _minimum(stats, "damage"),
            "damage_max": _maximum(stats, "damage"),
            "damage_text": _stat_text(stats, "damage"),
            "attack_range_min": _minimum(stats, "attack_range"),
            "attack_range_max": _maximum(stats, "attack_range"),
            "attack_range_text": _stat_text(stats, "attack_range"),
            "attack_period_min": _minimum(stats, "attack_period"),
            "attack_period_max": _maximum(stats, "attack_period"),
            "attack_period_text": _stat_text(stats, "attack_period"),
            "walk_speed_min": _minimum(stats, "walk_speed"),
            "walk_speed_max": _maximum(stats, "walk_speed"),
            "walk_speed_text": _stat_text(stats, "walk_speed"),
            "run_speed_min": _minimum(stats, "run_speed"),
            "run_speed_max": _maximum(stats, "run_speed"),
            "run_speed_text": _stat_text(stats, "run_speed"),
            "sanityaura_min": _minimum(stats, "sanityaura"),
            "sanityaura_max": _maximum(stats, "sanityaura"),
            "sanityaura_text": _stat_text(stats, "sanityaura"),
            "sanitydrain_min": _minimum(stats, "sanitydrain"),
            "sanitydrain_max": _maximum(stats, "sanitydrain"),
            "sanitydrain_text": _stat_text(stats, "sanitydrain"),
            "drop_edge_count": int(edge_counts.get("drops", 0)),
            "dropped_by_edge_count": int(edge_counts.get("dropped_by", 0)),
            "spawns_edge_count": int(edge_counts.get("spawns", 0)),
            "spawned_from_edge_count": int(edge_counts.get("spawned_from", 0)),
            "drop_related_titles": str(edge_titles.get("drops", "")),
            "spawn_related_titles": " | ".join(
                part
                for part in (
                    str(edge_titles.get("spawns", "")),
                    str(edge_titles.get("spawned_from", "")),
                )
                if part
            ),
            "attribute_count": int(bucket["attribute_count"]),
            "stat_count": int(bucket["stat_count"]),
            "source_count": len(bucket["source_ids"])
            + int(bucket["rollup_source_count"]),
            "variant_count": len(bucket["variant_keys"])
            + int(bucket["rollup_variant_count"]),
            "is_boss": int(str(identity["kind"]) == "boss"),
            "has_combat_stats": int(
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
            "has_movement_stats": int(
                any(name in stats for name in ("walk_speed", "run_speed"))
            ),
            "has_sanity_effects": int(
                any(name in stats for name in ("sanityaura", "sanitydrain"))
            ),
            "has_drop_data": int(
                bool(_text(texts, "drops") or edge_counts.get("drops"))
            ),
            "has_spawn_data": int(
                bool(
                    _text(texts, "spawn_from")
                    or _text(texts, "spawns")
                    or edge_counts.get("spawns")
                    or edge_counts.get("spawned_from")
                )
            ),
        }
        conn.execute(
            """
            insert into entity_creature_profiles (
                entity_id, slug, canonical_title, kind,
                biome_text, spawn_code_text, special_ability_text, perk_text,
                drops_text, dropped_by_text, spawn_from_text, spawns_text,
                health_min, health_max, health_text,
                damage_min, damage_max, damage_text,
                attack_range_min, attack_range_max, attack_range_text,
                attack_period_min, attack_period_max, attack_period_text,
                walk_speed_min, walk_speed_max, walk_speed_text,
                run_speed_min, run_speed_max, run_speed_text,
                sanityaura_min, sanityaura_max, sanityaura_text,
                sanitydrain_min, sanitydrain_max, sanitydrain_text,
                drop_edge_count, dropped_by_edge_count, spawns_edge_count,
                spawned_from_edge_count, drop_related_titles,
                spawn_related_titles, attribute_count, stat_count, source_count,
                variant_count, is_boss, has_combat_stats, has_movement_stats,
                has_sanity_effects, has_drop_data, has_spawn_data, updated_at
            )
            values (
                :entity_id, :slug, :canonical_title, :kind,
                :biome_text, :spawn_code_text, :special_ability_text, :perk_text,
                :drops_text, :dropped_by_text, :spawn_from_text, :spawns_text,
                :health_min, :health_max, :health_text,
                :damage_min, :damage_max, :damage_text,
                :attack_range_min, :attack_range_max, :attack_range_text,
                :attack_period_min, :attack_period_max, :attack_period_text,
                :walk_speed_min, :walk_speed_max, :walk_speed_text,
                :run_speed_min, :run_speed_max, :run_speed_text,
                :sanityaura_min, :sanityaura_max, :sanityaura_text,
                :sanitydrain_min, :sanitydrain_max, :sanitydrain_text,
                :drop_edge_count, :dropped_by_edge_count, :spawns_edge_count,
                :spawned_from_edge_count, :drop_related_titles,
                :spawn_related_titles, :attribute_count, :stat_count,
                :source_count, :variant_count, :is_boss, :has_combat_stats,
                :has_movement_stats, :has_sanity_effects, :has_drop_data,
                :has_spawn_data, current_timestamp
            )
            """,
            values,
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
            "edge_counts": {},
            "edge_related_titles": {},
            "attribute_count": 0,
            "stat_count": 0,
            "source_ids": set(),
            "variant_keys": set(),
            "rollup_source_count": 0,
            "rollup_variant_count": 0,
        },
    )


def _text_field(canonical_name: str) -> str:
    if canonical_name in {"spawn_code", "spawn_code1", "spawn_code2"}:
        return "spawn_code"
    return canonical_name


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
        where e.kind in ('mob', 'boss')
          and a.canonical_name in (
            'biome', 'spawn_code', 'spawn_code1', 'spawn_code2',
            'special_ability', 'perk', 'drops', 'dropped_by',
            'spawn_from', 'spawns'
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
        where kind in ('mob', 'boss')
          and stat_name in (
            'health', 'damage', 'attack_range', 'attack_period',
            'walk_speed', 'run_speed', 'sanityaura', 'sanitydrain'
          )
        order by slug, stat_name, id
        """
    ).fetchall()


def _edge_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            entity_id,
            entity_slug as slug,
            entity_title as canonical_title,
            entity_kind as kind,
            edge_type,
            count(*) as edge_count,
            group_concat(related_title, ' | ') as related_titles
        from entity_gameplay_edges
        where entity_kind in ('mob', 'boss')
          and edge_type in ('drops', 'dropped_by', 'spawns', 'spawned_from')
        group by entity_id, edge_type
        order by entity_slug, edge_type
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
