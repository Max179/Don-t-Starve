from __future__ import annotations

import re
import sqlite3
from typing import Dict, List

from dst_wiki_db.build import extract_number
from dst_wiki_db.schema import slugify


RELATION_FACT_FIELDS = {
    "drops",
    "dropped_by",
    "sold_by",
    "spawn_from",
    "spawns",
}

LINK_RE = re.compile(r"link=([^|,\)\n]+)")
PROBABILITY_RE = re.compile(r"\d+(?:\.\d+)?%")
QUANTITY_RE = re.compile(r"[×x]\s*\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?")


def extract_link_facts(value: str) -> List[Dict[str, str | None]]:
    matches = list(LINK_RE.finditer(value or ""))
    if not matches:
        return [
            {
                "target_title": None,
                "probability_text": _first_match(PROBABILITY_RE, value),
                "quantity_text": _first_match(QUANTITY_RE, value),
            }
        ]

    facts: List[Dict[str, str | None]] = []
    for index, match in enumerate(matches):
        segment_end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
        segment = value[match.start() : segment_end]
        facts.append(
            {
                "target_title": _clean_target(match.group(1)),
                "probability_text": _first_match(PROBABILITY_RE, segment),
                "quantity_text": _first_match(QUANTITY_RE, segment),
            }
        )
    return facts


def rebuild_entity_facts(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_facts")
    rows = conn.execute(
        """
        select
            entity_id, source_id, raw_page_id, template_index,
            raw_name, canonical_name, value_text, variant_key
        from entity_attributes
        where canonical_name in ('drops', 'dropped_by', 'sold_by', 'spawn_from', 'spawns')
        order by entity_id, raw_page_id, template_index, raw_name
        """
    ).fetchall()

    count = 0
    for row in rows:
        for fact_index, fact in enumerate(extract_link_facts(str(row["value_text"]))):
            target_title = fact["target_title"]
            quantity_text = fact["quantity_text"]
            conn.execute(
                """
                insert into entity_facts (
                    entity_id, source_id, raw_page_id, template_index, fact_index,
                    fact_type, raw_name, value_text, target_title, target_slug,
                    probability_text, quantity_text, quantity_number, variant_key
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["entity_id"]),
                    int(row["source_id"]),
                    int(row["raw_page_id"]),
                    int(row["template_index"]),
                    fact_index,
                    str(row["canonical_name"]),
                    str(row["raw_name"]),
                    str(row["value_text"]),
                    target_title,
                    slugify(target_title or ""),
                    fact["probability_text"],
                    quantity_text,
                    extract_number(quantity_text or ""),
                    str(row["variant_key"] or ""),
                ),
            )
            count += 1
    conn.commit()
    return count


def _first_match(pattern: re.Pattern, value: str) -> str | None:
    match = pattern.search(value or "")
    return match.group(0) if match else None


def _clean_target(value: str) -> str:
    target = value.strip().replace("_", " ")
    target = target.split("#", 1)[0].strip()
    target = re.split(r"\s+for\s+\d+px\b", target, maxsplit=1)[0]
    target = re.split(r"\s+or\s+\d+px\b", target, maxsplit=1)[0]
    target = re.split(r"\b\d+px\b", target, maxsplit=1)[0]
    target = target.split("(", 1)[0]
    target = target.split('"', 1)[0]
    target = PROBABILITY_RE.sub("", target)
    target = QUANTITY_RE.sub("", target)
    return re.sub(r"\s+", " ", target).strip()
