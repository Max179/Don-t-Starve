from __future__ import annotations

import re
import sqlite3
from typing import Dict, Mapping, Tuple

from dst_wiki_db.build import extract_number
from dst_wiki_db.schema import slugify


INGREDIENT_RE = re.compile(r"^ingredient(\d+)(?:_(\d+))?$", re.IGNORECASE)
MULTIPLIER_RE = re.compile(r"^multiplier(\d+)(?:_(\d+))?$", re.IGNORECASE)


def rebuild_recipe_ingredients(conn: sqlite3.Connection) -> int:
    conn.execute("delete from recipe_ingredients")
    rows = conn.execute(
        """
        select
            id, entity_id, source_id, raw_page_id, template_index,
            raw_name, value_text, value_number, variant_key
        from entity_attributes
        where lower(raw_name) glob 'ingredient[0-9]*'
           or lower(raw_name) glob 'multiplier[0-9]*'
        order by entity_id, raw_page_id, template_index, raw_name
        """
    ).fetchall()

    ingredients: Dict[Tuple[int, int, int, int, int, str], Mapping[str, object]] = {}
    multipliers: Dict[Tuple[int, int, int, int, int, str], Mapping[str, object]] = {}
    for row in rows:
        raw_name = str(row["raw_name"])
        ingredient_match = INGREDIENT_RE.match(raw_name)
        multiplier_match = MULTIPLIER_RE.match(raw_name)
        if ingredient_match:
            key = _recipe_key(row, ingredient_match)
            ingredients[key] = row
        elif multiplier_match:
            key = _recipe_key(row, multiplier_match)
            multipliers[key] = row

    count = 0
    for key, ingredient in ingredients.items():
        multiplier = multipliers.get(key)
        quantity_text = multiplier["value_text"] if multiplier is not None else None
        quantity_number = (
            multiplier["value_number"]
            if multiplier is not None and multiplier["value_number"] is not None
            else extract_number(str(quantity_text or ""))
        )
        conn.execute(
            """
            insert into recipe_ingredients (
                entity_id, source_id, raw_page_id, template_index, ingredient_slot,
                ingredient_name, ingredient_slug, quantity_text, quantity_number, variant_key
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(ingredient["entity_id"]),
                int(ingredient["source_id"]),
                int(ingredient["raw_page_id"]),
                int(ingredient["template_index"]),
                key[4],
                str(ingredient["value_text"]),
                slugify(str(ingredient["value_text"])),
                quantity_text,
                quantity_number,
                key[5],
            ),
        )
        count += 1
    conn.commit()
    return count


def _recipe_key(row, match) -> Tuple[int, int, int, int, int, str]:
    slot = int(match.group(1))
    suffix = match.group(2) or str(row["variant_key"] or "")
    return (
        int(row["entity_id"]),
        int(row["source_id"]),
        int(row["raw_page_id"]),
        int(row["template_index"]),
        slot,
        suffix,
    )
