from __future__ import annotations

from dataclasses import dataclass
import sqlite3


KIND_LABELS = {
    "boss": "Boss",
    "character": "Character",
    "food": "Food",
    "item": "Item",
    "mob": "Mob",
    "biome": "Biome",
    "page": "Page",
    "plant": "Plant",
    "structure": "Structure",
}

GAME_MODE_CATEGORY_TAGS = {
    "dont-starve": ("game_mode", "ds", "Don't Starve", 0.8),
    "dont-starve-together": ("game_mode", "dst", "Don't Starve Together", 0.85),
    "reign-of-giants": ("dlc", "reign-of-giants", "Reign of Giants", 0.8),
    "shipwrecked": ("dlc", "shipwrecked", "Shipwrecked", 0.8),
    "hamlet": ("dlc", "hamlet", "Hamlet", 0.8),
    "a-new-reign": ("dlc", "a-new-reign", "A New Reign", 0.8),
    "return-of-them": ("dlc", "return-of-them", "Return of Them", 0.8),
    "from-beyond": ("dlc", "from-beyond", "From Beyond", 0.8),
}

GAMEPLAY_CATEGORY_TAGS = {
    "hostile-creatures": ("gameplay", "hostile", "Hostile", 0.9),
    "friendly-creatures": ("gameplay", "friendly", "Friendly", 0.85),
    "neutral-creatures": ("gameplay", "neutral", "Neutral", 0.85),
    "mobs": ("gameplay", "mob", "Mob", 0.8),
    "bosses": ("gameplay", "boss", "Boss", 0.9),
    "giants": ("gameplay", "boss", "Boss", 0.85),
    "mob-dropped-items": ("gameplay", "drop_source", "Drop Source", 0.85),
    "craftable-items": ("gameplay", "craftable", "Craftable", 0.85),
    "craftable-structures": ("gameplay", "craftable", "Craftable", 0.85),
    "equipable-items": ("gameplay", "equipable", "Equipable", 0.85),
    "weapons": ("gameplay", "weapon", "Weapon", 0.85),
    "armor": ("gameplay", "armor", "Armor", 0.85),
    "healing": ("gameplay", "healing", "Healing", 0.8),
    "fuel": ("gameplay", "fuel", "Fuel", 0.8),
    "perishables": ("gameplay", "perishable", "Perishable", 0.8),
    "food": ("gameplay", "food", "Food", 0.8),
    "crock-pot-recipes": ("gameplay", "recipe", "Recipe", 0.85),
    "naturally-spawning-objects": ("gameplay", "naturally_spawning", "Naturally Spawning", 0.8),
    "non-renewable": ("gameplay", "non_renewable", "Non-Renewable", 0.8),
    "renewable": ("gameplay", "renewable", "Renewable", 0.8),
    "light-sources": ("gameplay", "light_source", "Light Source", 0.8),
    "sanity-loss": ("gameplay", "sanity_loss", "Sanity Loss", 0.8),
    "sanity-boost": ("gameplay", "sanity_boost", "Sanity Boost", 0.8),
    "biomes": ("gameplay", "biome", "Biome", 0.8),
    "resources": ("gameplay", "resource", "Resource", 0.8),
}


@dataclass
class TaxonomyTag:
    entity_id: int
    slug: str
    canonical_title: str
    kind: str
    taxonomy_type: str
    taxonomy_key: str
    label: str
    confidence: float
    evidence_source: str
    evidence_count: int = 1


