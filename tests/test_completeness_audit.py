import json

from dst_wiki_db.completeness_audit import rebuild_entity_completeness_audit
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_completeness_audit_combines_source_media_and_data_coverage(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    full_id = upsert_entity(
        conn,
        canonical_title="Bee Queen",
        kind="boss",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Bee_Queen",
        summary="",
    )
    sparse_id = upsert_entity(
        conn,
        canonical_title="Mystery",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Mystery",
        summary="",
    )
    _entity_coverage(
        conn,
        full_id,
        "bee-queen",
        "Bee Queen",
        "boss",
        coverage_score=100,
        attribute_count=3,
        stat_count=2,
        stat_value_count=2,
        variant_count=1,
        category_count=1,
        resolved_relation_count=2,
        official_mention_count=1,
        has_source=1,
        has_attributes=1,
        has_stats=1,
        has_variants=1,
        has_categories=1,
        has_relations=1,
        has_official_mentions=1,
    )
    _source_coverage(
        conn,
        full_id,
        "bee-queen",
        "Bee Queen",
        "boss",
        coverage_status="both_sources",
        source_profile_count=2,
        matched_page_count=3,
        has_both_core_wikis=1,
    )
    _media_coverage(
        conn,
        full_id,
        "bee-queen",
        "Bee Queen",
        "boss",
        media_status="downloaded_media",
        media_count=2,
        variant_count=1,
        has_media_profile=1,
        has_primary_image=1,
        has_direct_url=1,
    )
    _entity_coverage(
        conn,
        sparse_id,
        "mystery",
        "Mystery",
        "item",
        coverage_score=10,
        has_source=1,
    )
    _source_coverage(
        conn,
        sparse_id,
        "mystery",
        "Mystery",
        "item",
        coverage_status="wiki.gg_only",
        source_profile_count=1,
        matched_page_count=1,
    )
    _media_coverage(
        conn,
        sparse_id,
        "mystery",
        "Mystery",
        "item",
        media_status="no_media",
    )
    conn.execute(
        """
        insert into entity_source_gap_queue (
            entity_id, slug, canonical_title, kind, missing_source_key,
            coverage_status, priority
        )
        values (?, 'mystery', 'Mystery', 'item', 'fandom', 'wiki.gg_only', 35)
        """,
        (sparse_id,),
    )
    conn.execute(
        """
        insert into entity_media_gap_queue (
            entity_id, slug, canonical_title, kind, gap_reason,
            media_status, priority
        )
        values (?, 'mystery', 'Mystery', 'item', 'missing_media', 'no_media', 30)
        """,
        (sparse_id,),
    )

    result = rebuild_entity_completeness_audit(conn)

    assert result == 2
    rows = {
        row["canonical_title"]: dict(row)
        for row in conn.execute(
            """
            select canonical_title, readiness_score, readiness_status,
                   source_gap_count, media_gap_count,
                   missing_requirements_json, next_actions_json
            from entity_completeness_audit
            order by canonical_title
            """
        )
    }
    assert rows["Bee Queen"] == {
        "canonical_title": "Bee Queen",
        "readiness_score": 100,
        "readiness_status": "complete_profile",
        "source_gap_count": 0,
        "media_gap_count": 0,
        "missing_requirements_json": "[]",
        "next_actions_json": "[]",
    }
    assert rows["Mystery"]["readiness_score"] == 10
    assert rows["Mystery"]["readiness_status"] == "sparse_profile"
    assert rows["Mystery"]["source_gap_count"] == 1
    assert rows["Mystery"]["media_gap_count"] == 1
    assert json.loads(rows["Mystery"]["missing_requirements_json"]) == [
        "core_source_pair",
        "attributes",
        "stats",
        "media",
        "primary_direct_media",
        "variants",
        "categories",
        "relationships",
        "official_mentions",
    ]
    assert [
        action["action"] for action in json.loads(rows["Mystery"]["next_actions_json"])
    ] == [
        "fill_source_alignment",
        "fill_media_evidence",
        "parse_infobox_stats",
        "expand_variant_evidence",
        "resolve_gameplay_relationships",
        "verify_against_official_sources",
    ]


def test_rebuild_entity_completeness_audit_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Wilson",
        summary="",
    )
    _entity_coverage(
        conn,
        entity_id,
        "wilson",
        "Wilson",
        "character",
        coverage_score=40,
        has_source=1,
        has_attributes=1,
        has_categories=1,
    )

    first = rebuild_entity_completeness_audit(conn)
    second = rebuild_entity_completeness_audit(conn)

    assert first == second == 1
    row = conn.execute(
        "select readiness_score, readiness_status from entity_completeness_audit"
    ).fetchone()
    assert tuple(row) == (30, "sparse_profile")


