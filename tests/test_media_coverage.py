import json

from dst_wiki_db.media_coverage import rebuild_entity_media_coverage
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_media_coverage_summarizes_all_entities(tmp_path):
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
    berry_id = upsert_entity(
        conn,
        canonical_title="Berry Bush",
        kind="plant",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Berry_Bush",
        summary="",
    )
    mystery_id = upsert_entity(
        conn,
        canonical_title="Mystery",
        kind="boss",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Mystery",
        summary="",
    )
    conn.execute(
        """
        insert into entity_media_profiles (
            entity_id, slug, canonical_title, kind,
            media_count, primary_count, variant_count, direct_url_count,
            file_page_only_count, missing_url_count, pending_download_count,
            downloaded_count, failed_download_count, variant_type_count,
            variant_types_text, primary_image_name, primary_role,
            primary_asset_source, primary_download_url, primary_file_page_url,
            primary_assets_json, variant_assets_json, has_primary_image,
            has_direct_url, has_variants, has_downloaded_media
        )
        values (?, 'berry-bush', 'Berry Bush', 'plant',
                3, 1, 1, 1, 1, 1, 2, 0, 1, 1,
                'growth_stage', 'Berry Bush.png', 'image', 'infobox',
                'https://img.test/berry.png',
                'https://example.test/File:Berry_Bush.png',
                '[]', '[]', 1, 1, 1, 0)
        """,
        (berry_id,),
    )

    result = rebuild_entity_media_coverage(conn)

    assert result == {"entity_media_coverage": 2, "entity_media_gap_queue": 5}
    rows = {
        row["canonical_title"]: dict(row)
        for row in conn.execute(
            """
            select canonical_title, media_status, gap_reasons_json, priority,
                   media_count, primary_count, direct_url_count,
                   has_media_profile, has_primary_image, has_direct_url,
                   primary_image_name
            from entity_media_coverage
            order by canonical_title
            """
        )
    }
    assert rows["Berry Bush"] == {
        "canonical_title": "Berry Bush",
        "media_status": "partial_url_coverage",
        "gap_reasons_json": (
            '["file_page_resolution_pending", "missing_media_url", '
            '"failed_download", "pending_download"]'
        ),
        "priority": 35,
        "media_count": 3,
        "primary_count": 1,
        "direct_url_count": 1,
        "has_media_profile": 1,
        "has_primary_image": 1,
        "has_direct_url": 1,
        "primary_image_name": "Berry Bush.png",
    }
    assert rows["Mystery"]["media_status"] == "no_media"
    assert json.loads(rows["Mystery"]["gap_reasons_json"]) == ["missing_media"]
    assert rows["Mystery"]["priority"] == 5
    gaps = [
        tuple(row)
        for row in conn.execute(
            """
            select canonical_title, gap_reason, priority
            from entity_media_gap_queue
            order by priority, canonical_title, gap_reason
            """
        )
    ]
    assert gaps[0] == ("Mystery", "missing_media", 5)
    assert [gap[1] for gap in gaps[1:]] == [
        "file_page_resolution_pending",
        "missing_media_url",
        "failed_download",
        "pending_download",
    ]


def test_rebuild_entity_media_coverage_is_idempotent(tmp_path):
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
        insert into entity_media_profiles (
            entity_id, slug, canonical_title, kind,
            media_count, primary_count, direct_url_count,
            downloaded_count, primary_image_name, primary_assets_json,
            variant_assets_json, has_primary_image, has_direct_url,
            has_downloaded_media
        )
        values (?, 'wilson', 'Wilson', 'character',
                1, 1, 1, 1, 'Wilson.png', '[]', '[]', 1, 1, 1)
        """,
        (entity_id,),
    )

    first = rebuild_entity_media_coverage(conn)
    second = rebuild_entity_media_coverage(conn)

    assert first == second == {
        "entity_media_coverage": 1,
        "entity_media_gap_queue": 0,
    }
    row = conn.execute(
        "select media_status, gap_reasons_json from entity_media_coverage"
    ).fetchone()
    assert tuple(row) == ("downloaded_media", "[]")
