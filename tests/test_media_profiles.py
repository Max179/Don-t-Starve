import json

from dst_wiki_db.media_profiles import rebuild_entity_media_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_media_profiles_summarizes_primary_and_variant_assets(tmp_path):
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
        canonical_title="Berry Bush",
        kind="plant",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Berry_Bush",
        summary="",
    )
    primary_id = _asset(
        conn,
        entity_id,
        source_id,
        "Berry Bush.png",
        role="image",
        original_url="https://img.test/berry.png",
        description_url="https://example.test/File:Berry_Bush.png",
        width=64,
        height=64,
        is_primary=1,
    )
    variant_id = _asset(
        conn,
        entity_id,
        source_id,
        "Berry Bush Picked.png",
        role="page_reference",
        original_url=None,
        description_url="https://example.test/File:Berry_Bush_Picked.png",
        variant_key="picked",
        variant_type="growth_stage",
        variant_label="Picked",
        is_variant=1,
    )
    missing_id = _asset(
        conn,
        entity_id,
        source_id,
        "Berry Bush Missing.png",
        role="page_reference",
        original_url=None,
        description_url=None,
    )
    _download(
        conn,
        primary_id,
        entity_id,
        source_id,
        "Berry Bush.png",
        "direct_url",
        "downloaded",
        download_url="https://img.test/berry.png",
        local_path="data/images/fandom/berry-bush/berry-bush-png",
        content_length=123,
        is_primary=1,
    )
    _download(
        conn,
        variant_id,
        entity_id,
        source_id,
        "Berry Bush Picked.png",
        "file_page_only",
        "pending",
        file_page_url="https://example.test/File:Berry_Bush_Picked.png",
        variant_key="picked",
        variant_type="growth_stage",
        variant_label="Picked",
        is_variant=1,
    )
    _download(
        conn,
        missing_id,
        entity_id,
        source_id,
        "Berry Bush Missing.png",
        "missing_url",
        "failed",
    )

    result = rebuild_entity_media_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, media_count, primary_count, variant_count,
               direct_url_count, file_page_only_count, missing_url_count,
               pending_download_count, downloaded_count, failed_download_count,
               variant_type_count, variant_types_text, primary_image_name,
               primary_download_url, primary_local_path, primary_width,
               primary_height, has_primary_image, has_direct_url,
               has_variants, has_downloaded_media, primary_assets_json,
               variant_assets_json
        from entity_media_profiles
        """
    ).fetchone()
    assert row["canonical_title"] == "Berry Bush"
    assert row["media_count"] == 3
    assert row["primary_count"] == 1
    assert row["variant_count"] == 1
    assert row["direct_url_count"] == 1
    assert row["file_page_only_count"] == 1
    assert row["missing_url_count"] == 1
    assert row["pending_download_count"] == 1
    assert row["downloaded_count"] == 1
    assert row["failed_download_count"] == 1
    assert row["variant_type_count"] == 1
    assert row["variant_types_text"] == "growth_stage"
    assert row["primary_image_name"] == "Berry Bush.png"
    assert row["primary_download_url"] == "https://img.test/berry.png"
    assert row["primary_local_path"] == "data/images/fandom/berry-bush/berry-bush-png"
    assert row["primary_width"] == 64
    assert row["primary_height"] == 64
    assert row["has_primary_image"] == 1
    assert row["has_direct_url"] == 1
    assert row["has_variants"] == 1
    assert row["has_downloaded_media"] == 1
    primary_assets = json.loads(row["primary_assets_json"])
    variant_assets = json.loads(row["variant_assets_json"])
    assert primary_assets[0]["content_length"] == 123
    assert variant_assets[0]["variant_key"] == "picked"


def test_rebuild_entity_media_profiles_is_idempotent_without_media(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    assert rebuild_entity_media_profiles(conn) == 0
    assert rebuild_entity_media_profiles(conn) == 0


def test_rebuild_entity_media_profiles_caps_embedded_asset_summaries(tmp_path):
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
        canonical_title="Map",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Map",
        summary="",
    )
    for index in range(30):
        _asset(
            conn,
            entity_id,
            source_id,
            f"Map Variant {index:02d}.png",
            role="page_reference",
            original_url=f"https://img.test/map-{index:02d}.png",
            description_url=f"https://example.test/File:Map_Variant_{index:02d}.png",
            variant_key=f"variant-{index:02d}",
            variant_type="visual_variant",
            variant_label=f"Variant {index:02d}",
            is_variant=1,
        )

    rebuild_entity_media_profiles(conn)

    row = conn.execute(
        """
        select media_count, variant_count, variant_assets_json
        from entity_media_profiles
        """
    ).fetchone()
    assert row["media_count"] == 30
    assert row["variant_count"] == 30
    assert len(json.loads(row["variant_assets_json"])) == 25


def _asset(
    conn,
    entity_id,
    source_id,
    image_name,
    *,
    role,
    original_url,
    description_url,
    width=None,
    height=None,
    variant_key="",
    variant_type="",
    variant_label="",
    is_primary=0,
    is_variant=0,
):
    image_slug = image_name.lower().replace(" ", "-")
    conn.execute(
        """
        insert into entity_media_assets (
            entity_id, source_id, asset_source, image_name, image_slug,
            role, original_url, description_url, width, height, variant_key,
            variant_type, variant_label, is_primary, is_variant, confidence
        )
        values (?, ?, 'infobox', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0)
        """,
        (
            entity_id,
            source_id,
            image_name,
            image_slug,
            role,
            original_url,
            description_url,
            width,
            height,
            variant_key,
            variant_type,
            variant_label,
            is_primary,
            is_variant,
        ),
    )
    return conn.execute(
        "select id from entity_media_assets where image_name = ?",
        (image_name,),
    ).fetchone()["id"]


def _download(
    conn,
    asset_id,
    entity_id,
    source_id,
    image_name,
    url_status,
    download_status,
    *,
    download_url=None,
    file_page_url=None,
    local_path=None,
    content_length=None,
    variant_key="",
    variant_type="",
    variant_label="",
    is_primary=0,
    is_variant=0,
):
    image_slug = image_name.lower().replace(" ", "-")
    conn.execute(
        """
        insert into entity_media_downloads (
            entity_media_asset_id, entity_id, source_id, download_url,
            file_page_url, url_status, download_status, local_path,
            content_length, priority, queue_reason
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'test')
        """,
        (
            asset_id,
            entity_id,
            source_id,
            download_url,
            file_page_url,
            url_status,
            download_status,
            local_path,
            content_length,
        ),
    )
