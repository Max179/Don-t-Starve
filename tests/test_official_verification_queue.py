from dst_wiki_db.official_verification_queue import (
    rebuild_entity_official_verification_queue,
)
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_official_verification_queue_targets_missing_official_mentions(tmp_path):
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
    boss_id = upsert_entity(
        conn,
        canonical_title="Ancient Fuelweaver",
        kind="boss",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Ancient_Fuelweaver",
        summary="",
    )
    item_id = upsert_entity(
        conn,
        canonical_title="Mystery",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Mystery",
        summary="",
    )
    _source_coverage(conn, boss_id, "ancient-fuelweaver", "Ancient Fuelweaver", "boss")
    _gap(
        conn,
        boss_id,
        "ancient-fuelweaver",
        "Ancient Fuelweaver",
        "boss",
        "official_mentions",
        "verify_against_official_sources",
        priority=36,
    )
    _gap(
        conn,
        item_id,
        "mystery",
        "Mystery",
        "item",
        "variants",
        "expand_variant_evidence",
        priority=55,
    )

    result = rebuild_entity_official_verification_queue(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, kind, priority, best_source_key,
               best_page_url, suggested_sources_text, official_search_query,
               steam_news_query, klei_query, candidate_reason
        from entity_official_verification_queue
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Ancient Fuelweaver",
        "kind": "boss",
        "priority": 36,
        "best_source_key": "wiki.gg",
        "best_page_url": "https://dontstarve.wiki.gg/wiki/Ancient_Fuelweaver",
        "suggested_sources_text": "klei|steam",
        "official_search_query": (
            '"Ancient Fuelweaver" "Don\'t Starve" OR '
            '"Don\'t Starve Together" official'
        ),
        "steam_news_query": (
            '"Ancient Fuelweaver" "Don\'t Starve Together" Steam news'
        ),
        "klei_query": (
            '"Ancient Fuelweaver" site:klei.com OR '
            "site:forums.kleientertainment.com"
        ),
        "candidate_reason": "missing_official_mentions",
    }


def test_rebuild_entity_official_verification_queue_is_idempotent(tmp_path):
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
    _gap(
        conn,
        entity_id,
        "wilson",
        "Wilson",
        "character",
        "official_mentions",
        "verify_against_official_sources",
        priority=41,
    )

    first = rebuild_entity_official_verification_queue(conn)
    second = rebuild_entity_official_verification_queue(conn)

    assert first == second == 1
    row = conn.execute(
        "select canonical_title, priority from entity_official_verification_queue"
    ).fetchone()
    assert tuple(row) == ("Wilson", 41)


def _source_coverage(conn, entity_id, slug, title, kind):
    conn.execute(
        """
        insert into entity_source_coverage (
            entity_id, slug, canonical_title, kind, coverage_status,
            source_profile_count, matched_page_count, best_source_key,
            best_page_title, best_page_url
        )
        values (?, ?, ?, ?, 'both_sources', 2, 3, 'wiki.gg', ?,
                'https://dontstarve.wiki.gg/wiki/Ancient_Fuelweaver')
        """,
        (entity_id, slug, title, kind, title),
    )


def _gap(
    conn,
    entity_id,
    slug,
    title,
    kind,
    requirement,
    next_action,
    *,
    priority,
):
    conn.execute(
        """
        insert into entity_completeness_gap_queue (
            entity_id, slug, canonical_title, kind, missing_requirement,
            readiness_score, readiness_status, priority, next_action
        )
        values (?, ?, ?, ?, ?, 80, 'strong_profile', ?, ?)
        """,
        (entity_id, slug, title, kind, requirement, priority, next_action),
    )
