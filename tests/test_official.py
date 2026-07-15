import json

import requests

from dst_wiki_db.official import (
    OfficialRecord,
    fetch_steam_records,
    records_from_steam_appdetails,
    records_from_steam_news,
)
from dst_wiki_db.schema import connect, init_db, upsert_official_record


def test_schema_can_upsert_official_records(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    record = OfficialRecord(
        provider="steam",
        record_type="appdetails",
        external_id="322330",
        title="Don't Starve Together",
        url="https://store.steampowered.com/app/322330/",
        status="ok",
        summary="Standalone multiplayer expansion.",
        payload={"steam_appid": 322330},
    )

    record_id = upsert_official_record(conn, record)

    row = conn.execute(
        "select provider, record_type, external_id, title from official_records where id=?",
        (record_id,),
    ).fetchone()
    assert tuple(row) == ("steam", "appdetails", "322330", "Don't Starve Together")


def test_records_from_steam_appdetails_extracts_app_summary_and_dlc_ids():
    payload = {
        "322330": {
            "success": True,
            "data": {
                "name": "Don't Starve Together",
                "steam_appid": 322330,
                "short_description": "Fight, Farm, Build and Explore Together.",
                "dlc": [4211520, 1084430],
            },
        }
    }

    records = records_from_steam_appdetails(322330, payload)

    assert records[0].external_id == "322330"
    assert records[0].title == "Don't Starve Together"
    assert records[0].summary == "Fight, Farm, Build and Explore Together."
    assert records[1].record_type == "steam_dlc_id"
    assert records[1].external_id == "4211520"


def test_records_from_steam_news_extracts_news_items():
    payload = {
        "appnews": {
            "appid": 322330,
            "newsitems": [
                {
                    "gid": "1836506165576869",
                    "title": "Hotfix 740477",
                    "url": "https://example.test/news",
                    "contents": "Changes and bug fixes.",
                    "date": 1783378705,
                }
            ],
        }
    }

    records = records_from_steam_news(322330, payload)

    assert records == [
        OfficialRecord(
            provider="steam",
            record_type="news",
            external_id="1836506165576869",
            title="Hotfix 740477",
            url="https://example.test/news",
            status="ok",
            summary="Changes and bug fixes.",
            payload=payload["appnews"]["newsitems"][0],
        )
    ]


def test_fetch_steam_records_stores_failure_record_when_endpoint_times_out():
    class TimeoutSession:
        def get(self, url, params=None, timeout=None):
            raise requests.Timeout("slow endpoint")

    records = fetch_steam_records(
        appids=[219740],
        news_count=5,
        timeout=1,
        session=TimeoutSession(),
    )

    assert records[0].provider == "steam"
    assert records[0].record_type == "appdetails"
    assert records[0].external_id == "219740"
    assert records[0].status == "failed"
    assert "slow endpoint" in records[0].summary
