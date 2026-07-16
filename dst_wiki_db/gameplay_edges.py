from __future__ import annotations

import sqlite3
from typing import Any


FACT_EDGE_TYPES = {
    "drops": ("drops", "dropped_by"),
    "dropped_by": ("dropped_by", "drops"),
    "spawn_from": ("spawned_from", "spawns"),
    "spawns": ("spawns", "spawned_from"),
    "sold_by": ("sold_by", "sells"),
}


def rebuild_entity_gameplay_edges(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_gameplay_edges")
    count = 0
    count += _insert_recipe_edges(conn)
    count += _insert_fact_edges(conn)
    conn.commit()
    return count


def _insert_recipe_edges(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select
            rit.recipe_ingredient_id as source_row_id,
            rit.entity_id,
            rit.source_id,
            rit.ingredient_entity_id as related_entity_id,
            rit.confidence,
            ri.quantity_text,
            ri.quantity_number,
            ri.variant_key,
            source.canonical_title as entity_title,
            source.slug as entity_slug,
            source.kind as entity_kind,
            target.canonical_title as related_title,
            target.slug as related_slug,
            target.kind as related_kind
        from recipe_ingredient_targets rit
        join recipe_ingredients ri on ri.id = rit.recipe_ingredient_id
        join entities source on source.id = rit.entity_id
        join entities target on target.id = rit.ingredient_entity_id
        order by rit.recipe_ingredient_id, rit.ingredient_entity_id
        """
    ).fetchall()
    count = 0
    for row in rows:
        count += _insert_edge(
            conn,
            row,
            edge_type="uses_ingredient",
            edge_group="recipe",
            direction="forward",
            source_table="recipe_ingredients",
        )
        count += _insert_edge(
            conn,
            _reverse_row(row),
            edge_type="ingredient_for",
            edge_group="recipe",
            direction="inverse",
            source_table="recipe_ingredients",
        )
    return count


def _insert_fact_edges(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select
            eft.entity_fact_id as source_row_id,
            eft.entity_id,
            eft.source_id,
            eft.target_entity_id as related_entity_id,
            eft.confidence,
            ef.fact_type,
            ef.quantity_text,
            ef.quantity_number,
            ef.probability_text,
            ef.variant_key,
            source.canonical_title as entity_title,
            source.slug as entity_slug,
            source.kind as entity_kind,
            target.canonical_title as related_title,
            target.slug as related_slug,
            target.kind as related_kind
        from entity_fact_targets eft
        join entity_facts ef on ef.id = eft.entity_fact_id
        join entities source on source.id = eft.entity_id
        join entities target on target.id = eft.target_entity_id
        order by eft.entity_fact_id, eft.target_entity_id
        """
    ).fetchall()
    count = 0
    for row in rows:
        edge_types = FACT_EDGE_TYPES.get(str(row["fact_type"]))
        if edge_types is None:
            continue
        forward_type, inverse_type = edge_types
        count += _insert_edge(
            conn,
            row,
            edge_type=forward_type,
            edge_group="fact",
            direction="forward",
            source_table="entity_facts",
        )
        count += _insert_edge(
            conn,
            _reverse_row(row),
            edge_type=inverse_type,
            edge_group="fact",
            direction="inverse",
            source_table="entity_facts",
        )
    return count


def _insert_edge(
    conn: sqlite3.Connection,
    row: sqlite3.Row | dict[str, Any],
    *,
    edge_type: str,
    edge_group: str,
    direction: str,
    source_table: str,
) -> int:
    cursor = conn.execute(
        """
        insert or ignore into entity_gameplay_edges (
            entity_id, related_entity_id, source_id, source_table,
            source_row_id, edge_type, edge_group, direction, entity_title,
            entity_slug, entity_kind, related_title, related_slug,
            related_kind, quantity_text, quantity_number, probability_text,
            variant_key, confidence
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(row["entity_id"]),
            int(row["related_entity_id"]),
            int(row["source_id"]),
            source_table,
            int(row["source_row_id"]),
            edge_type,
            edge_group,
            direction,
            str(row["entity_title"]),
            str(row["entity_slug"]),
            str(row["entity_kind"]),
            str(row["related_title"]),
            str(row["related_slug"]),
            str(row["related_kind"]),
            row["quantity_text"],
            row["quantity_number"],
            row["probability_text"] if "probability_text" in row.keys() else None,
            str(row["variant_key"] or ""),
            float(row["confidence"]),
        ),
    )
    return 1 if cursor.rowcount == 1 else 0


def _reverse_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "source_row_id": row["source_row_id"],
        "entity_id": row["related_entity_id"],
        "source_id": row["source_id"],
        "related_entity_id": row["entity_id"],
        "confidence": row["confidence"],
        "quantity_text": row["quantity_text"],
        "quantity_number": row["quantity_number"],
        "probability_text": row["probability_text"] if "probability_text" in row.keys() else None,
        "variant_key": row["variant_key"],
        "entity_title": row["related_title"],
        "entity_slug": row["related_slug"],
        "entity_kind": row["related_kind"],
        "related_title": row["entity_title"],
        "related_slug": row["entity_slug"],
        "related_kind": row["entity_kind"],
    }
