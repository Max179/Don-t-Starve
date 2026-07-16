from dst_wiki_db.official import OfficialRecord
from dst_wiki_db.official_updates import rebuild_official_update_events
from dst_wiki_db.schema import (
    connect,
    init_db,
    upsert_entity,
    upsert_official_record,
    upsert_source,
)


def test_rebuild_official_update_events_extracts_event_and_media(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    record_id = upsert_official_record(
        conn,
        OfficialRecord(
            provider="steam",
            record_type="news",
            external_id="hotfix-1",
            title="Hotfix 740477",
            url="https://example.test/news",
            status="ok",
            summary="Changes and bug fixes.",
            payload={
                "appid": 322330,
                "author": "JesseB_Klei",
                "date": 1700000000,
                "contents": (
                    "Bug Fixes {STEAM_CLAN_IMAGE}/6835324/abc.png "
                    '<img src="https://cdn.test/extra.jpg" width="100" height="50"> '
                    "Wilson fixed."
                ),
            },
        ),
    )
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
        canonical_url="https://dontstarve.fandom.com/wiki/Wilson",
        summary="",
    )
    conn.execute(
        """
        insert into official_record_mentions (
            official_record_id, entity_id, provider, record_type, external_id,
            entity_title, mention_text, match_field, match_method,
            confidence, context_text
        )
        values (?, ?, 'steam', 'news', 'hotfix-1', 'Wilson', 'Wilson',
                'payload', 'canonical_title_phrase', 0.95, 'Wilson fixed.')
        """,
        (record_id, entity_id),
    )

    result = rebuild_official_update_events(conn)

    assert result == {"official_update_events": 1, "official_update_media": 2}
    event = conn.execute(
        """
        select
            provider,
            record_type,
            external_id,
            appid,
            title,
            url,
            author,
            published_at_unix,
            published_at_iso,
            event_type,
            content_text,
            content_length,
            mentioned_entity_count
        from official_update_events
        """
    ).fetchone()
    event_dict = dict(event)
    assert event_dict == {
        "provider": "steam",
        "record_type": "news",
        "external_id": "hotfix-1",
        "appid": 322330,
        "title": "Hotfix 740477",
        "url": "https://example.test/news",
        "author": "JesseB_Klei",
        "published_at_unix": 1700000000,
        "published_at_iso": "2023-11-14T22:13:20Z",
        "event_type": "hotfix",
        "content_text": "Bug Fixes Wilson fixed.",
        "content_length": 23,
        "mentioned_entity_count": 1,
    }
    media_rows = conn.execute(
        """
        select media_role, media_index, media_url, width, height, source_field
        from official_update_media
        order by media_role, media_index
        """
    ).fetchall()
    assert [dict(row) for row in media_rows] == [
        {
            "media_role": "html_image",
            "media_index": 0,
            "media_url": "https://cdn.test/extra.jpg",
            "width": 100,
            "height": 50,
            "source_field": "contents",
        },
        {
            "media_role": "steam_clan_image",
            "media_index": 0,
            "media_url": "https://clan.cloudflare.steamstatic.com/images/6835324/abc.png",
            "width": None,
            "height": None,
            "source_field": "contents",
        },
    ]


def test_rebuild_official_update_events_classifies_events_and_milestones(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    for external_id, title, author in [
        ("event-1", "Midsummer Cawnival is Back!", "Klei-JoeW"),
        ("milestone-1", "Don't Starve Together peaks at 122k players", "SteamDB"),
    ]:
        upsert_official_record(
            conn,
            OfficialRecord(
                provider="steam",
                record_type="news",
                external_id=external_id,
                title=title,
                url=f"https://example.test/{external_id}",
                status="ok",
                summary="",
                payload={
                    "appid": 322330,
                    "author": author,
                    "date": 1700000000,
                    "contents": title,
                },
            ),
        )

    result = rebuild_official_update_events(conn)

    assert result == {"official_update_events": 2, "official_update_media": 0}
    rows = conn.execute(
        """
        select external_id, event_type
        from official_update_events
        order by external_id
        """
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        ("event-1", "event"),
        ("milestone-1", "milestone"),
    ]


def test_rebuild_official_update_events_stops_steam_clan_images_at_extension(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    upsert_official_record(
        conn,
        OfficialRecord(
            provider="steam",
            record_type="news",
            external_id="image-boundary",
            title="Event Images",
            url="https://example.test/image-boundary",
            status="ok",
            summary="",
            payload={
                "appid": 322330,
                "author": "Klei-JoeW",
                "date": 1700000000,
                "contents": (
                    "{STEAM_CLAN_IMAGE}/6835324/ab86c0465b1ab14494e7f5f5baa18059fc74d611.pngThe "
                    "{STEAM_CLAN_IMAGE}/6835324/ed456a94d5028022d6a85a6b70bb2d4053f4c987..."
                ),
            },
        ),
    )

    result = rebuild_official_update_events(conn)

    assert result == {"official_update_events": 1, "official_update_media": 1}
    media_url = conn.execute(
        "select media_url from official_update_media"
    ).fetchone()[0]
    assert (
        media_url
        == "https://clan.cloudflare.steamstatic.com/images/6835324/ab86c0465b1ab14494e7f5f5baa18059fc74d611.png"
    )
    content_text = conn.execute(
        "select content_text from official_update_events"
    ).fetchone()[0]
    assert content_text == "The"


def test_rebuild_official_update_events_ignores_failed_and_non_news_records(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    for record in [
        OfficialRecord(
            provider="steam",
            record_type="news",
            external_id="failed-news",
            title="Failed News",
            url="https://example.test/failed",
            status="failed",
            summary=None,
            payload={"error": "timeout"},
        ),
        OfficialRecord(
            provider="steam",
            record_type="dlc_appdetails",
            external_id="4211520",
            title="Don't Starve Together: Starter Pack 2026",
            url="https://store.steampowered.com/app/4211520/",
            status="ok",
            summary="Starter pack.",
            payload={"data": {"name": "Starter Pack"}},
        ),
    ]:
        upsert_official_record(conn, record)

    result = rebuild_official_update_events(conn)

    assert result == {"official_update_events": 0, "official_update_media": 0}
    assert conn.execute("select count(*) from official_update_events").fetchone()[0] == 0
