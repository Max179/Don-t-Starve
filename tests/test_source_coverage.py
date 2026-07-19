import json

from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.source_coverage import rebuild_entity_source_coverage


def test_rebuild_entity_source_coverage_summarizes_core_wiki_sources(tmp_path):
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
    berry_id = upsert_entity(
        conn,
        canonical_title="Berry Bush",
        kind="plant",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Berry_Bush",
        summary="",
    )
    wilson_id = upsert_entity(
        conn,
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Wilson",
        summary="",
    )
    mystery_id = upsert_entity(
        conn,
        canonical_title="Mystery",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=3,
        canonical_url="https://example.test/Mystery",
        summary="",
    )
    _insert_source_profile(
        conn,
        berry_id,
        "wiki.gg",
        "berry-bush",
        "Berry Bush",
        "plant",
        matched=2,
        exact=1,
        game_variant=1,
        methods=2,
        primary_title="Berry Bush",
        primary_url="https://dontstarve.wiki.gg/wiki/Berry_Bush",
    )
    _insert_source_profile(
        conn,
        berry_id,
        "fandom",
        "berry-bush",
        "Berry Bush",
        "plant",
        matched=1,
        exact=1,
        methods=1,
        primary_title="Berry Bush",
        primary_url="https://dontstarve.fandom.com/wiki/Berry_Bush",
    )
    _insert_source_profile(
        conn,
        wilson_id,
        "wiki.gg",
        "wilson",
        "Wilson",
        "character",
        matched=1,
        exact=1,
        methods=1,
        primary_title="Wilson",
        primary_url="https://dontstarve.wiki.gg/wiki/Wilson",
    )

    result = rebuild_entity_source_coverage(conn)

    assert result == 3
    rows = {
        row["canonical_title"]: dict(row)
        for row in conn.execute(
            """
            select canonical_title, source_profile_count, matched_page_count,
                   wiki_gg_page_count, fandom_page_count, has_wiki_gg,
                   has_fandom, has_both_core_wikis, missing_sources_json,
                   coverage_status, best_source_key, best_page_title
            from entity_source_coverage
            order by canonical_title
            """
        )
    }
    assert rows["Berry Bush"] == {
        "canonical_title": "Berry Bush",
        "source_profile_count": 2,
        "matched_page_count": 3,
        "wiki_gg_page_count": 2,
        "fandom_page_count": 1,
        "has_wiki_gg": 1,
        "has_fandom": 1,
        "has_both_core_wikis": 1,
        "missing_sources_json": "[]",
        "coverage_status": "both_sources",
        "best_source_key": "wiki.gg",
        "best_page_title": "Berry Bush",
    }
    assert rows["Wilson"]["coverage_status"] == "wiki.gg_only"
    assert json.loads(rows["Wilson"]["missing_sources_json"]) == ["fandom"]
    assert rows["Mystery"]["coverage_status"] == "missing_source_profiles"
    assert json.loads(rows["Mystery"]["missing_sources_json"]) == [
        "wiki.gg",
        "fandom",
    ]


def test_rebuild_entity_source_coverage_is_idempotent(tmp_path):
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
        canonical_title="Crock Pot",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Crock_Pot",
        summary="",
    )
    _insert_source_profile(
        conn,
        entity_id,
        "fandom",
        "crock-pot",
        "Crock Pot",
        "item",
        matched=1,
        exact=1,
        methods=1,
        primary_title="Crock Pot",
        primary_url="https://dontstarve.fandom.com/wiki/Crock_Pot",
    )

    first = rebuild_entity_source_coverage(conn)
    second = rebuild_entity_source_coverage(conn)

    assert first == second == 1
    row = conn.execute(
        "select coverage_status from entity_source_coverage"
    ).fetchone()
    assert row["coverage_status"] == "fandom_only"


def _insert_source_profile(
    conn,
    entity_id,
    source_key,
    slug,
    title,
    kind,
    *,
    matched,
    exact,
    methods,
    primary_title,
    primary_url,
    game_variant=0,
):
    conn.execute(
        """
        insert into entity_source_profiles (
            entity_id, source_key, slug, canonical_title, kind,
            matched_page_count, exact_page_count, game_variant_page_count,
            prefab_page_count, image_page_count, method_count,
            match_methods_json, primary_page_title, primary_page_url,
            matched_pages_json, has_exact_page, has_game_variant_pages,
            has_prefab_page, has_image_page
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?,
                '[]', ?, ?, '[]', ?, ?, 0, 0)
        """,
        (
            entity_id,
            source_key,
            slug,
            title,
            kind,
            matched,
            exact,
            game_variant,
            methods,
            primary_title,
            primary_url,
            int(exact > 0),
            int(game_variant > 0),
        ),
    )
