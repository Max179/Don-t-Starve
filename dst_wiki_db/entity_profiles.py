from __future__ import annotations

import base64
import gzip
import json
import sqlite3
from typing import Any


PROFILE_ENCODING = "gzip+base64+json"


def rebuild_entity_profile_json(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_profile_json")
    rows = conn.execute(
        """
        select
            id as entity_id,
            slug,
            canonical_title,
            kind,
            canonical_url,
            summary
        from entities
        order by id
        """
    ).fetchall()
    count = 0
    for row in rows:
        entity_id = int(row["entity_id"])
        profile = _profile_for_entity(conn, row)
        counts = profile["counts"]
        coverage_score = int(profile["coverage"].get("coverage_score", 0))
        conn.execute(
            """
            insert into entity_profile_json (
                entity_id, slug, canonical_title, kind, coverage_score,
                media_count, stat_count, variant_count, category_count,
                fact_count, recipe_ingredient_count, official_mention_count,
                relationship_count, taxonomy_count, profile_encoding,
                profile_json, updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                entity_id,
                str(row["slug"]),
                str(row["canonical_title"]),
                str(row["kind"]),
                coverage_score,
                counts["media"],
                counts["stats"],
                counts["variants"],
                counts["categories"],
                counts["facts"],
                counts["recipes"],
                counts["official_mentions"],
                counts["relationships"],
                counts["taxonomy"],
                PROFILE_ENCODING,
                dump_profile_json(profile),
            ),
        )
        count += 1
    conn.commit()
    return count


def dump_profile_json(profile: dict[str, Any]) -> str:
    payload = json.dumps(profile, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return base64.b64encode(gzip.compress(payload, compresslevel=9)).decode("ascii")


def load_profile_json(row_or_text: sqlite3.Row | str, encoding: str | None = None) -> dict[str, Any]:
    if isinstance(row_or_text, str):
        text = row_or_text
        profile_encoding = encoding or "json"
    else:
        text = str(row_or_text["profile_json"])
        profile_encoding = str(row_or_text["profile_encoding"])
    if profile_encoding == PROFILE_ENCODING:
        payload = gzip.decompress(base64.b64decode(text.encode("ascii"))).decode("utf-8")
        return json.loads(payload)
    if profile_encoding == "json":
        return json.loads(text)
    raise ValueError(f"Unsupported profile encoding: {profile_encoding}")


def _profile_for_entity(conn: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    entity_id = int(row["entity_id"])
    media = _media(conn, entity_id)
    stats = _stats(conn, entity_id)
    stat_rollups = _stat_rollups(conn, entity_id)
    variants = _variants(conn, entity_id)
    categories = _categories(conn, entity_id)
    facts = _facts(conn, entity_id)
    recipes = _recipes(conn, entity_id)
    official_mentions = _official_mentions(conn, entity_id)
    relationships = _relationships(conn, entity_id)
    taxonomy = _taxonomy(conn, entity_id)
    combat_profile = _combat_profile(conn, entity_id)
    food_profile = _food_profile(conn, entity_id)
    item_profile = _item_profile(conn, entity_id)
    world_profile = _world_profile(conn, entity_id)
    return {
        "identity": {
            "id": entity_id,
            "slug": str(row["slug"]),
            "title": str(row["canonical_title"]),
            "kind": str(row["kind"]),
            "canonical_url": row["canonical_url"],
            "summary": row["summary"] or "",
        },
        "coverage": _coverage(conn, entity_id),
        "counts": {
            "media": len(media),
            "stats": len(stats),
            "variants": len(variants),
            "categories": len(categories),
            "facts": len(facts),
            "recipes": len(recipes),
            "official_mentions": len(official_mentions),
            "relationships": len(relationships),
            "taxonomy": len(taxonomy),
        },
        "media": media,
        "stats": stats,
        "stat_rollups": stat_rollups,
        "variants": variants,
        "categories": categories,
        "facts": facts,
        "recipes": recipes,
        "official_mentions": official_mentions,
        "relationships": relationships,
        "taxonomy": taxonomy,
        "combat_profile": combat_profile,
        "food_profile": food_profile,
        "item_profile": item_profile,
        "world_profile": world_profile,
    }


def _coverage(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any]:
    row = conn.execute(
        """
        select
            source_count,
            raw_page_count,
            attribute_count,
            stat_count,
            stat_value_count,
            infobox_image_count,
            page_image_count,
            variant_count,
            category_count,
            relation_count,
            resolved_relation_count,
            fact_count,
            resolved_fact_count,
            recipe_ingredient_count,
            resolved_recipe_ingredient_count,
            official_mention_count,
            has_source,
            has_attributes,
            has_stats,
            has_images,
            has_variants,
            has_categories,
            has_relations,
            has_facts,
            has_recipes,
            has_official_mentions,
            coverage_score,
            missing_summary
        from entity_coverage
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    if row is None:
        return {
            "coverage_score": 0,
            "missing": ["coverage"],
            "counts": {},
            "flags": {},
        }
    count_keys = (
        "source_count",
        "raw_page_count",
        "attribute_count",
        "stat_count",
        "stat_value_count",
        "infobox_image_count",
        "page_image_count",
        "variant_count",
        "category_count",
        "relation_count",
        "resolved_relation_count",
        "fact_count",
        "resolved_fact_count",
        "recipe_ingredient_count",
        "resolved_recipe_ingredient_count",
        "official_mention_count",
    )
    flag_keys = (
        "has_source",
        "has_attributes",
        "has_stats",
        "has_images",
        "has_variants",
        "has_categories",
        "has_relations",
        "has_facts",
        "has_recipes",
        "has_official_mentions",
    )
    missing_summary = str(row["missing_summary"] or "")
    return {
        "coverage_score": int(row["coverage_score"]),
        "missing": [part for part in missing_summary.split("|") if part],
        "counts": {key: int(row[key]) for key in count_keys},
        "flags": {key: bool(row[key]) for key in flag_keys},
    }


def _media(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            asset_source,
            image_name,
            image_slug,
            role,
            original_url,
            description_url,
            local_path,
            width,
            height,
            mime,
            variant_key,
            variant_type,
            variant_label,
            is_variant,
            is_primary,
            confidence
        from entity_media_assets
        where entity_id = ?
        order by is_primary desc, is_variant desc, asset_source, image_name, id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "asset_source": str(row["asset_source"]),
            "image_name": str(row["image_name"]),
            "image_slug": str(row["image_slug"]),
            "role": str(row["role"]),
            "original_url": row["original_url"],
            "description_url": row["description_url"],
            "local_path": row["local_path"],
            "width": _optional_int(row["width"]),
            "height": _optional_int(row["height"]),
            "mime": row["mime"],
            "variant_key": str(row["variant_key"] or ""),
            "variant_type": str(row["variant_type"] or ""),
            "variant_label": str(row["variant_label"] or ""),
            "is_variant": bool(row["is_variant"]),
            "is_primary": bool(row["is_primary"]),
            "confidence": _optional_float(row["confidence"]),
        }
        for row in rows
    ]


def _stats(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            stat_name,
            stat_type,
            raw_name,
            value_text,
            value_number,
            unit,
            variant_key
        from entity_stats
        where entity_id = ?
        order by stat_type, stat_name, raw_name, id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "stat_name": str(row["stat_name"]),
            "stat_type": str(row["stat_type"]),
            "raw_name": str(row["raw_name"]),
            "value_text": str(row["value_text"]),
            "value_number": _optional_float(row["value_number"]),
            "unit": str(row["unit"]),
            "variant_key": str(row["variant_key"] or ""),
        }
        for row in rows
    ]


