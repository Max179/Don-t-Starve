from dst_wiki_db.media_assets import rebuild_entity_media_assets
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_media_assets_unifies_infobox_page_and_variant_images(tmp_path):
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
    raw_page_id = conn.execute("select id from raw_pages").fetchone()[0]
    conn.execute(
        """
        insert into entity_images (
            entity_id, source_id, raw_page_id, image_name, role, original_url,
            description_url, width, height, mime, sha1, variant_key
        )
        values (?, ?, ?, 'Bee.png', 'image', 'https://cdn.test/Bee.png',
                'https://example.test/File:Bee.png', 64, 64, 'image/png',
                'abc123', '')
        """,
        (entity_id, source_id, raw_page_id),
    )
    entity_image_id = conn.execute("select id from entity_images").fetchone()[0]
    conn.execute(
        """
        insert into entity_images (
            entity_id, source_id, raw_page_id, image_name, role, original_url,
            description_url, variant_key
        )
        values (?, ?, ?, 'Bee DST.png', 'image', 'https://cdn.test/Bee_DST.png',
                'https://example.test/File:Bee_DST.png', 'dst')
        """,
        (entity_id, source_id, raw_page_id),
    )
    variant_entity_image_id = conn.execute(
        "select id from entity_images where image_name='Bee DST.png'"
    ).fetchone()[0]
    conn.execute(
        """
        insert into page_images (
            entity_id, source_id, raw_page_id, image_title, image_name,
            image_slug, role, description_url
        )
        values (?, ?, ?, 'File:Bee Frozen.png', 'Bee Frozen.png',
                'bee-frozen-png', 'page_reference',
                'https://example.test/File:Bee_Frozen.png')
        """,
        (entity_id, source_id, raw_page_id),
    )
    page_image_id = conn.execute("select id from page_images").fetchone()[0]
    conn.execute(
        """
        insert into image_variants (
            entity_id, source_id, raw_page_id, page_image_id, image_name,
            image_slug, variant_key, variant_type, label, match_method,
            confidence
        )
        values (?, ?, ?, ?, 'Bee Frozen.png', 'bee-frozen-png', 'frozen',
                'state', 'Frozen', 'entity_slug_filename_prefix', 0.85)
        """,
        (entity_id, source_id, raw_page_id, page_image_id),
    )

    result = rebuild_entity_media_assets(conn)

    assert result == 3
    rows = conn.execute(
        """
        select asset_source, entity_image_id, page_image_id, image_name,
               role, original_url, description_url, variant_key,
               variant_type, variant_label, is_variant, is_primary,
               confidence
        from entity_media_assets
        order by asset_source
        """
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        (
            "infobox",
            entity_image_id,
            None,
            "Bee.png",
            "image",
            "https://cdn.test/Bee.png",
            "https://example.test/File:Bee.png",
            "",
            "",
            "",
            0,
            1,
            1.0,
        ),
        (
            "infobox",
            variant_entity_image_id,
            None,
            "Bee DST.png",
            "image",
            "https://cdn.test/Bee_DST.png",
            "https://example.test/File:Bee_DST.png",
            "dst",
            "game_scope",
            "Don't Starve Together",
            1,
            1,
            1.0,
        ),
        (
            "page_reference",
            None,
            page_image_id,
            "Bee Frozen.png",
            "page_reference",
            None,
            "https://example.test/File:Bee_Frozen.png",
            "frozen",
            "state",
            "Frozen",
            1,
            0,
            0.85,
        ),
    ]


def test_rebuild_entity_media_assets_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_entity_media_assets(conn)
    second = rebuild_entity_media_assets(conn)

    assert first == second == 0


def test_rebuild_entity_media_assets_preserves_resolved_page_reference_metadata(tmp_path):
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
    raw_page_id = conn.execute("select id from raw_pages").fetchone()[0]
    conn.execute(
        """
        insert into page_images (
            entity_id, source_id, raw_page_id, image_title, image_name,
            image_slug, role, description_url
        )
        values (?, ?, ?, 'File:Bee Frozen.png', 'Bee Frozen.png',
                'bee-frozen-png', 'page_reference',
                'https://example.test/File:Bee_Frozen.png')
        """,
        (entity_id, source_id, raw_page_id),
    )

    rebuild_entity_media_assets(conn)
    conn.execute(
        """
        update entity_media_assets
        set original_url = 'https://img.test/Bee_Frozen.png',
            width = 128,
            height = 96,
            mime = 'image/png',
            sha1 = 'def'
        """
    )
    conn.execute(
        """
        update page_images
        set description_url = 'https://example.test/File:Bee_Frozen.png?stable=1'
        """
    )

    rebuild_entity_media_assets(conn)

    row = conn.execute(
        """
        select original_url, description_url, width, height, mime, sha1
        from entity_media_assets
        """
    ).fetchone()
    assert dict(row) == {
        "original_url": "https://img.test/Bee_Frozen.png",
        "description_url": "https://example.test/File:Bee_Frozen.png?stable=1",
        "width": 128,
        "height": 96,
        "mime": "image/png",
        "sha1": "def",
    }
