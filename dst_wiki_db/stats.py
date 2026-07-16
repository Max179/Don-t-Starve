from __future__ import annotations

import re
import sqlite3


STAT_UNITS = {
    "attack_period": "seconds",
    "attack_range": "tiles",
    "burn_time": "seconds",
    "cooktime": "seconds",
    "damage": "points",
    "durability": "uses",
    "food_value": "points",
    "health": "points",
    "hp_restored": "points",
    "hunger": "points",
    "hunger_restored": "points",
    "priority": "level",
    "protection": "percent",
    "renew": "points",
    "resources": "items",
    "run_speed": "units_per_second",
    "sanity": "points",
    "sanityaura": "sanity_per_minute",
    "sanitydrain": "sanity_per_minute",
    "sanity_restored": "points",
    "spoil": "days",
    "stack": "items",
    "stacklimit": "items",
    "tier": "level",
    "walk_speed": "units_per_second",
    "water_resistance": "percent",
}

COMBAT_STATS = {"attack_period", "attack_range", "damage", "health"}
MOVEMENT_STATS = {"run_speed", "walk_speed"}
FOOD_STATS = {
    "food_value",
    "health",
    "hp_restored",
    "hunger",
    "hunger_restored",
    "sanity",
    "sanity_restored",
    "spoil",
}
ITEM_STATS = {
    "burn_time",
    "durability",
    "priority",
    "protection",
    "renew",
    "resources",
    "stack",
    "stacklimit",
    "tier",
    "water_resistance",
}
SURVIVAL_STATS = {"sanityaura", "sanitydrain"}
FOOD_VALUE_RE = re.compile(r"[×x]\s*([-+]?\d+(?:\.\d+)?)")


def rebuild_entity_stats(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_stats")
    rows = conn.execute(
        """
        select
            a.id as attribute_id,
            a.entity_id,
            a.source_id,
            a.raw_page_id,
            a.template_index,
            a.template_name,
            a.raw_name,
            a.canonical_name,
            a.value_text,
            a.value_number,
            coalesce(a.variant_key, '') as variant_key,
            e.kind as entity_kind
        from entity_attributes a
        join entities e on e.id = a.entity_id
        order by a.entity_id, a.raw_page_id, a.template_index, a.id
        """
    ).fetchall()

    count = 0
    for row in rows:
        stat_name = _base_stat_name(str(row["canonical_name"]))
        if stat_name not in STAT_UNITS:
            continue
        conn.execute(
            """
            insert into entity_stats (
                entity_id, source_id, raw_page_id, attribute_id, template_index,
                stat_name, stat_type, raw_name, value_text, value_number, unit,
                variant_key
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["raw_page_id"]),
                int(row["attribute_id"]),
                int(row["template_index"]),
                stat_name,
                _stat_type(
                    stat_name=stat_name,
                    entity_kind=str(row["entity_kind"]),
                    template_name=str(row["template_name"] or ""),
                ),
                str(row["raw_name"]),
                str(row["value_text"]),
                _value_number(
                    stat_name=stat_name,
                    value_text=str(row["value_text"]),
                    stored_value=row["value_number"],
                ),
                STAT_UNITS[stat_name],
                str(row["variant_key"] or ""),
            ),
        )
        count += 1
    conn.commit()
    return count


def _base_stat_name(canonical_name: str) -> str:
    if canonical_name in STAT_UNITS:
        return canonical_name
    without_suffix = re.sub(r"\d+$", "", canonical_name)
    if without_suffix in STAT_UNITS:
        return without_suffix
    return canonical_name


def _stat_type(*, stat_name: str, entity_kind: str, template_name: str) -> str:
    template_lower = template_name.lower()
    if stat_name in FOOD_STATS and (entity_kind == "food" or "food" in template_lower):
        return "food"
    if stat_name in COMBAT_STATS:
        return "combat"
    if stat_name in MOVEMENT_STATS:
        return "movement"
    if stat_name in ITEM_STATS:
        return "item"
    if stat_name in SURVIVAL_STATS:
        return "survival"
    if stat_name in FOOD_STATS:
        return "survival"
    return "stat"


def _value_number(*, stat_name: str, value_text: str, stored_value) -> float | int | None:
    if stat_name == "food_value":
        match = FOOD_VALUE_RE.search(value_text)
        if match:
            number = float(match.group(1))
            if number.is_integer():
                return int(number)
            return number
    return stored_value
