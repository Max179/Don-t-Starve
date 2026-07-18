from __future__ import annotations

import json
import sqlite3
from typing import Any


def rebuild_entity_recipe_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_recipe_profiles")
    grouped: dict[int, dict[str, Any]] = {}

    for row in _ingredient_rows(conn):
        bucket = _bucket(grouped, row)
        bucket["source_ids"].add(int(row["source_id"]))
        variant_key = str(row["variant_key"] or "")
        if variant_key:
            bucket["variant_keys"].add(variant_key)
        bucket["recipe_keys"].add(
            (
                int(row["raw_page_id"]),
                int(row["template_index"]),
            )
        )
        bucket["ingredients"].append(
            {
                "slot": int(row["ingredient_slot"]),
                "name": str(row["ingredient_name"]),
                "slug": str(row["ingredient_slug"]),
                "quantity_text": row["quantity_text"],
                "quantity_number": _optional_float(row["quantity_number"]),
                "variant_key": variant_key,
            }
        )

    for row in _target_rows(conn):
        bucket = _bucket(grouped, row)
        bucket["targets"].append(
            {
                "slot": int(row["ingredient_slot"]),
                "ingredient_entity_id": int(row["ingredient_entity_id"]),
                "title": str(row["ingredient_title"]),
                "slug": str(row["ingredient_slug"]),
                "kind": str(row["ingredient_kind"]),
                "quantity_text": row["quantity_text"],
                "quantity_number": _optional_float(row["quantity_number"]),
                "variant_key": str(row["variant_key"] or ""),
                "match_method": str(row["match_method"]),
                "confidence": _optional_float(row["confidence"]),
            }
        )

    for row in _used_in_rows(conn):
        bucket = _bucket(grouped, row)
        bucket["used_in"].append(
            {
                "entity_id": int(row["related_entity_id"]),
                "title": str(row["related_title"]),
                "slug": str(row["related_slug"]),
                "kind": str(row["related_kind"]),
                "quantity_text": row["quantity_text"],
                "quantity_number": _optional_float(row["quantity_number"]),
                "variant_key": str(row["variant_key"] or ""),
                "confidence": _optional_float(row["confidence"]),
            }
        )

    count = 0
    for bucket in grouped.values():
        ingredients = sorted(
            bucket["ingredients"],
            key=lambda item: (
                str(item["variant_key"]),
                int(item["slot"]),
                str(item["name"]),
            ),
        )
        targets = sorted(
            bucket["targets"],
            key=lambda item: (
                str(item["variant_key"]),
                int(item["slot"]),
                str(item["title"]),
            ),
        )
        used_in = sorted(
            bucket["used_in"],
            key=lambda item: (str(item["title"]), str(item["variant_key"])),
        )
        if not ingredients and not used_in:
            continue
        identity = bucket["identity"]
        ingredient_names = _join_unique(item["name"] for item in ingredients)
        ingredient_titles = _join_unique(item["title"] for item in targets)
        used_in_titles = _join_unique(item["title"] for item in used_in)
        conn.execute(
            """
            insert into entity_recipe_profiles (
                entity_id, slug, canonical_title, kind,
                recipe_count, ingredient_count, resolved_ingredient_count,
                unresolved_ingredient_count, used_in_count, source_count,
                variant_count, ingredient_names_text, ingredient_targets_text,
                used_in_titles_text, ingredient_summary_json,
                used_in_summary_json, has_recipe, has_resolved_ingredients,
                is_ingredient, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["slug"]),
                str(identity["canonical_title"]),
                str(identity["kind"]),
                len(bucket["recipe_keys"]),
                len(ingredients),
                len(targets),
                max(0, len(ingredients) - len(targets)),
                len(used_in),
                len(bucket["source_ids"]),
                len(bucket["variant_keys"]),
                ingredient_names,
                ingredient_titles,
                used_in_titles,
                json.dumps(ingredients, ensure_ascii=False, sort_keys=True),
                json.dumps(used_in, ensure_ascii=False, sort_keys=True),
                int(bool(ingredients)),
                int(bool(targets)),
                int(bool(used_in)),
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
            "ingredients": [],
            "targets": [],
            "used_in": [],
            "source_ids": set(),
            "variant_keys": set(),
            "recipe_keys": set(),
        },
    )


def _ingredient_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            ri.source_id,
            ri.raw_page_id,
            ri.template_index,
            ri.ingredient_slot,
            ri.ingredient_name,
            ri.ingredient_slug,
            ri.quantity_text,
            ri.quantity_number,
            ri.variant_key
        from recipe_ingredients ri
        join entities e on e.id = ri.entity_id
        order by e.slug, ri.raw_page_id, ri.template_index, ri.variant_key,
                 ri.ingredient_slot
        """
    ).fetchall()


def _target_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            ri.ingredient_slot,
            ri.quantity_text,
            ri.quantity_number,
            ri.variant_key,
            target.id as ingredient_entity_id,
            target.canonical_title as ingredient_title,
            target.slug as ingredient_slug,
            target.kind as ingredient_kind,
            rit.match_method,
            rit.confidence
        from recipe_ingredient_targets rit
        join recipe_ingredients ri on ri.id = rit.recipe_ingredient_id
        join entities e on e.id = rit.entity_id
        join entities target on target.id = rit.ingredient_entity_id
        order by e.slug, ri.variant_key, ri.ingredient_slot, target.canonical_title
        """
    ).fetchall()


def _used_in_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            edge.related_entity_id,
            edge.related_title,
            edge.related_slug,
            edge.related_kind,
            edge.quantity_text,
            edge.quantity_number,
            edge.variant_key,
            edge.confidence
        from entity_gameplay_edges edge
        join entities e on e.id = edge.entity_id
        where edge.edge_type = 'ingredient_for'
          and edge.edge_group = 'recipe'
          and edge.direction = 'inverse'
        order by e.slug, edge.related_title
        """
    ).fetchall()


def _join_unique(values: Any) -> str:
    seen = []
    for value in values:
        text = " ".join(str(value or "").split())
        if text and text not in seen:
            seen.append(text)
    return " | ".join(seen)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
