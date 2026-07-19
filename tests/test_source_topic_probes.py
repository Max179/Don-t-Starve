from dst_wiki_db.schema import connect, init_db, upsert_source
from dst_wiki_db.source_catalog import rebuild_source_catalog
from dst_wiki_db.source_topic_probes import (
    SourceTopicProbe,
    probe_source_topics,
    relink_source_topic_probes,
)


class FakeResponse:
    def __init__(self, *, status_code=200, text="", url="https://example.test/"):
        self.status_code = status_code
        self.text = text
        self.url = url
        self.headers = {"content-type": "text/html"}


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        response = self.responses.pop(0)
        response.url = url
        return response


def test_probe_source_topics_writes_representative_coverage_rows(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    rebuild_source_catalog(conn)
    catalog_id = conn.execute(
        "select id from source_catalog where source_key='wiki.gg'"
    ).fetchone()["id"]
    probes = [
        SourceTopicProbe(
            source_key="wiki.gg",
            probe_group="core_entity",
            probe_title="Wilson",
            entity_slug="wilson",
            entity_title="Wilson",
            url="https://dontstarve.wiki.gg/wiki/Wilson",
            expected_use="canonical article coverage",
        )
    ]

    result = probe_source_topics(
        conn,
        probes=probes,
        session=FakeSession(
            [
                FakeResponse(
                    text="<html><head><title>Wilson - Don't Starve Wiki</title></head></html>"
                )
            ]
        ),
    )

    assert result["records_written"] == 1
    assert result["by_source"] == {"wiki.gg": 1}
    assert result["by_status"] == {"ok": 1}
    row = conn.execute(
        """
        select source_catalog_id, source_key, probe_group, probe_title,
               entity_slug, status, status_code, method, page_title
        from source_topic_probes
        """
    ).fetchone()
    assert tuple(row) == (
        catalog_id,
        "wiki.gg",
        "core_entity",
        "Wilson",
        "wilson",
        "ok",
        200,
        "GET",
        "Wilson - Don't Starve Wiki",
    )


def test_probe_source_topics_upserts_failures_and_relinks_catalog(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    rebuild_source_catalog(conn)
    probes = [
        SourceTopicProbe(
            source_key="wiki.gg",
            probe_group="core_entity",
            probe_title="Wilson",
            entity_slug="wilson",
            entity_title="Wilson",
            url="https://dontstarve.wiki.gg/wiki/Wilson",
            expected_use="canonical article coverage",
        )
    ]

    probe_source_topics(
        conn,
        probes=probes,
        session=FakeSession([FakeResponse(status_code=404, text="Missing")]),
    )
    rebuild_source_catalog(conn)
    count = relink_source_topic_probes(conn)

    assert count == 1
    row = conn.execute(
        "select status, status_code, source_catalog_id from source_topic_probes"
    ).fetchone()
    assert row["status"] == "failed"
    assert row["status_code"] == 404
    assert row["source_catalog_id"] is not None
