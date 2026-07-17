from dst_wiki_db.media_downloads import (
    download_pending_media,
    rebuild_entity_media_downloads,
)
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_media_downloads_prioritizes_primary_and_variant_assets(tmp_path):
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
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Bee",
        summary="",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, 'Bee', 'https://example.test/Bee', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_media_assets (
            entity_id, source_id, raw_page_id, asset_source, image_name,
            image_slug, role, original_url, description_url, local_path,
            width, height, mime, sha1, variant_key, variant_type,
            variant_label, is_variant, is_primary, confidence
        )
        values (?, ?, ?, 'infobox', 'Bee.png', 'bee-png',
                'image', 'https://img.test/Bee.png',
                'https://example.test/File:Bee.png',
                null, 64, 64, 'image/png', 'abc', '', '', '',
                0, 1, 1.0)
        """,
        (entity_id, source_id, raw_page_id),
    )
    conn.execute(
        """
        insert into entity_media_assets (
            entity_id, source_id, raw_page_id, asset_source, image_name,
            image_slug, role, original_url, description_url, local_path,
            width, height, mime, sha1, variant_key, variant_type,
            variant_label, is_variant, is_primary, confidence
        )
        values (?, ?, ?, 'page_reference', 'Bee Build.png', 'bee-build-png',
                'page_reference', null, 'https://example.test/File:Bee_Build.png',
                null, null, null, null, null, 'build', 'build_state',
                'Build', 1, 0, 0.7)
        """,
        (entity_id, source_id, raw_page_id),
    )

    result = rebuild_entity_media_downloads(conn)

    assert result == 2
    rows = conn.execute(
        """
        select
            source_key,
            slug,
            image_name,
            download_url,
            file_page_url,
            url_status,
            target_path,
            download_status,
            priority,
            queue_reason,
            is_primary,
            is_variant,
            variant_key
        from entity_media_downloads
        order by priority, id
        """
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "source_key": "fandom",
            "slug": "bee",
            "image_name": "Bee.png",
            "download_url": "https://img.test/Bee.png",
            "file_page_url": "https://example.test/File:Bee.png",
            "url_status": "direct_url",
            "target_path": "data/images/fandom/bee/bee-png",
            "download_status": "pending",
            "priority": 10,
            "queue_reason": "primary|direct_url",
            "is_primary": 1,
            "is_variant": 0,
            "variant_key": "",
        },
        {
            "source_key": "fandom",
            "slug": "bee",
            "image_name": "Bee Build.png",
            "download_url": None,
            "file_page_url": "https://example.test/File:Bee_Build.png",
            "url_status": "file_page_only",
            "target_path": "data/images/fandom/bee/bee-build-png",
            "download_status": "pending",
            "priority": 35,
            "queue_reason": "variant|file_page_only",
            "is_primary": 0,
            "is_variant": 1,
            "variant_key": "build",
        },
    ]


def test_rebuild_entity_media_downloads_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_entity_media_downloads(conn)
    second = rebuild_entity_media_downloads(conn)

    assert first == second == 0


def test_download_pending_media_writes_files_and_updates_status(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _seed_pending_direct_download(conn)
    session = FakeSession({b"image-bytes"})

    result = download_pending_media(
        conn,
        output_root=tmp_path,
        limit=1,
        session=session,
        timeout=5,
    )

    assert result == {
        "attempted": 1,
        "downloaded": 1,
        "failed": 0,
        "skipped": 0,
        "dry_run": False,
    }
    target = tmp_path / "data/images/fandom/bee/bee-png"
    assert target.read_bytes() == b"image-bytes"
    row = conn.execute(
        """
        select download_status, local_path, content_length, error_text
        from entity_media_downloads
        """
    ).fetchone()
    assert dict(row) == {
        "download_status": "downloaded",
        "local_path": str(target),
        "content_length": 11,
        "error_text": "",
    }


def test_download_pending_media_dry_run_does_not_write_or_update(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _seed_pending_direct_download(conn)
    session = FakeSession({b"image-bytes"})

    result = download_pending_media(
        conn,
        output_root=tmp_path,
        limit=1,
        session=session,
        dry_run=True,
    )

    assert result == {
        "attempted": 1,
        "downloaded": 0,
        "failed": 0,
        "skipped": 1,
        "dry_run": True,
    }
    assert not (tmp_path / "data/images/fandom/bee/bee-png").exists()
    row = conn.execute(
        "select download_status, local_path from entity_media_downloads"
    ).fetchone()
    assert tuple(row) == ("pending", None)


def _seed_pending_direct_download(conn):
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
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Bee",
        summary="",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, 'Bee', 'https://example.test/Bee', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    cursor = conn.execute(
        """
        insert into entity_media_assets (
            entity_id, source_id, raw_page_id, asset_source, image_name,
            image_slug, role, original_url, description_url, local_path,
            width, height, mime, sha1, variant_key, variant_type,
            variant_label, is_variant, is_primary, confidence
        )
        values (?, ?, ?, 'infobox', 'Bee.png', 'bee-png',
                'image', 'https://img.test/Bee.png',
                'https://example.test/File:Bee.png',
                null, 64, 64, 'image/png', 'abc', '', '', '',
                0, 1, 1.0)
        """,
        (entity_id, source_id, raw_page_id),
    )
    media_asset_id = cursor.lastrowid
    conn.execute(
        """
        insert into entity_media_downloads (
            entity_media_asset_id, entity_id, source_id, source_key, slug,
            canonical_title, kind, image_name, image_slug, role,
            asset_source, download_url, file_page_url, url_status,
            target_path, download_status, priority, queue_reason,
            is_primary, is_variant, confidence
        )
        values (?, ?, ?, 'fandom', 'bee', 'Bee', 'mob', 'Bee.png',
                'bee-png', 'image', 'infobox', 'https://img.test/Bee.png',
                'https://example.test/File:Bee.png', 'direct_url',
                'data/images/fandom/bee/bee-png', 'pending', 10,
                'primary|direct_url', 1, 0, 1.0)
        """,
        (media_asset_id, entity_id, source_id),
    )
    return media_asset_id


class FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requested_urls = []

    def get(self, url, timeout):
        self.requested_urls.append((url, timeout))
        return FakeResponse(self.payloads.pop(0))


class FakeResponse:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        return None