def _entity_coverage(
    conn,
    entity_id,
    slug,
    title,
    kind,
    **kwargs,
):
    values = {
        "coverage_score": 0,
        "attribute_count": 0,
        "stat_count": 0,
        "stat_value_count": 0,
        "variant_count": 0,
        "category_count": 0,
        "resolved_relation_count": 0,
        "resolved_fact_count": 0,
        "resolved_recipe_ingredient_count": 0,
        "official_mention_count": 0,
        "has_source": 0,
        "has_attributes": 0,
        "has_stats": 0,
        "has_variants": 0,
        "has_categories": 0,
        "has_relations": 0,
        "has_facts": 0,
        "has_recipes": 0,
        "has_official_mentions": 0,
    } | kwargs
    conn.execute(
        """
        insert into entity_coverage (
            entity_id, slug, canonical_title, kind, coverage_score,
            attribute_count, stat_count, stat_value_count, variant_count,
            category_count, resolved_relation_count, resolved_fact_count,
            resolved_recipe_ingredient_count, official_mention_count,
            has_source, has_attributes, has_stats, has_variants,
            has_categories, has_relations, has_facts, has_recipes,
            has_official_mentions, missing_summary
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, '')
        """,
        (
            entity_id,
            slug,
            title,
            kind,
            values["coverage_score"],
            values["attribute_count"],
            values["stat_count"],
            values["stat_value_count"],
            values["variant_count"],
            values["category_count"],
            values["resolved_relation_count"],
            values["resolved_fact_count"],
            values["resolved_recipe_ingredient_count"],
            values["official_mention_count"],
            values["has_source"],
            values["has_attributes"],
            values["has_stats"],
            values["has_variants"],
            values["has_categories"],
            values["has_relations"],
            values["has_facts"],
            values["has_recipes"],
            values["has_official_mentions"],
        ),
    )


def _source_coverage(
    conn,
    entity_id,
    slug,
    title,
    kind,
    **kwargs,
):
    values = {
        "coverage_status": "missing_source_profiles",
        "source_profile_count": 0,
        "matched_page_count": 0,
        "has_both_core_wikis": 0,
    } | kwargs
    conn.execute(
        """
        insert into entity_source_coverage (
            entity_id, slug, canonical_title, kind, coverage_status,
            source_profile_count, matched_page_count, has_both_core_wikis
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            slug,
            title,
            kind,
            values["coverage_status"],
            values["source_profile_count"],
            values["matched_page_count"],
            values["has_both_core_wikis"],
        ),
    )


def _media_coverage(
    conn,
    entity_id,
    slug,
    title,
    kind,
    **kwargs,
):
    values = {
        "media_status": "no_media",
        "media_count": 0,
        "variant_count": 0,
        "has_media_profile": 0,
        "has_primary_image": 0,
        "has_direct_url": 0,
    } | kwargs
    conn.execute(
        """
        insert into entity_media_coverage (
            entity_id, slug, canonical_title, kind, media_status,
            media_count, variant_count, has_media_profile,
            has_primary_image, has_direct_url
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            slug,
            title,
            kind,
            values["media_status"],
            values["media_count"],
            values["variant_count"],
            values["has_media_profile"],
            values["has_primary_image"],
            values["has_direct_url"],
        ),
    )