def _stat_rollups(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            stat_name,
            stat_type,
            unit,
            value_min,
            value_max,
            value_count,
            evidence_count,
            source_count,
            variant_count,
            value_texts
        from entity_stat_rollups
        where entity_id = ?
        order by stat_type, stat_name, unit, id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "stat_name": str(row["stat_name"]),
            "stat_type": str(row["stat_type"]),
            "unit": str(row["unit"]),
            "value_range": {
                "min": _optional_float(row["value_min"]),
                "max": _optional_float(row["value_max"]),
            },
            "value_count": int(row["value_count"]),
            "evidence_count": int(row["evidence_count"]),
            "source_count": int(row["source_count"]),
            "variant_count": int(row["variant_count"]),
            "value_texts": str(row["value_texts"]),
        }
        for row in rows
    ]


def _variants(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            variant_key,
            variant_type,
            label,
            attribute_count,
            stat_count,
            fact_count,
            recipe_ingredient_count,
            entity_variant_count,
            media_asset_count,
            primary_media_asset_count,
            has_data,
            has_media,
            has_stats,
            has_facts,
            has_recipes,
            confidence,
            source_summary
        from entity_variant_summary
        where entity_id = ?
        order by variant_type, variant_key, id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "variant_key": str(row["variant_key"]),
            "variant_type": str(row["variant_type"]),
            "label": str(row["label"]),
            "counts": {
                "attributes": int(row["attribute_count"]),
                "stats": int(row["stat_count"]),
                "facts": int(row["fact_count"]),
                "recipes": int(row["recipe_ingredient_count"]),
                "explicit_variants": int(row["entity_variant_count"]),
                "media": int(row["media_asset_count"]),
                "primary_media": int(row["primary_media_asset_count"]),
            },
            "flags": {
                "has_data": bool(row["has_data"]),
                "has_media": bool(row["has_media"]),
                "has_stats": bool(row["has_stats"]),
                "has_facts": bool(row["has_facts"]),
                "has_recipes": bool(row["has_recipes"]),
            },
            "confidence": _optional_float(row["confidence"]),
            "source_summary": str(row["source_summary"]),
        }
        for row in rows
    ]


