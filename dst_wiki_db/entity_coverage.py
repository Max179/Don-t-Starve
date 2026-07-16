from __future__ import annotations

import sqlite3


COVERAGE_DIMENSIONS = (
    ("source", "has_source"),
    ("attributes", "has_attributes"),
    ("stats", "has_stats"),
    ("images", "has_images"),
    ("variants", "has_variants"),
    ("categories", "has_categories"),
    ("relations", "has_relations"),
    ("facts", "has_facts"),
    ("recipes", "has_recipes"),
    ("official_mentions", "has_official_mentions"),
)


def rebuild_entity_coverage(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_coverage")
    rows = conn.execute(
        """
        select id as entity_id, slug, canonical_title, kind
        from entities
        order by id
        """
    ).fetchall()
    aggregates = _aggregates(conn)
    count = 0
    for row in rows:
        entity_id = int(row["entity_id"])
        counts = {
            "source_count": aggregates["source_count"].get(entity_id, 0),
            "raw_page_count": aggregates["raw_page_count"].get(entity_id, 0),
            "attribute_count": aggregates["attribute_count"].get(entity_id, 0),
            "stat_count": aggregates["stat_count"].get(entity_id, 0),
            "stat_value_count": aggregates["stat_value_count"].get(entity_id, 0),
            "infobox_image_count": aggregates["infobox_image_count"].get(entity_id, 0),
            "page_image_count": aggregates["page_image_count"].get(entity_id, 0),
            "variant_count": aggregates["variant_count"].get(entity_id, 0),
            "category_count": aggregates["category_count"].get(entity_id, 0),
            "relation_count": aggregates["relation_count"].get(entity_id, 0),
            "resolved_relation_count": aggregates["resolved_relation_count"].get(entity_id, 0),
            "fact_count": aggregates["fact_count"].get(entity_id, 0),
            "resolved_fact_count": aggregates["resolved_fact_count"].get(entity_id, 0),
            "recipe_ingredient_count": aggregates["recipe_ingredient_count"].get(entity_id, 0),
            "resolved_recipe_ingredient_count": aggregates[
                "resolved_recipe_ingredient_count"
            ].get(entity_id, 0),
            "official_mention_count": aggregates["official_mention_count"].get(entity_id, 0),
        }
        flags = _flags(counts)
        missing = [
            name
            for name, flag_name in COVERAGE_DIMENSIONS
            if flags[flag_name] == 0
        ]
        score = sum(flags.values()) * 10
        conn.execute(
            """
            insert into entity_coverage (
                entity_id, slug, canonical_title, kind, source_count,
                raw_page_count, attribute_count, stat_count, stat_value_count,
                infobox_image_count, page_image_count, variant_count,
                category_count, relation_count, resolved_relation_count,
                fact_count, resolved_fact_count, recipe_ingredient_count,
                resolved_recipe_ingredient_count, official_mention_count,
                has_source, has_attributes, has_stats, has_images,
                has_variants, has_categories, has_relations, has_facts,
                has_recipes, has_official_mentions, coverage_score,
                missing_summary
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                str(row["slug"]),
                str(row["canonical_title"]),
                str(row["kind"]),
                counts["source_count"],
                counts["raw_page_count"],
                counts["attribute_count"],
                counts["stat_count"],
                counts["stat_value_count"],
                counts["infobox_image_count"],
                counts["page_image_count"],
                counts["variant_count"],
                counts["category_count"],
                counts["relation_count"],
                counts["resolved_relation_count"],
                counts["fact_count"],
                counts["resolved_fact_count"],
                counts["recipe_ingredient_count"],
                counts["resolved_recipe_ingredient_count"],
                counts["official_mention_count"],
                flags["has_source"],
                flags["has_attributes"],
                flags["has_stats"],
                flags["has_images"],
                flags["has_variants"],
                flags["has_categories"],
                flags["has_relations"],
                flags["has_facts"],
                flags["has_recipes"],
                flags["has_official_mentions"],
                score,
                "|".join(missing),
            ),
        )
        count += 1
    conn.commit()
    return count


def _aggregates(conn: sqlite3.Connection) -> dict[str, dict[int, int]]:
    return {
        "source_count": _count_distinct(conn, "entity_sources", "source_id"),
        "raw_page_count": _count_distinct(conn, "entity_sources", "raw_page_id"),
        "attribute_count": _count_rows(conn, "entity_attributes"),
        "stat_count": _count_rows(conn, "entity_stats"),
        "stat_value_count": _count_rows(conn, "entity_stat_values"),
        "infobox_image_count": _count_rows(conn, "entity_images"),
        "page_image_count": _count_rows(conn, "page_images"),
        "variant_count": _count_rows(conn, "entity_variants"),
        "category_count": _count_rows(conn, "entity_categories"),
        "relation_count": _count_rows(conn, "entity_relations"),
        "resolved_relation_count": _count_rows(
            conn, "entity_relations", "target_entity_id is not null"
        ),
        "fact_count": _count_rows(conn, "entity_facts"),
        "resolved_fact_count": _count_rows(conn, "entity_fact_targets"),
        "recipe_ingredient_count": _count_rows(conn, "recipe_ingredients"),
        "resolved_recipe_ingredient_count": _count_rows(
            conn, "recipe_ingredient_targets"
        ),
        "official_mention_count": _count_rows(conn, "official_record_mentions"),
    }


def _count_rows(
    conn: sqlite3.Connection, table: str, where: str | None = None
) -> dict[int, int]:
    where_clause = f"where {where}" if where else ""
    rows = conn.execute(
        f"""
        select entity_id, count(*) as count
        from {table}
        {where_clause}
        group by entity_id
        """
    ).fetchall()
    return {int(row["entity_id"]): int(row["count"]) for row in rows}


def _count_distinct(conn: sqlite3.Connection, table: str, column: str) -> dict[int, int]:
    rows = conn.execute(
        f"""
        select entity_id, count(distinct {column}) as count
        from {table}
        group by entity_id
        """
    ).fetchall()
    return {int(row["entity_id"]): int(row["count"]) for row in rows}


def _flags(counts: dict[str, int]) -> dict[str, int]:
    return {
        "has_source": int(counts["source_count"] > 0 and counts["raw_page_count"] > 0),
        "has_attributes": int(counts["attribute_count"] > 0),
        "has_stats": int(counts["stat_count"] > 0),
        "has_images": int(
            counts["infobox_image_count"] > 0 or counts["page_image_count"] > 0
        ),
        "has_variants": int(counts["variant_count"] > 0),
        "has_categories": int(counts["category_count"] > 0),
        "has_relations": int(counts["resolved_relation_count"] > 0),
        "has_facts": int(counts["resolved_fact_count"] > 0),
        "has_recipes": int(counts["resolved_recipe_ingredient_count"] > 0),
        "has_official_mentions": int(counts["official_mention_count"] > 0),
    }
