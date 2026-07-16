import json

from dst_wiki_db.build import SourceDefinition
from dst_wiki_db.report import database_counts
from dst_wiki_db.schema import connect, init_db, upsert_source
from dst_wiki_db.source_audit import (
    SourceAuditRecord,
    audit_http_endpoint,
    audit_mediawiki_source,
    parse_robot_policy,
    summarize_source_audits,
    write_source_audits,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code=200,
        text="",
        payload=None,
        url="https://example.test/",
        headers=None,
    ):
        self.status_code = status_code
        self.text = text
        self._payload = payload
        self.url = url
        self.headers = headers or {}

    def json(self):
        return self._payload

    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, params=None, timeout=None):
        self.calls.append((url, params, timeout))
        response = self.responses.pop(0)
        response.url = url
        return response


class FakeHeadSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def head(self, url, timeout=None, allow_redirects=None):
        self.calls.append(("HEAD", url, timeout, allow_redirects))
        self.response.url = url
        return self.response


def test_parse_robot_policy_extracts_star_disallows_and_content_signals():
    policy = parse_robot_policy(
        """
        User-agent: *
        Content-Signal: search=yes,ai-train=no,use=reference
        Allow: /
        Disallow: /api.php
        Disallow: /wiki/File:

        User-agent: GPTBot
        Disallow: /
        """
    )

    assert "/api.php" in policy.disallow
    assert "/wiki/File:" in policy.disallow
    assert policy.content_signals == {
        "search": "yes",
        "ai-train": "no",
        "use": "reference",
    }
    assert policy.is_allowed("/wiki/Wilson")
    assert not policy.is_allowed("/api.php?action=query")


def test_audit_mediawiki_source_marks_restricted_api_without_fetching_siteinfo():
    source = SourceDefinition(
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
        license="CC BY-SA 4.0",
        api_restricted_by_robots=True,
    )
    session = FakeSession(
        [
            FakeResponse(
                text="""
                User-agent: *
                Allow: /
                Disallow: /api.php
                """
            )
        ]
    )

    records = audit_mediawiki_source(source, session=session, timeout=1)

    assert [record.check_type for record in records] == ["robots_txt", "mediawiki_siteinfo"]
    assert records[0].status == "ok"
    assert records[0].allowed is True
    assert records[1].status == "restricted_by_robots"
    assert records[1].allowed is False
    assert len(session.calls) == 1


def test_audit_mediawiki_source_reads_siteinfo_when_api_is_allowed():
    source = SourceDefinition(
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
        license="CC BY-SA / Fandom licensing",
    )
    session = FakeSession(
        [
            FakeResponse(text="User-agent: *\nAllow: /\n"),
            FakeResponse(
                payload={
                    "query": {
                        "general": {"sitename": "Don't Starve Wiki"},
                        "statistics": {"articles": 2252, "images": 25319},
                    }
                }
            ),
        ]
    )

    records = audit_mediawiki_source(source, session=session, timeout=1)
    siteinfo = records[1]

    assert siteinfo.status == "ok"
    assert siteinfo.allowed is True
    assert siteinfo.status_code == 200
    assert siteinfo.payload["statistics"]["articles"] == 2252
    assert siteinfo.summary == "Don't Starve Wiki: 2252 articles, 25319 images"
    assert len(session.calls) == 2


def test_audit_mediawiki_source_sanitizes_volatile_siteinfo_fields():
    source = SourceDefinition(
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
        license="CC BY-SA / Fandom licensing",
    )
    session = FakeSession(
        [
            FakeResponse(text="User-agent: *\nAllow: /\n"),
            FakeResponse(
                payload={
                    "query": {
                        "general": {
                            "sitename": "Don't Starve Wiki",
                            "base": "https://dontstarve.fandom.com/wiki/Don%27t_Starve_Wiki",
                            "time": "2026-07-16T03:40:20Z",
                            "phpversion": "8.3.32",
                        },
                        "statistics": {
                            "pages": 219384,
                            "articles": 2252,
                            "edits": 533981,
                            "images": 25319,
                            "jobs": 0,
                        },
                    }
                }
            ),
        ]
    )

    siteinfo = audit_mediawiki_source(source, session=session, timeout=1)[1]

    assert siteinfo.payload == {
        "general": {
            "base": "https://dontstarve.fandom.com/wiki/Don%27t_Starve_Wiki",
            "sitename": "Don't Starve Wiki",
        },
        "statistics": {
            "activeusers": None,
            "articles": 2252,
            "edits": 533981,
            "images": 25319,
            "pages": 219384,
        },
    }


