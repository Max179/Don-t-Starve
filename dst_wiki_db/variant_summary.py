from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from dst_wiki_db.variants import variant_label, variant_type


SOURCE_ORDER = ("attributes", "stats", "facts", "recipes", "entity_variants", "media")


@dataclass
class VariantAggregate:
    entity_id: int
    variant_key: str
    variant_type: str = ""
    label: str = ""
    attribute_count: int = 0
    stat_count: int = 0
    fact_count: int = 0
    recipe_ingredient_count: int = 0
    entity_variant_count: int = 0
    media_asset_count: int = 0
    primary_media_asset_count: int = 0


def rebuild_entity_variant_summary(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_variant_summary")
    aggregates: dict[tuple[int, str], VariantAggregate] = {}
    _merge_entity_variants(conn, aggregates)
    _merge_variant_key_counts(
        conn,
        aggregates,
        table="entity_attributes",
        count_field="attribute_count",
    )
    _merge_variant_key_counts(
        conn,
        aggregates,
        table="entity_stats",
        count_field="stat_count",
    )
    _merge_variant_key_counts(
        conn,
        aggregates,
        table="entity_facts",
        count_field="fact_count",
    )
    _merge_variant_key_counts(
        conn,
        aggregates,
        table="recipe_ingredients",
        count_field="recipe_ingredient_count",
    )
    _merge_media_assets(conn, aggregates)

    entities = {
        int(row["id"]): row
        for row in conn.execute(
            "select id, slug, canonical_title, kind from entities"
        ).fetchall()
    }
    count = 0
    for key in sorted(aggregates):
        aggregate = aggregates[key]
        entity = entities.get(aggregate.entity_id)
        if entity is None:
            continue
        vtype = aggregate.variant_type or variant_type(aggregate.variant_key)
        label = aggregate.label or variant_label(aggregate.variant_key)
        source_summary = _source_summary(aggregate)
        confidence = _confidence(aggregate)
        conn.execute(
            """
            insert into entity_variant_summary (
                entity_id, slug, canonical_title, kind, variant_key,
                variant_type, label, attribute_count, stat_count, fact_count,
                recipe_ingredient_count, entity_variant_count,
                media_asset_count, primary_media_asset_count, has_data,
                has_media, has_stats, has_facts, has_recipes, confidence,
                source_summary
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                aggregate.entity_id,
                str(entity["slug"]),
                str(entity["canonical_title"]),
                str(entity["kind"]),
                aggregate.variant_key,
                vtype,
                label,
                aggregate.attribute_count,
                aggregate.stat_count,
                aggregate.fact_count,
                aggregate.recipe_ingredient_count,
                aggregate.entity_variant_count,
                aggregate.media_asset_count,
                aggregate.primary_media_asset_count,
                int(
                    aggregate.attribute_count > 0
                    or aggregate.stat_count > 0
                    or aggregate.fact_count > 0
                    or aggregate.recipe_ingredient_count > 0
                    or aggregate.entity_variant_count > 0
                ),
                int(aggregate.media_asset_count > 0),
                int(aggregate.stat_count > 0),
                int(aggregate.fact_count > 0),
                int(aggregate.recipe_ingredient_count > 0),
                confidence,
                source_summary,
            ),
        )
        count += 1
    conn.commit()
    return count


def _aggregate(
    aggregates: dict[tuple[int, str], VariantAggregate],
    *,
    entity_id: int,
    variant_key: str,
) -> VariantAggregate:
    key = (entity_id, variant_key)
    if key not in aggregates:
        aggregates[key] = VariantAggregate(entity_id=entity_id, variant_key=variant_key)
    return aggregates[key]


def _merge_entity_variants(
    conn: sqlite3.Connection,
    aggregates: dict[tuple[int, str], VariantAggregate],
) -> None:
    rows = conn.execute(
        """
        select entity_id, variant_key, variant_type, label, count(*) as count
        from entity_variants
        where variant_key != ''
        group by entity_id, variant_key, variant_type, label
        """
    ).fetchall()
    for row in rows:
        aggregate = _aggregate(
            aggregates,
            entity_id=int(row["entity_id"]),
            variant_key=str(row["variant_key"]),
        )
        aggregate.entity_variant_count += int(row["count"])
        if not aggregate.variant_type:
            aggregate.variant_type = str(row["variant_type"])
        if not aggregate.label:
            aggregate.label = str(row["label"])


def _merge_variant_key_counts(
    conn: sqlite3.Connection,
    aggregates: dict[tuple[int, str], VariantAggregate],
    *,
    table: str,
    count_field: str,
) -> None:
    rows = conn.execute(
        f"""
        select entity_id, variant_key, count(*) as count
        from {table}
        where variant_key is not null and variant_key != ''
        group by entity_id, variant_key
        """
    ).fetchall()
    for row in rows:
        aggregate = _aggregate(
            aggregates,
            entity_id=int(row["entity_id"]),
            variant_key=str(row["variant_key"]),
        )
        setattr(aggregate, count_field, getattr(aggregate, count_field) + int(row["count"]))


def _merge_media_assets(
    conn: sqlite3.Connection,
    aggregates: dict[tuple[int, str], VariantAggregate],
) -> None:
    rows = conn.execute(
        """
        select
            entity_id,
            variant_key,
            variant_type,
            variant_label,
            count(*) as media_asset_count,
            sum(case when is_primary = 1 then 1 else 0 end) as primary_media_asset_count
        from entity_media_assets
        where is_variant = 1 and variant_key != ''
        group by entity_id, variant_key, variant_type, variant_label
        """
    ).fetchall()
    for row in rows:
        aggregate = _aggregate(
            aggregates,
            entity_id=int(row["entity_id"]),
            variant_key=str(row["variant_key"]),
        )
        aggregate.media_asset_count += int(row["media_asset_count"])
        aggregate.primary_media_asset_count += int(row["primary_media_asset_count"] or 0)
        if not aggregate.variant_type and row["variant_type"]:
            aggregate.variant_type = str(row["variant_type"])
        if not aggregate.label and row["variant_label"]:
            aggregate.label = str(row["variant_label"])


def _source_summary(aggregate: VariantAggregate) -> str:
    present = []
    if aggregate.attribute_count:
        present.append("attributes")
    if aggregate.stat_count:
        present.append("stats")
    if aggregate.fact_count:
        present.append("facts")
    if aggregate.recipe_ingredient_count:
        present.append("recipes")
    if aggregate.entity_variant_count:
        present.append("entity_variants")
    if aggregate.media_asset_count:
        present.append("media")
    return "|".join(source for source in SOURCE_ORDER if source in present)


def _confidence(aggregate: VariantAggregate) -> float:
    score = 0.4
    if aggregate.entity_variant_count:
        score += 0.25
    if aggregate.attribute_count or aggregate.stat_count:
        score += 0.2
    if aggregate.media_asset_count:
        score += 0.15
    if aggregate.fact_count or aggregate.recipe_ingredient_count:
        score += 0.1
    return min(1.0, round(score, 2))
