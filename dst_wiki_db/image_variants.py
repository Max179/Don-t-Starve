from __future__ import annotations

import re
import sqlite3


IMAGE_EXTENSION_RE = re.compile(r"-(?:png|jpg|jpeg|gif|webp)$", re.IGNORECASE)

BUILD_STATE_KEYS = {"build", "built"}
STATE_KEYS = {
    "burnt",
    "burned",
    "dropped",
    "frozen",
    "sleeping",
    "open",
    "used",
    "wet",
}
FARM_PLANT_PREFIXES = {"plant", "stalk"}
FARM_PLANT_GROWTH_STAGES = {"seed", "sprout", "small", "med", "medium", "full", "large"}
PHASE_RE = re.compile(r"^(?:phase|form)-\d+$")
STAGE_RE = re.compile(r"^(?:stage|stages|life-stage|life-stages)(?:-\d+)?$")


def rebuild_image_variants(conn: sqlite3.Connection) -> int:
    conn.execute("delete from image_variants")
    entity_slugs = _entity_slugs(conn)
    rows = conn.execute(
        """
        select
            pi.id as page_image_id,
            pi.entity_id,
            pi.source_id,
            pi.raw_page_id,
            pi.image_name,
            pi.image_slug,
            e.slug as entity_slug
        from page_images pi
        join entities e on e.id = pi.entity_id
        order by pi.entity_id, pi.image_slug
        """
    ).fetchall()

    count = 0
    for row in rows:
        candidate = _candidate_from_image_slug(
            entity_slug=str(row["entity_slug"]),
            image_slug=str(row["image_slug"]),
            entity_slugs=entity_slugs,
        )
        if candidate is None:
            continue
        variant_key, variant_type, confidence = candidate
        conn.execute(
            """
            insert into image_variants (
                entity_id, source_id, raw_page_id, page_image_id,
                image_name, image_slug, variant_key, variant_type,
                label, match_method, confidence
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(row["entity_id"]),
                int(row["source_id"]),
                int(row["raw_page_id"]),
                int(row["page_image_id"]),
                str(row["image_name"]),
                str(row["image_slug"]),
                variant_key,
                variant_type,
                _label(variant_key),
                "entity_slug_filename_prefix",
                confidence,
            ),
        )
        count += 1
    conn.commit()
    return count


def _candidate_from_image_slug(
    *, entity_slug: str, image_slug: str, entity_slugs: set[str]
) -> tuple[str, str, float] | None:
    stem = IMAGE_EXTENSION_RE.sub("", image_slug)
    prefix = f"{entity_slug}-"
    if not stem.startswith(prefix):
        return None
    if stem in entity_slugs:
        return None
    variant_key = stem[len(prefix) :].strip("-")
    if not variant_key:
        return None
    return variant_key, _variant_type(variant_key), _confidence(variant_key)


def _variant_type(variant_key: str) -> str:
    if variant_key in BUILD_STATE_KEYS:
        return "build_state"
    if variant_key in STATE_KEYS:
        return "state"
    crop_stage = _crop_stage_key(variant_key)
    if crop_stage in FARM_PLANT_GROWTH_STAGES:
        return "growth_stage"
    if crop_stage in {"oversized", "oversized-rot", "rot-oversized"}:
        return "oversized_form"
    if PHASE_RE.match(variant_key):
        return "phase"
    if STAGE_RE.match(variant_key):
        return "growth_stage"
    if "animation" in variant_key or variant_key.endswith("-gif"):
        return "animation"
    if "map-icon" in variant_key or variant_key == "map-icons":
        return "map_icon"
    if "figure" in variant_key or "sketch" in variant_key:
        return "reference_asset"
    return "visual_variant"


def _confidence(variant_key: str) -> float:
    variant_type = _variant_type(variant_key)
    if variant_type in {
        "build_state",
        "state",
        "phase",
        "growth_stage",
        "oversized_form",
    }:
        return 0.85
    if variant_type in {"animation", "map_icon"}:
        return 0.7
    if variant_type == "reference_asset":
        return 0.45
    return 0.6


def _label(variant_key: str) -> str:
    return " ".join(part.capitalize() for part in variant_key.split("-") if part)


def _crop_stage_key(variant_key: str) -> str | None:
    prefix, separator, stage = variant_key.partition("-")
    if not separator or prefix not in FARM_PLANT_PREFIXES:
        return None
    return stage


def _entity_slugs(conn: sqlite3.Connection) -> set[str]:
    return {str(row["slug"]) for row in conn.execute("select slug from entities")}
