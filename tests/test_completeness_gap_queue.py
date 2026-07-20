import json

from dst_wiki_db.completeness_gap_queue import rebuild_entity_completeness_gap_queue
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_completeness_gap_queue_expands_missing_requirements(tmp_path):
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
    _audit(
        conn,
        boss_id,
        "ancient-fuelweaver",
        "Ancient Fuelweaver",
        "boss",
        readiness_score=80,
        readiness_status="strong_profile",
        missing='["official_mentions","variants"]',
        next_actions=(
            '[{"action":"expand_variant_evidence","variant_count":0,'
            '"variant_media_count":0},'
            '{"action":"verify_against_official_sources",'
            '"official_mention_count":0}]'
        ),
    )
    _audit(
        conn,
        item_id,
        "mystery",
        "Mystery",
        "item",
        readiness_score=20,
        readiness_status="sparse_profile",
        missing='["core_source_pair","media"]',
        next_actions=(
            '[{"action":"fill_source_alignment","gap_count":1,'
            '"status":"wiki.gg_only"},'
            '{"action":"fill_media_evidence","gap_count":1,'
            '"status":"no_media"}]'
        ),
        source_coverage_status="wiki.gg_only",
        media_status="no_media",
        source_gap_count=1,
        media_gap_count=1,
    )

    result = rebuild_entity_completeness_gap_queue(conn)

    assert result == 4
    rows = [
        dict(row)
        for row in conn.execute(
            """
            select canonical_title, missing_requirement, next_action,
                   readiness_score, priority, detail_json
            from entity_completeness_gap_queue
            order by priority, canonical_title, missing_requirement
            """
        )
    ]
    assert rows[0]["canonical_title"] == "Ancient Fuelweaver"
    assert rows[0]["missing_requirement"] == "variants"
    assert rows[0]["next_action"] == "expand_variant_evidence"
    assert rows[0]["priority"] == 27
    assert rows[1]["canonical_title"] == "Mystery"
    assert rows[1]["missing_requirement"] == "core_source_pair"
    assert rows[1]["priority"] == 33
    assert rows[2]["missing_requirement"] == "official_mentions"
    assert rows[2]["priority"] == 37
    detail = json.loads(rows[1]["detail_json"])
    assert detail["source"] == {"gap_count": 1, "status": "wiki.gg_only"}
    assert detail["action_detail"]["action"] == "fill_source_alignment"


def test_rebuild_entity_completeness_gap_queue_is_idempotent(tmp_path):
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
    _audit(
        conn,
        entity_id,
        "wilson",
        "Wilson",
        "character",
        readiness_score=90,
        readiness_status="strong_profile",
        missing='["official_mentions"]',
        next_actions=(
            '[{"action":"verify_against_official_sources",'
            '"official_mention_count":0}]'
        ),
    )

    first = rebuild_entity_completeness_gap_queue(conn)
    second = rebuild_entity_completeness_gap_queue(conn)

    assert first == second == 1
    row = conn.execute(
        """
        select missing_requirement, next_action
        from entity_completeness_gap_queue
        """
    ).fetchone()
    assert tuple(row) == ("official_mentions", "verify_against_official_sources")


def _audit(
    conn,
    entity_id,
    slug,
    title,
    kind,
    *,
    readiness_score,
    readiness_status,
    missing,
    next_actions,
    source_coverage_status="both_sources",
    media_status="download_pending",
    source_gap_count=0,
    media_gap_count=0,
):
    conn.execute(
        """
        insert into entity_completeness_audit (
            entity_id, slug, canonical_title, kind, readiness_score,
            readiness_status, source_coverage_status, media_status,
            source_gap_count, media_gap_count, missing_requirements_json,
            next_actions_json
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            entity_id,
            slug,
            title,
            kind,
            readiness_score,
            readiness_status,
            source_coverage_status,
            media_status,
            source_gap_count,
            media_gap_count,
            missing,
            next_actions,
        ),
    )