def rebuild_entity_taxonomy(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_taxonomy")
    entities = conn.execute(
        """
        select id as entity_id, slug, canonical_title, kind
        from entities
        order by id
        """
    ).fetchall()
    category_rows = _category_rows(conn)
    stat_counts = _counts(conn, "entity_stats")
    spawn_code_counts = _counts(
        conn,
        "entity_attributes",
        "canonical_name = 'spawn_code' and value_text != ''",
    )
    count = 0
    for entity in entities:
        for tag in _tags_for_entity(
            entity,
            category_rows.get(int(entity["entity_id"]), []),
            stat_counts.get(int(entity["entity_id"]), 0),
            spawn_code_counts.get(int(entity["entity_id"]), 0),
        ):
            cursor = conn.execute(
                """
                insert or ignore into entity_taxonomy (
                    entity_id, slug, canonical_title, kind, taxonomy_type,
                    taxonomy_key, label, confidence, evidence_source,
                    evidence_count
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tag.entity_id,
                    tag.slug,
                    tag.canonical_title,
                    tag.kind,
                    tag.taxonomy_type,
                    tag.taxonomy_key,
                    tag.label,
                    tag.confidence,
                    tag.evidence_source,
                    tag.evidence_count,
                ),
            )
            count += 1 if cursor.rowcount == 1 else 0
    conn.commit()
    return count


def _tags_for_entity(
    entity: sqlite3.Row,
    categories: list[sqlite3.Row],
    stat_count: int,
    spawn_code_count: int,
) -> list[TaxonomyTag]:
    entity_id = int(entity["entity_id"])
    base = {
        "entity_id": entity_id,
        "slug": str(entity["slug"]),
        "canonical_title": str(entity["canonical_title"]),
        "kind": str(entity["kind"]),
    }
    tags = [
        TaxonomyTag(
            **base,
            taxonomy_type="kind",
            taxonomy_key=str(entity["kind"]),
            label=KIND_LABELS.get(str(entity["kind"]), str(entity["kind"]).title()),
            confidence=1.0,
            evidence_source="entities.kind",
        )
    ]
    for category in categories:
        category_slug = str(category["category_slug"])
        category_name = str(category["category_name"])
        evidence_count = int(category["count"])
        tags.append(
            TaxonomyTag(
                **base,
                taxonomy_type="source_category",
                taxonomy_key=category_slug,
                label=category_name,
                confidence=0.75,
                evidence_source="entity_categories",
                evidence_count=evidence_count,
            )
        )
        for mapping in (GAME_MODE_CATEGORY_TAGS, GAMEPLAY_CATEGORY_TAGS):
            mapped = mapping.get(category_slug)
            if mapped:
                taxonomy_type, taxonomy_key, label, confidence = mapped
                tags.append(
                    TaxonomyTag(
                        **base,
                        taxonomy_type=taxonomy_type,
                        taxonomy_key=taxonomy_key,
                        label=label,
                        confidence=confidence,
                        evidence_source=f"category:{category_slug}",
                        evidence_count=evidence_count,
                    )
                )
    if stat_count:
        tags.append(
            TaxonomyTag(
                **base,
                taxonomy_type="data",
                taxonomy_key="has_stats",
                label="Has Stats",
                confidence=0.95,
                evidence_source="entity_stats",
                evidence_count=stat_count,
            )
        )
    if spawn_code_count:
        tags.append(
            TaxonomyTag(
                **base,
                taxonomy_type="data",
                taxonomy_key="has_spawn_code",
                label="Has Spawn Code",
                confidence=0.95,
                evidence_source="entity_attributes.spawn_code",
                evidence_count=spawn_code_count,
            )
        )
    return _dedupe_tags(tags)


def _dedupe_tags(tags: list[TaxonomyTag]) -> list[TaxonomyTag]:
    by_key: dict[tuple[str, str], TaxonomyTag] = {}
    for tag in tags:
        key = (tag.taxonomy_type, tag.taxonomy_key)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = tag
            continue
        by_key[key] = TaxonomyTag(
            entity_id=tag.entity_id,
            slug=tag.slug,
            canonical_title=tag.canonical_title,
            kind=tag.kind,
            taxonomy_type=tag.taxonomy_type,
            taxonomy_key=tag.taxonomy_key,
            label=tag.label,
            confidence=max(existing.confidence, tag.confidence),
            evidence_source="|".join(
                sorted({existing.evidence_source, tag.evidence_source})
            ),
            evidence_count=existing.evidence_count + tag.evidence_count,
        )
    return [by_key[key] for key in sorted(by_key)]


def _category_rows(conn: sqlite3.Connection) -> dict[int, list[sqlite3.Row]]:
    rows = conn.execute(
        """
        select
            entity_id,
            category_name,
            category_slug,
            count(*) as count
        from entity_categories
        group by entity_id, category_name, category_slug
        order by entity_id, category_slug
        """
    ).fetchall()
    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(int(row["entity_id"]), []).append(row)
    return grouped


def _counts(
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
