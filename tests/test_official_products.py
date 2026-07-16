from dst_wiki_db.official import OfficialRecord
from dst_wiki_db.official_products import rebuild_official_products
from dst_wiki_db.schema import connect, init_db, upsert_official_record


def test_rebuild_official_products_extracts_product_facts_and_media(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    upsert_official_record(
        conn,
        OfficialRecord(
            provider="steam",
            record_type="dlc_appdetails",
            external_id="4211520",
            title="Don't Starve Together: Starter Pack 2026",
            url="https://store.steampowered.com/app/4211520/",
            status="ok",
            summary="Starter pack.",
            payload={
                "parent_appid": 322330,
                "data": {
                    "type": "dlc",
                    "name": "Don't Starve Together: Starter Pack 2026",
                    "steam_appid": 4211520,
                    "short_description": "Starter pack.",
                    "fullgame": {
                        "appid": "322330",
                        "name": "Don't Starve Together",
                    },
                    "required_age": 0,
                    "is_free": False,
                    "controller_support": "full",
                    "supported_languages": "English<strong>*</strong>",
                    "website": "http://www.dontstarvegame.com",
                    "header_image": "https://cdn.test/header.jpg",
                    "capsule_image": "https://cdn.test/capsule.jpg",
                    "detailed_description": (
                        '<img src="https://cdn.test/extra.avif" width=491 height=654>'
                    ),
                },
            },
        ),
    )

    result = rebuild_official_products(conn)

    assert result == {"official_products": 1, "official_product_media": 3}
    product = conn.execute(
        """
        select
            provider,
            record_type,
            external_id,
            product_type,
            title,
            parent_external_id,
            parent_title,
            short_description,
            is_free,
            required_age,
            controller_support,
            website
        from official_products
        """
    ).fetchone()
    assert dict(product) == {
        "provider": "steam",
        "record_type": "dlc_appdetails",
        "external_id": "4211520",
        "product_type": "dlc",
        "title": "Don't Starve Together: Starter Pack 2026",
        "parent_external_id": "322330",
        "parent_title": "Don't Starve Together",
        "short_description": "Starter pack.",
        "is_free": 0,
        "required_age": 0,
        "controller_support": "full",
        "website": "http://www.dontstarvegame.com",
    }
    media_rows = conn.execute(
        """
        select media_role, media_index, media_url, width, height
        from official_product_media
        order by media_role, media_index
        """
    ).fetchall()
    assert [dict(row) for row in media_rows] == [
        {
            "media_role": "capsule_image",
            "media_index": 0,
            "media_url": "https://cdn.test/capsule.jpg",
            "width": None,
            "height": None,
        },
        {
            "media_role": "description_image",
            "media_index": 0,
            "media_url": "https://cdn.test/extra.avif",
            "width": 491,
            "height": 654,
        },
        {
            "media_role": "header_image",
            "media_index": 0,
            "media_url": "https://cdn.test/header.jpg",
            "width": None,
            "height": None,
        },
    ]


def test_rebuild_official_products_ignores_news_and_failed_records(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    for record in [
        OfficialRecord(
            provider="steam",
            record_type="news",
            external_id="news-1",
            title="Update",
            url="https://example.test/news",
            status="ok",
            summary="News.",
            payload={"title": "Update"},
        ),
        OfficialRecord(
            provider="steam",
            record_type="dlc_appdetails",
            external_id="4211520",
            title="Steam DLC 4211520",
            url="https://store.steampowered.com/app/4211520/",
            status="failed",
            summary=None,
            payload={"error": "timeout"},
        ),
    ]:
        upsert_official_record(conn, record)

    result = rebuild_official_products(conn)

    assert result == {"official_products": 0, "official_product_media": 0}
    assert conn.execute("select count(*) from official_products").fetchone()[0] == 0
