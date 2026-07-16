from __future__ import annotations

import sqlite3
from typing import Dict, List


COUNT_TABLES = [
    "sources",
    "raw_pages",
    "entities",
    "entity_sources",
    "entity_attributes",
    "entity_images",
    "entity_relations",
    "verification_checks",
    "official_records",
    "recipe_ingredients",
    "entity_facts",
    "entity_variants",
    "entity_categories",
    "entity_identity_keys",
    "cross_source_matches",
]


def database_counts(conn: sqlite3.Connection) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for table in COUNT_TABLES:
        row = conn.execute(f"select count(*) as count from {table}").fetchone()
        counts[table] = int(row["count"] if hasattr(row, "keys") else row[0])
    return counts


def sample_entities(conn: sqlite3.Connection, *, limit: int = 10) -> List[dict]:
    rows = conn.execute(
        """
        select
            e.canonical_title,
            e.kind,
            count(distinct a.id) as attribute_count,
            count(distinct i.id) as image_count
        from entities e
        left join entity_attributes a on a.entity_id = e.id
        left join entity_images i on i.entity_id = e.id
        group by e.id
        order by e.canonical_title
        limit ?
        """,
        (limit,),
    ).fetchall()
    return [
        {
            "canonical_title": row["canonical_title"],
            "kind": row["kind"],
            "attribute_count": int(row["attribute_count"]),
            "image_count": int(row["image_count"]),
        }
        for row in rows
    ]