def _categories(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, str]]:
    rows = conn.execute(
        """
        select distinct category_name, category_slug
        from entity_categories
        where entity_id = ?
        order by category_name, category_slug
        """,
        (entity_id,),
    ).fetchall()
    return [
        {"name": str(row["category_name"]), "slug": str(row["category_slug"])}
        for row in rows
    ]


def _facts(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            fact_type,
            raw_name,
            value_text,
            target_title,
            target_slug,
            probability_text,
            quantity_text,
            quantity_number,
            variant_key
        from entity_facts
        where entity_id = ?
        order by fact_type, fact_index, raw_name, id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "fact_type": str(row["fact_type"]),
            "raw_name": str(row["raw_name"]),
            "value_text": str(row["value_text"]),
            "target_title": row["target_title"],
            "target_slug": str(row["target_slug"] or ""),
            "probability_text": row["probability_text"],
            "quantity_text": row["quantity_text"],
            "quantity_number": _optional_float(row["quantity_number"]),
            "variant_key": str(row["variant_key"] or ""),
        }
        for row in rows
    ]


def _recipes(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            ingredient_slot,
            ingredient_name,
            ingredient_slug,
            quantity_text,
            quantity_number,
            variant_key
        from recipe_ingredients
        where entity_id = ?
        order by template_index, ingredient_slot, id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "ingredient_slot": int(row["ingredient_slot"]),
            "ingredient_name": str(row["ingredient_name"]),
            "ingredient_slug": str(row["ingredient_slug"]),
            "quantity_text": row["quantity_text"],
            "quantity_number": _optional_float(row["quantity_number"]),
            "variant_key": str(row["variant_key"] or ""),
        }
        for row in rows
    ]


def _official_mentions(
    conn: sqlite3.Connection, entity_id: int
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            orm.provider,
            orm.record_type,
            orm.external_id,
            orm.mention_text,
            orm.match_field,
            orm.match_method,
            orm.confidence,
            orm.context_text,
            official_records.title,
            official_records.url
        from official_record_mentions orm
        join official_records on official_records.id = orm.official_record_id
        where orm.entity_id = ?
        order by orm.provider, orm.record_type, orm.external_id, orm.match_field, orm.id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "provider": str(row["provider"]),
            "record_type": str(row["record_type"]),
            "external_id": str(row["external_id"]),
            "title": str(row["title"]),
            "url": row["url"],
            "mention_text": str(row["mention_text"]),
            "match_field": str(row["match_field"]),
            "match_method": str(row["match_method"]),
            "confidence": _optional_float(row["confidence"]),
            "context_text": str(row["context_text"]),
        }
        for row in rows
    ]


def _relationships(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            related_entity_id,
            related_title,
            related_slug,
            related_kind,
            edge_type,
            edge_group,
            direction,
            source_table,
            source_row_id,
            quantity_text,
            quantity_number,
            probability_text,
            variant_key,
            confidence
        from entity_gameplay_edges
        where entity_id = ?
        order by edge_group, edge_type, related_title, id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "related_entity_id": int(row["related_entity_id"]),
            "related_title": str(row["related_title"]),
            "related_slug": str(row["related_slug"]),
            "related_kind": str(row["related_kind"]),
            "edge_type": str(row["edge_type"]),
            "edge_group": str(row["edge_group"]),
            "direction": str(row["direction"]),
            "source_table": str(row["source_table"]),
            "source_row_id": int(row["source_row_id"]),
            "quantity_text": row["quantity_text"],
            "quantity_number": _optional_float(row["quantity_number"]),
            "probability_text": row["probability_text"],
            "variant_key": str(row["variant_key"] or ""),
            "confidence": _optional_float(row["confidence"]),
        }
        for row in rows
    ]


