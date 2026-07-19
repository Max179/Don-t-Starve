import json

from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.source_gap_queue import rebuild_entity_source_gap_queue


def test_rebuild_entity_source_gap_queue_expands_missing_sources(tmp_path):
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
    mystery_id = upsert_entity(
        conn,
        canonical_title="Mystery",
        kind="page",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Mystery",
        summary="",
    )
    conn.execute(
        """
        insert into entity_source_coverage (
            entity_id, slug, canonical_title, kind,
            source_profile_count, matched_page_count,
            wiki_gg_page_count, fandom_page_count, other_page_count,
            exact_page_count, game_variant_page_count, prefab_page_count,
            image_page_count, method_count,
            has_wiki_gg, has_fandom, has_both_core_wikis,
            has_exact_page, has_game_variant_pages, has_prefab_page,
            has_image_page, source_keys_json, missing_sources_json,
            coverage_status, best_source_key, best_page_title, best_page_url
        )
        values (?, 'ancient-fuelweaver', 'Ancient Fuelweaver', 'boss',
                1, 1, 1, 0, 0, 1, 0, 0, 0, 1,
                1, 0, 0, 1, 0, 0, 0,
                '["wiki.gg"]', '["fandom"]', 'wiki.gg_only',
                'wiki.gg', 'Ancient Fuelweaver',
                'https://dontstarve.wiki.gg/wiki/Ancient_Fuelweaver')
        """,
        (boss_id,),
    )
    conn.execute(
        """
        insert into entity_source_coverage (
            entity_id, slug, canonical_title, kind,
            source_keys_json, missing_sources_json, coverage_status
        )
        values (?, 'mystery', 'Mystery', 'page',
                '[]', '["wiki.gg","fandom"]', 'missing_source_profiles')
        """,
        (mystery_id,),
    )

    result = rebuild_entity_source_gap_queue(conn)

    assert result == 3
    rows = [
        dict(row)
        for row in conn.execute(
            """
            select canonical_title, missing_source_key, priority,
                   available_source_keys_json, best_available_source_key,
                   best_available_page_title
            from entity_source_gap_queue
            order by priority, canonical_title, missing_source_key
            """
        )
    ]
    assert rows[0] == {
        "canonical_title": "Ancient Fuelweaver",
        "missing_source_key": "fandom",
        "priority": 10,
        "available_source_keys_json": '["wiki.gg"]',
        "best_available_source_key": "wiki.gg",
        "best_available_page_title": "Ancient Fuelweaver",
    }
    assert [row["missing_source_key"] for row in rows[1:]] == ["wiki.gg", "fandom"]
    assert [row["priority"] for row in rows[1:]] == [80, 85]
    assert json.loads(rows[1]["available_source_keys_json"]) == []


def test_rebuild_entity_source_gap_queue_is_idempotent(tmp_path):
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
    conn.execute(
        """
        insert into entity_source_coverage (
            entity_id, slug, canonical_title, kind,
            source_profile_count, matched_page_count,
            fandom_page_count, exact_page_count, method_count,
            has_fandom, has_exact_page, source_keys_json,
            missing_sources_json, coverage_status, best_source_key,
            best_page_title, best_page_url
        )
        values (?, 'wilson', 'Wilson', 'character',
                1, 1, 1, 1, 1, 1, 1, '["fandom"]',
                '["wiki.gg"]', 'fandom_only', 'fandom', 'Wilson',
                'https://dontstarve.fandom.com/wiki/Wilson')
        """,
        (entity_id,),
    )

    first = rebuild_entity_source_gap_queue(conn)
    second = rebuild_entity_source_gap_queue(conn)

    assert first == second == 1
    row = conn.execute(
        "select missing_source_key, priority from entity_source_gap_queue"
    ).fetchone()
    assert tuple(row) == ("wiki.gg", 10)
