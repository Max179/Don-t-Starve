from __future__ import annotations

import json
import sqlite3
from typing import Any


def rebuild_entity_prefab_profiles(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_prefab_profiles")
    rows = conn.execute(
        """
        select
            eik.entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            eik.source_id,
            s.key as source_key,
            eik.raw_page_id,
            eik.key_value,
            eik.source_field,
            eik.confidence
        from entity_identity_keys eik
        join entities e on e.id = eik.entity_id
        join sources s on s.id = eik.source_id
        where eik.key_type = 'spawn_code'
        order by e.slug, eik.key_value, eik.source_field, eik.id
        """
    ).fetchall()
    buckets: dict[int, dict[str, Any]] = {}
    for row in rows:
        bucket = _bucket(buckets, row)
        code = _prefab_code(row)
        bucket["codes"].append(code)
        bucket["source_fields"].add(code["source_field"])
        for category in code["categories"]:
            bucket["categories"].add(category)
            bucket["category_counts"][category] = (
                int(bucket["category_counts"].get(category, 0)) + 1
            )

    count = 0
    for bucket in buckets.values():
        identity = bucket["identity"]
        codes = sorted(
            bucket["codes"],
            key=lambda item: (
                "standard" not in item["categories"],
                -float(item["confidence"]),
                item["code"],
            ),
        )
        categories = sorted(bucket["categories"])
        category_counts = bucket["category_counts"]
        primary = codes[0]["code"] if codes else ""
        conn.execute(
            """
            insert into entity_prefab_profiles (
                entity_id, slug, canonical_title, kind, prefab_count,
                primary_prefab, prefab_codes_json, source_fields_text,
                category_count, code_categories_text, upgraded_prefab_count,
                reskin_prefab_count, mast_upgrade_prefab_count,
                chest_upgrade_prefab_count, merm_upgrade_prefab_count,
                has_prefabs, has_upgraded_prefab, has_reskin_prefab,
                has_mast_upgrade_prefab, has_chest_upgrade_prefab,
                has_merm_upgrade_prefab, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, current_timestamp)
            """,
            (
                int(identity["entity_id"]),
                str(identity["slug"]),
                str(identity["canonical_title"]),
                str(identity["kind"]),
                len(codes),
                primary,
                json.dumps(codes, ensure_ascii=False, sort_keys=True),
                " | ".join(sorted(bucket["source_fields"])),
                len(categories),
                " | ".join(categories),
                int(category_counts.get("upgraded", 0)),
                int(category_counts.get("reskin", 0)),
                int(category_counts.get("mast_upgrade", 0)),
                int(category_counts.get("chest_upgrade", 0)),
                int(category_counts.get("merm_upgrade", 0)),
                int(bool(codes)),
                int(bool(category_counts.get("upgraded", 0))),
                int(bool(category_counts.get("reskin", 0))),
                int(bool(category_counts.get("mast_upgrade", 0))),
                int(bool(category_counts.get("chest_upgrade", 0))),
                int(bool(category_counts.get("merm_upgrade", 0))),
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
            "codes": [],
            "source_fields": set(),
            "categories": set(),
            "category_counts": {},
        },
    )


def _prefab_code(row: sqlite3.Row) -> dict[str, Any]:
    code = str(row["key_value"])
    categories = _categories_for_code(code)
    return {
        "code": code,
        "categories": categories,
        "source_id": int(row["source_id"]),
        "source_key": str(row["source_key"]),
        "raw_page_id": row["raw_page_id"],
        "source_field": str(row["source_field"]),
        "confidence": float(row["confidence"]),
    }


def _categories_for_code(code: str) -> list[str]:
    value = code.lower()
    categories = []
    if "upgrad" in value:
        categories.append("upgraded")
    if "reskin" in value:
        categories.append("reskin")
    if "mastupgrade" in value:
        categories.append("mast_upgrade")
    if "chestupgrade" in value:
        categories.append("chest_upgrade")
    if "merm" in value and ("upgrad" in value or "upgraded" in value):
        categories.append("merm_upgrade")
    if not categories:
        categories.append("standard")
    return categories
