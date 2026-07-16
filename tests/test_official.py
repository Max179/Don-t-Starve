import json

import requests

from scripts import fetch_official_sources
from dst_wiki_db.official import (
    OfficialRecord,
    fetch_steam_records,
    records_from_steam_dlc_appdetails,
    records_from_steam_appdetails,
    records_from_steam_news,
)
from dst_wiki_db.schema import connect, init_db, upsert_official_record


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class SequencedSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payloads.pop(0))


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


def test_records_from_steam_dlc_appdetails_preserves_parent_and_media():
    payload = {
        "4211520": {
            "success": True,
            "data": {
                "type": "dlc",
                "name": "Don't Starve Together: Starter Pack 2026",
                "steam_appid": 4211520,
                "short_description": "Starter pack.",
                "fullgame": {"appid": "322330", "name": "Don't Starve Together"},
                "header_image": "https://cdn.test/header.jpg",
            },
        }
    }

    record = records_from_steam_dlc_appdetails(4211520, 322330, payload)

    assert record == OfficialRecord(
        provider="steam",
        record_type="dlc_appdetails",
        external_id="4211520",
        title="Don't Starve Together: Starter Pack 2026",
        url="https://store.steampowered.com/app/4211520/",
        status="ok",
        summary="Starter pack.",
        payload={
            "parent_appid": 322330,
            "data": payload["4211520"]["data"],
        },
    )


def test_records_from_steam_dlc_appdetails_marks_unsuccessful_payload_as_failed():
    payload = {"4211520": {"success": False}}

    record = records_from_steam_dlc_appdetails(4211520, 322330, payload)

    assert record.provider == "steam"
    assert record.record_type == "dlc_appdetails"
    assert record.external_id == "4211520"
    assert record.status == "failed"
    assert record.payload["parent_appid"] == 322330
    assert record.payload["payload"] == payload["4211520"]


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


def test_fetch_steam_records_fetches_details_for_discovered_dlc():
    parent_appdetails_payload = {
        "322330": {
            "success": True,
            "data": {
                "name": "Don't Starve Together",
                "steam_appid": 322330,
                "short_description": "Fight, Farm, Build and Explore Together.",
                "dlc": [4211520],
            },
        }
    }
    parent_news_payload = {
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
    dlc_appdetails_payload = {
        "4211520": {
            "success": True,
            "data": {
                "type": "dlc",
                "name": "Don't Starve Together: Starter Pack 2026",
                "steam_appid": 4211520,
                "short_description": "Starter pack.",
            },
        }
    }
    session = SequencedSession(
        [parent_appdetails_payload, parent_news_payload, dlc_appdetails_payload]
    )

    records = fetch_steam_records(
        appids=[322330],
        news_count=1,
        timeout=5,
        session=session,
        include_dlc_details=True,
    )

    assert [record.record_type for record in records] == [
        "appdetails",
        "steam_dlc_id",
        "news",
        "dlc_appdetails",
    ]
    assert records[-1].title == "Don't Starve Together: Starter Pack 2026"
    assert session.calls[-1][1]["appids"] == "4211520"
    assert session.calls[-1][1]["filters"] == "basic"


def test_fetch_steam_records_can_skip_dlc_detail_requests():
    parent_appdetails_payload = {
        "322330": {
            "success": True,
            "data": {
                "name": "Don't Starve Together",
                "steam_appid": 322330,
                "short_description": "Fight, Farm, Build and Explore Together.",
                "dlc": [4211520],
            },
        }
    }
    parent_news_payload = {"appnews": {"appid": 322330, "newsitems": []}}
    session = SequencedSession([parent_appdetails_payload, parent_news_payload])

    records = fetch_steam_records(
        appids=[322330],
        news_count=1,
        timeout=5,
        session=session,
        include_dlc_details=False,
    )

    assert [record.record_type for record in records] == ["appdetails", "steam_dlc_id"]
    assert len(session.calls) == 2


def test_fetch_official_sources_cli_can_skip_dlc_details(tmp_path, monkeypatch):
    captured = {}

    def fake_fetch_steam_records(**kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setattr(
        fetch_official_sources,
        "fetch_steam_records",
        fake_fetch_steam_records,
    )
    monkeypatch.setattr(
        fetch_official_sources,
        "fetch_klei_records",
        lambda **kwargs: [],
    )

    result = fetch_official_sources.main(
        [
            "--db",
            str(tmp_path / "wiki.sqlite"),
            "--report",
            str(tmp_path / "official.json"),
            "--skip-steam-dlc-details",
        ]
    )

    assert result == 0
    assert captured["include_dlc_details"] is False


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
