from __future__ import annotations

import sqlite3


def rebuild_entity_targets(conn: sqlite3.Connection) -> dict[str, int]:
    relation_count = resolve_entity_relation_targets(conn)
    fact_count = rebuild_entity_fact_targets(conn)
    recipe_count = rebuild_recipe_ingredient_targets(conn)
    conn.commit()
    return {
        "entity_relation_targets": relation_count,
        "entity_fact_targets": fact_count,
        "recipe_ingredient_targets": recipe_count,
    }


def resolve_entity_relation_targets(conn: sqlite3.Connection) -> int:
    conn.execute("update entity_relations set target_entity_id = null")
    cursor = conn.execute(
        """
        update entity_relations
        set target_entity_id = (
            select e.id
            from entities e
            where e.slug = entity_relations.target_slug
        )
        where target_slug in (select slug from entities)
        """
    )
    return int(cursor.rowcount or 0)


def rebuild_entity_fact_targets(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_fact_targets")
    rows = conn.execute(
        """
        select
            f.id as entity_fact_id,
            f.entity_id,
            f.source_id,
            f.target_title,
            f.target_slug,
            e.id as target_entity_id
        from entity_facts f
        join entities e on e.slug = f.target_slug
        where f.target_slug != ''
        order by f.id
        """
    ).fetchall()
    count = 0
    for row in rows:
        cursor = conn.execute(
            """
            insert or ignore into entity_fact_targets (
                entity_fact_id, entity_id, source_id, target_entity_id,
                target_title, target_slug, match_method, confidence
            )
            values (?, ?, ?, ?, ?, ?, 'target_slug', 0.9)
            """,
            (
                int(row["entity_fact_id"]),
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["target_entity_id"]),
                str(row["target_title"] or ""),
                str(row["target_slug"]),
            ),
        )
        count += 1 if cursor.rowcount == 1 else 0
    return count


def rebuild_recipe_ingredient_targets(conn: sqlite3.Connection) -> int:
    conn.execute("delete from recipe_ingredient_targets")
    rows = conn.execute(
        """
        select
            ri.id as recipe_ingredient_id,
            ri.entity_id,
            ri.source_id,
            ri.ingredient_name,
            ri.ingredient_slug,
            e.id as ingredient_entity_id
        from recipe_ingredients ri
        join entities e on e.slug = ri.ingredient_slug
        where ri.ingredient_slug != ''
        order by ri.id
        """
    ).fetchall()
    count = 0
    for row in rows:
        cursor = conn.execute(
            """
            insert or ignore into recipe_ingredient_targets (
                recipe_ingredient_id, entity_id, source_id, ingredient_entity_id,
                ingredient_name, ingredient_slug, match_method, confidence
            )
            values (?, ?, ?, ?, ?, ?, 'ingredient_slug', 0.9)
            """,
            (
                int(row["recipe_ingredient_id"]),
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["ingredient_entity_id"]),
                str(row["ingredient_name"]),
                str(row["ingredient_slug"]),
            ),
        )
        count += 1 if cursor.rowcount == 1 else 0
    return count