def test_audit_http_endpoint_uses_head_without_storing_response_body():
    response = FakeResponse(
        status_code=200,
        text="large body that should not be stored",
        headers={"Content-Type": "application/json", "Content-Length": "999999"},
    )
    session = FakeHeadSession(response)

    record = audit_http_endpoint(
        source_key="steam",
        check_type="official_http_probe",
        url="https://store.steampowered.com/api/appdetails?appids=322330&filters=basic",
        title="Steam appdetails 322330",
        session=session,
        timeout=1,
    )

    assert record.status == "ok"
    assert record.summary == "HTTP 200"
    assert record.payload == {
        "method": "HEAD",
        "final_url": "https://store.steampowered.com/api/appdetails?appids=322330&filters=basic",
        "headers": {
            "content-type": "application/json",
        },
    }
    assert session.calls == [
        (
            "HEAD",
            "https://store.steampowered.com/api/appdetails?appids=322330&filters=basic",
            1,
            True,
        )
    ]


def test_write_source_audits_upserts_records(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    record = SourceAuditRecord(
        source_key="fandom",
        check_type="mediawiki_siteinfo",
        url="https://dontstarve.fandom.com/api.php",
        status="ok",
        status_code=200,
        allowed=True,
        title="MediaWiki siteinfo",
        summary="Don't Starve Wiki: 2252 articles, 25319 images",
        payload={"statistics": {"articles": 2252}},
    )

    assert write_source_audits(conn, [record]) == 1
    updated = SourceAuditRecord(
        source_key="fandom",
        check_type="mediawiki_siteinfo",
        url="https://dontstarve.fandom.com/api.php",
        status="failed",
        status_code=503,
        allowed=True,
        title="MediaWiki siteinfo",
        summary="temporary outage",
        payload={"error": "temporary outage"},
    )
    assert write_source_audits(conn, [updated]) == 1

    rows = conn.execute("select status, status_code, payload_json from source_audits").fetchall()
    assert len(rows) == 1
    assert tuple(rows[0][:2]) == ("failed", 503)
    assert json.loads(rows[0]["payload_json"]) == {"error": "temporary outage"}
    assert database_counts(conn)["source_audits"] == 1


def test_summarize_source_audits_groups_by_source_type_and_status():
    records = [
        SourceAuditRecord(
            source_key="wiki.gg",
            check_type="robots_txt",
            url="https://dontstarve.wiki.gg/robots.txt",
            status="ok",
            status_code=200,
            allowed=True,
            title="robots.txt",
            summary="1 allow rules, 1 disallow rules",
            payload={},
        ),
        SourceAuditRecord(
            source_key="wiki.gg",
            check_type="mediawiki_siteinfo",
            url="https://dontstarve.wiki.gg/api.php",
            status="restricted_by_robots",
            status_code=None,
            allowed=False,
            title="MediaWiki siteinfo",
            summary="skipped",
            payload={},
        ),
        SourceAuditRecord(
            source_key="steam",
            check_type="official_http_probe",
            url="https://store.steampowered.com/api/appdetails?appids=322330",
            status="ok",
            status_code=200,
            allowed=True,
            title="Steam appdetails 322330",
            summary="ok",
            payload={},
        ),
    ]

    summary = summarize_source_audits(records)

    assert summary["records_written"] == 3
    assert summary["by_source"] == {"wiki.gg": 2, "steam": 1}
    assert summary["by_status"] == {"ok": 2, "restricted_by_robots": 1}
    assert summary["by_type"] == {
        "robots_txt": 1,
        "mediawiki_siteinfo": 1,
        "official_http_probe": 1,
    }
