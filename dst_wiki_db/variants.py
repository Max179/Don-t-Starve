from __future__ import annotations

import re
import sqlite3


GROWTH_KEYS = {"seed", "sprout", "small", "med", "medium", "large", "bolting", "picked"}


def variant_type(key: str) -> str:
    if key in {"ds", "dst"}:
        return "game_scope"
    if key in GROWTH_KEYS:
        return "growth_stage"
    if key.isdigit():
        return "numbered_variant"
    if key.startswith("template:"):
        return "infobox_instance"
    return "variant"


def variant_label(key: str) -> str:
    labels = {
        "ds": "Don't Starve",
        "dst": "Don't Starve Together",
        "med": "Medium",
    }
    if key in labels:
        return labels[key]
    if key in GROWTH_KEYS:
        return key.replace("_", " ").title()
    if key.isdigit():
        return f"Variant {key}"
    if key.startswith("template:"):
        return f"Infobox #{key.split(':', 1)[1]}"
    return key.replace("_", " ").title()


def rebuild_entity_variants(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_variants")
    seen = set()
    for row in _variant_attribute_rows(conn):
        key = str(row["variant_key"])
        if key.isdigit() and not _is_numeric_variant_field(str(row["raw_name"])):
            continue
        _insert_variant(
            conn,
            seen,
            entity_id=int(row["entity_id"]),
            source_id=int(row["source_id"]),
            raw_page_id=int(row["raw_page_id"]),
            template_index=int(row["template_index"]),
            key=key,
            label=variant_label(key),
            source_field=str(row["raw_name"]),
        )
    for row in _variant_image_rows(conn):
        _insert_variant(
            conn,
            seen,
            entity_id=int(row["entity_id"]),
            source_id=int(row["source_id"]),
            raw_page_id=int(row["raw_page_id"]),
            template_index=0,
            key=str(row["variant_key"]),
            label=variant_label(str(row["variant_key"])),
            source_field=str(row["role"]),
        )
    for row in _repeated_infobox_rows(conn):
        key = f"template:{int(row['template_index'])}"
        _insert_variant(
            conn,
            seen,
            entity_id=int(row["entity_id"]),
            source_id=int(row["source_id"]),
            raw_page_id=int(row["raw_page_id"]),
            template_index=int(row["template_index"]),
            key=key,
            label=f"{row['template_name']} #{int(row['template_index'])}",
            source_field=str(row["template_name"]),
        )
    conn.commit()
    return len(seen)


def _variant_attribute_rows(conn):
    return conn.execute(
        """
        select distinct entity_id, source_id, raw_page_id, template_index, variant_key, raw_name
        from entity_attributes
        where variant_key is not null and variant_key != ''
        """
    ).fetchall()


def _variant_image_rows(conn):
    return conn.execute(
        """
        select distinct entity_id, source_id, raw_page_id, variant_key, role
        from entity_images
        where variant_key is not null and variant_key != ''
        """
    ).fetchall()


def _repeated_infobox_rows(conn):
    return conn.execute(
        """
        with template_counts as (
            select
                a.entity_id,
                a.source_id,
                a.raw_page_id,
                a.template_name,
                count(distinct a.template_index) as template_count
            from entity_attributes a
            join entities e on e.id = a.entity_id
            where a.template_name is not null and e.kind != 'page'
            group by a.entity_id, a.source_id, a.raw_page_id, a.template_name
        )
        select distinct
            a.entity_id,
            a.source_id,
            a.raw_page_id,
            a.template_index,
            a.template_name
        from entity_attributes a
        join template_counts tc
          on tc.entity_id = a.entity_id
         and tc.source_id = a.source_id
         and tc.raw_page_id = a.raw_page_id
         and tc.template_name = a.template_name
        where tc.template_count > 1 and a.template_index > 0
        """
    ).fetchall()


def _insert_variant(
    conn,
    seen: set,
    *,
    entity_id: int,
    source_id: int,
    raw_page_id: int,
    template_index: int,
    key: str,
    label: str,
    source_field: str,
) -> None:
    vtype = variant_type(key)
    dedupe_key = (entity_id, source_id, raw_page_id, template_index, key, vtype)
    if dedupe_key in seen:
        return
    seen.add(dedupe_key)
    conn.execute(
        """
        insert into entity_variants (
            entity_id, source_id, raw_page_id, template_index,
            variant_key, variant_type, label, source_field
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (entity_id, source_id, raw_page_id, template_index, key, vtype, label, source_field),
    )


def _is_numeric_variant_field(raw_name: str) -> bool:
    compact = re.sub(r"[^a-z0-9]", "", raw_name.lower())
    return compact.startswith(
        (
            "image",
            "inventoryimage",
            "spawncode",
            "health",
            "hunger",
            "sanity",
            "spoil",
            "stacklimit",
        )
    )