def _taxonomy(conn: sqlite3.Connection, entity_id: int) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        select
            taxonomy_type,
            taxonomy_key,
            label,
            confidence,
            evidence_source,
            evidence_count
        from entity_taxonomy
        where entity_id = ?
        order by taxonomy_type, taxonomy_key, id
        """,
        (entity_id,),
    ).fetchall()
    return [
        {
            "taxonomy_type": str(row["taxonomy_type"]),
            "taxonomy_key": str(row["taxonomy_key"]),
            "label": str(row["label"]),
            "confidence": _optional_float(row["confidence"]),
            "evidence_source": str(row["evidence_source"]),
            "evidence_count": int(row["evidence_count"]),
        }
        for row in rows
    ]


def _combat_profile(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        select
            health_min,
            health_max,
            health_text,
            health_evidence_count,
            damage_min,
            damage_max,
            damage_text,
            damage_evidence_count,
            attack_range_min,
            attack_range_max,
            attack_range_text,
            attack_range_evidence_count,
            attack_period_min,
            attack_period_max,
            attack_period_text,
            attack_period_evidence_count,
            walk_speed_min,
            walk_speed_max,
            walk_speed_text,
            walk_speed_evidence_count,
            run_speed_min,
            run_speed_max,
            run_speed_text,
            run_speed_evidence_count,
            combat_stat_count,
            movement_stat_count,
            source_count,
            variant_count
        from entity_combat_profiles
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "health": _profile_stat(row, "health"),
        "damage": _profile_stat(row, "damage"),
        "attack_range": _profile_stat(row, "attack_range"),
        "attack_period": _profile_stat(row, "attack_period"),
        "walk_speed": _profile_stat(row, "walk_speed"),
        "run_speed": _profile_stat(row, "run_speed"),
        "counts": {
            "combat_stats": int(row["combat_stat_count"]),
            "movement_stats": int(row["movement_stat_count"]),
            "sources": int(row["source_count"]),
            "variants": int(row["variant_count"]),
        },
    }


def _food_profile(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        select
            health_min,
            health_max,
            health_text,
            hunger_min,
            hunger_max,
            hunger_text,
            sanity_min,
            sanity_max,
            sanity_text,
            food_value_min,
            food_value_max,
            food_value_text,
            spoil_days_min,
            spoil_days_max,
            spoil_text,
            cooktime_seconds_min,
            cooktime_seconds_max,
            cooktime_text,
            priority_min,
            priority_max,
            priority_text,
            stat_count,
            source_count,
            variant_count,
            has_restore_stats,
            has_food_value
        from entity_food_profiles
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "health": _profile_min_max_text(row, "health"),
        "hunger": _profile_min_max_text(row, "hunger"),
        "sanity": _profile_min_max_text(row, "sanity"),
        "food_value": _profile_min_max_text(row, "food_value"),
        "spoil_days": {
            "min": _optional_float(row["spoil_days_min"]),
            "max": _optional_float(row["spoil_days_max"]),
            "text": str(row["spoil_text"] or ""),
        },
        "cooktime_seconds": {
            "min": _optional_float(row["cooktime_seconds_min"]),
            "max": _optional_float(row["cooktime_seconds_max"]),
            "text": str(row["cooktime_text"] or ""),
        },
        "priority": _profile_min_max_text(row, "priority"),
        "counts": {
            "stats": int(row["stat_count"]),
            "sources": int(row["source_count"]),
            "variants": int(row["variant_count"]),
        },
        "flags": {
            "has_restore_stats": bool(row["has_restore_stats"]),
            "has_food_value": bool(row["has_food_value"]),
        },
    }


def _item_profile(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        select
            damage_min,
            damage_max,
            damage_text,
            durability_min,
            durability_max,
            durability_text,
            protection_min,
            protection_max,
            protection_text,
            water_resistance_min,
            water_resistance_max,
            water_resistance_text,
            stack_min,
            stack_max,
            stack_text,
            stacklimit_min,
            stacklimit_max,
            stacklimit_text,
            burn_time_seconds_min,
            burn_time_seconds_max,
            burn_time_text,
            tier_min,
            tier_max,
            tier_text,
            resources_min,
            resources_max,
            resources_text,
            renew_min,
            renew_max,
            renew_text,
            priority_min,
            priority_max,
            priority_text,
            stat_count,
            source_count,
            variant_count,
            has_weapon_stats,
            has_armor_stats,
            has_stack_stats
        from entity_item_profiles
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "damage": _profile_min_max_text(row, "damage"),
        "durability": _profile_min_max_text(row, "durability"),
        "protection": _profile_min_max_text(row, "protection"),
        "water_resistance": _profile_min_max_text(row, "water_resistance"),
        "stack": _profile_min_max_text(row, "stack"),
        "stacklimit": _profile_min_max_text(row, "stacklimit"),
        "burn_time_seconds": {
            "min": _optional_float(row["burn_time_seconds_min"]),
            "max": _optional_float(row["burn_time_seconds_max"]),
            "text": str(row["burn_time_text"] or ""),
        },
        "tier": _profile_min_max_text(row, "tier"),
        "resources": _profile_min_max_text(row, "resources"),
        "renew": _profile_min_max_text(row, "renew"),
        "priority": _profile_min_max_text(row, "priority"),
        "counts": {
            "stats": int(row["stat_count"]),
            "sources": int(row["source_count"]),
            "variants": int(row["variant_count"]),
        },
        "flags": {
            "has_weapon_stats": bool(row["has_weapon_stats"]),
            "has_armor_stats": bool(row["has_armor_stats"]),
            "has_stack_stats": bool(row["has_stack_stats"]),
        },
    }


def _world_profile(conn: sqlite3.Connection, entity_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        """
        select
            biome_text,
            spawn_code_text,
            renew_text,
            resources_min,
            resources_max,
            resources_text,
            tool_text,
            perk_text,
            special_ability_text,
            growth_formula_text,
            seasons_text,
            health_min,
            health_max,
            health_text,
            damage_min,
            damage_max,
            damage_text,
            attack_range_min,
            attack_range_max,
            attack_range_text,
            attack_period_min,
            attack_period_max,
            attack_period_text,
            attribute_count,
            stat_count,
            source_count,
            variant_count,
            has_biome,
            has_spawn_code,
            is_renewable,
            has_resources,
            has_growth_data,
            has_combat_stats
        from entity_world_profiles
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "biome_text": str(row["biome_text"] or ""),
        "spawn_code_text": str(row["spawn_code_text"] or ""),
        "renew_text": str(row["renew_text"] or ""),
        "resources": {
            "min": _optional_float(row["resources_min"]),
            "max": _optional_float(row["resources_max"]),
            "text": str(row["resources_text"] or ""),
        },
        "tool_text": str(row["tool_text"] or ""),
        "perk_text": str(row["perk_text"] or ""),
        "special_ability_text": str(row["special_ability_text"] or ""),
        "growth_formula_text": str(row["growth_formula_text"] or ""),
        "seasons_text": str(row["seasons_text"] or ""),
        "health": _profile_min_max_text(row, "health"),
        "damage": _profile_min_max_text(row, "damage"),
        "attack_range": _profile_min_max_text(row, "attack_range"),
        "attack_period": _profile_min_max_text(row, "attack_period"),
        "counts": {
            "attributes": int(row["attribute_count"]),
            "stats": int(row["stat_count"]),
            "sources": int(row["source_count"]),
            "variants": int(row["variant_count"]),
        },
        "flags": {
            "has_biome": bool(row["has_biome"]),
            "has_spawn_code": bool(row["has_spawn_code"]),
            "is_renewable": bool(row["is_renewable"]),
            "has_resources": bool(row["has_resources"]),
            "has_growth_data": bool(row["has_growth_data"]),
            "has_combat_stats": bool(row["has_combat_stats"]),
        },
    }


def _profile_min_max_text(row: sqlite3.Row, prefix: str) -> dict[str, Any]:
    return {
        "min": _optional_float(row[f"{prefix}_min"]),
        "max": _optional_float(row[f"{prefix}_max"]),
        "text": str(row[f"{prefix}_text"] or ""),
    }


def _profile_stat(row: sqlite3.Row, prefix: str) -> dict[str, Any]:
    return {
        "min": _optional_float(row[f"{prefix}_min"]),
        "max": _optional_float(row[f"{prefix}_max"]),
        "text": str(row[f"{prefix}_text"] or ""),
        "evidence_count": int(row[f"{prefix}_evidence_count"]),
    }


def _optional_int(value: Any) -> int | None:
    return None if value is None else int(value)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)
