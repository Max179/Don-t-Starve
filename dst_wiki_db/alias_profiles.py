from __future__ import annotations

import json
import re
import sqlite3
from pathlib import PurePosixPath
from typing import Any

from dst_wiki_db.schema import slugify


IMAGE_EXTENSION_RE = re.compile(r"\.(?:png|jpe?g|gif|webp|svg)$", re.IGNORECASE)


def rebuild_entity_alias_profiles(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("delete from entity_alias_profiles")
    conn.execute("delete from entity_aliases")
    alias_count = 0
    alias_count += _insert_canonical_aliases(conn)
    alias_count += _insert_source_title_aliases(conn)
    alias_count += _insert_identity_key_aliases(conn)
    profile_count = _insert_alias_profiles(conn)
    conn.commit()
    return {"entity_aliases": alias_count, "entity_alias_profiles": profile_count}


def _insert_canonical_aliases(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select
            e.id as entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            s.key as source_key
        from entities e
        left join sources s on s.id = e.primary_source_id
        order by e.id
        """
    ).fetchall()
    count = 0
    for row in rows:
        count += _insert_alias(
            conn,
            row,
            alias_type="canonical_title",
            alias_value=str(row["canonical_title"]),
            source_key=str(row["source_key"] or "canonical"),
            source_field="entities.canonical_title",
            confidence=1.0,
        )
        count += _insert_alias(
            conn,
            row,
            alias_type="canonical_slug",
            alias_value=str(row["slug"]),
            source_key=str(row["source_key"] or "canonical"),
            source_field="entities.slug",
            confidence=0.96,
        )
    return count


def _insert_source_title_aliases(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select
            es.entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            s.key as source_key,
            es.source_title
        from entity_sources es
        join entities e on e.id = es.entity_id
        join sources s on s.id = es.source_id
        where es.source_title is not null and es.source_title != ''
        order by es.entity_id, s.key, es.source_title
        """
    ).fetchall()
    count = 0
    for row in rows:
        count += _insert_alias(
            conn,
            row,
            alias_type="source_title",
            alias_value=str(row["source_title"]),
            source_key=str(row["source_key"]),
            source_field="entity_sources.source_title",
            confidence=0.94,
        )
    return count


def _insert_identity_key_aliases(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select
            eik.entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            s.key as source_key,
            eik.key_type,
            eik.key_value,
            eik.source_field,
            eik.confidence
        from entity_identity_keys eik
        join entities e on e.id = eik.entity_id
        join sources s on s.id = eik.source_id
        where eik.key_type in ('title_slug', 'spawn_code', 'image_name')
          and eik.key_value is not null
          and eik.key_value != ''
        order by eik.entity_id, eik.key_type, eik.key_value, eik.id
        """
    ).fetchall()
    count = 0
    for row in rows:
        key_type = str(row["key_type"])
        if key_type == "title_slug":
            count += _insert_alias(
                conn,
                row,
                alias_type="source_slug",
                alias_value=str(row["key_value"]),
                source_key=str(row["source_key"]),
                source_field=str(row["source_field"]),
                confidence=float(row["confidence"]),
            )
        elif key_type == "spawn_code":
            count += _insert_alias(
                conn,
                row,
                alias_type="prefab_code",
                alias_value=str(row["key_value"]),
                source_key=str(row["source_key"]),
                source_field=str(row["source_field"]),
                confidence=float(row["confidence"]),
            )
        elif key_type == "image_name":
            image_name = str(row["key_value"])
            count += _insert_alias(
                conn,
                row,
                alias_type="image_name",
                alias_value=image_name,
                source_key=str(row["source_key"]),
                source_field=str(row["source_field"]),
                confidence=float(row["confidence"]),
            )
            stem = _image_stem(image_name)
            if stem and stem != image_name:
                count += _insert_alias(
                    conn,
                    row,
                    alias_type="image_stem",
                    alias_value=stem,
                    source_key=str(row["source_key"]),
                    source_field=str(row["source_field"]),
                    confidence=max(0.5, float(row["confidence"]) - 0.05),
                )
    return count


def _insert_alias_profiles(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select
            ea.entity_id,
            e.slug,
            e.canonical_title,
            e.kind,
            ea.alias_type,
            ea.alias_value,
            ea.alias_key,
            ea.source_key,
            ea.source_field,
            ea.confidence
        from entity_aliases ea
        join entities e on e.id = ea.entity_id
        order by ea.entity_id, ea.confidence desc, ea.alias_type, ea.alias_value
        """
    ).fetchall()
    buckets: dict[int, dict[str, Any]] = {}
    for row in rows:
        entity_id = int(row["entity_id"])
        bucket = buckets.setdefault(
            entity_id,
            {
                "identity": row,
                "aliases": [],
                "search_keys": set(),
                "sources": set(),
                "type_counts": {},
            },
        )
        alias = {
            "type": str(row["alias_type"]),
            "value": str(row["alias_value"]),
            "key": str(row["alias_key"]),
            "source_key": str(row["source_key"] or ""),
            "source_field": str(row["source_field"] or ""),
            "confidence": float(row["confidence"]),
        }
        bucket["aliases"].append(alias)
        bucket["search_keys"].add(alias["key"])
        if alias["source_key"]:
            bucket["sources"].add(alias["source_key"])
        bucket["type_counts"][alias["type"]] = int(bucket["type_counts"].get(alias["type"], 0)) + 1

    count = 0
    for bucket in buckets.values():
        row = bucket["identity"]
        aliases = bucket["aliases"]
        type_counts = bucket["type_counts"]
        search_keys = sorted(bucket["search_keys"])
        title_alias_count = sum(
            int(type_counts.get(alias_type, 0))
            for alias_type in (
                "canonical_title",
                "canonical_slug",
                "source_title",
                "source_slug",
            )
        )
        image_alias_count = sum(
            int(type_counts.get(alias_type, 0))
            for alias_type in ("image_name", "image_stem")
        )
        source_keys = sorted(bucket["sources"])
        conn.execute(
            """
            insert into entity_alias_profiles (
                entity_id, slug, canonical_title, kind, alias_count,
                title_alias_count, source_title_count, identity_key_count,
                prefab_alias_count, image_alias_count, search_key_count,
                source_count, source_keys_text, primary_search_key,
                aliases_json, search_keys_json, has_source_titles,
                has_prefab_aliases, has_image_aliases, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    current_timestamp)
            """,
            (
                int(row["entity_id"]),
                str(row["slug"]),
                str(row["canonical_title"]),
                str(row["kind"]),
                len(aliases),
                title_alias_count,
                int(type_counts.get("source_title", 0)),
                len(aliases) - int(type_counts.get("canonical_title", 0)) - int(type_counts.get("canonical_slug", 0)),
                int(type_counts.get("prefab_code", 0)),
                image_alias_count,
                len(search_keys),
                len(source_keys),
                " | ".join(source_keys),
                _alias_key(str(row["canonical_title"])),
                json.dumps(_summary_aliases(aliases), ensure_ascii=False, sort_keys=True),
                json.dumps(search_keys[:40], ensure_ascii=False),
                int(bool(type_counts.get("source_title", 0))),
                int(bool(type_counts.get("prefab_code", 0))),
                int(bool(image_alias_count)),
            ),
        )
        count += 1
    return count


def _insert_alias(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    alias_type: str,
    alias_value: str,
    source_key: str,
    source_field: str,
    confidence: float,
) -> int:
    alias_value = _clean_alias(alias_value)
    alias_key = _alias_key(alias_value)
    if not alias_value or not alias_key:
        return 0
    cursor = conn.execute(
        """
        insert or ignore into entity_aliases (
            entity_id, alias_type, alias_value, alias_key, source_key,
            source_field, confidence
        )
        values (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            int(row["entity_id"]),
            alias_type,
            alias_value,
            alias_key,
            source_key,
            source_field,
            confidence,
        ),
    )
    return 1 if cursor.rowcount == 1 else 0


def _summary_aliases(aliases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    type_order = {
        "canonical_title": 0,
        "canonical_slug": 1,
        "source_title": 2,
        "source_slug": 3,
        "prefab_code": 4,
        "image_stem": 5,
        "image_name": 6,
    }
    ranked = sorted(
        aliases,
        key=lambda alias: (
            type_order.get(str(alias["type"]), 99),
            -float(alias["confidence"]),
            str(alias["key"]),
        ),
    )
    return [
        {
            "type": str(alias["type"]),
            "value": str(alias["value"]),
            "key": str(alias["key"]),
        }
        for alias in ranked[:8]
    ]


def _clean_alias(value: str) -> str:
    cleaned = value.strip().replace("_", " ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _alias_key(value: str) -> str:
    return slugify(_clean_alias(value))


def _image_stem(image_name: str) -> str:
    basename = PurePosixPath(image_name.replace("\\", "/")).name
    basename = re.sub(r"^file:", "", basename, flags=re.IGNORECASE)
    stem = IMAGE_EXTENSION_RE.sub("", basename)
    return _clean_alias(stem)
