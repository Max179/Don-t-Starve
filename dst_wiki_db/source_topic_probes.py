from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import json
from typing import Iterable, Mapping
from urllib.parse import quote

import requests


USER_AGENT = "DontStarveWikiSourceProbe/0.1 (+https://github.com/Max179/Don-t-Starve)"


@dataclass(frozen=True)
class SourceTopicProbe:
    source_key: str
    probe_group: str
    probe_title: str
    entity_slug: str
    entity_title: str
    url: str
    expected_use: str


@dataclass(frozen=True)
class SourceTopicProbeResult:
    probe: SourceTopicProbe
    status: str
    status_code: int | None
    method: str
    final_url: str
    page_title: str
    summary: str
    payload: Mapping[str, object]


TOPIC_PROBES = (
    SourceTopicProbe(
        "wiki.gg",
        "core_entity",
        "Wilson",
        "wilson",
        "Wilson",
        "https://dontstarve.wiki.gg/wiki/Wilson",
        "canonical article coverage",
    ),
    SourceTopicProbe(
        "wiki.gg",
        "core_entity",
        "Crock Pot",
        "crock-pot",
        "Crock Pot",
        "https://dontstarve.wiki.gg/wiki/Crock_Pot",
        "canonical item/structure mechanics",
    ),
    SourceTopicProbe(
        "wiki.gg",
        "boss",
        "Ancient Fuelweaver",
        "ancient-fuelweaver",
        "Ancient Fuelweaver",
        "https://dontstarve.wiki.gg/wiki/Ancient_Fuelweaver",
        "canonical boss mechanics",
    ),
    SourceTopicProbe(
        "fandom",
        "core_entity",
        "Wilson",
        "wilson",
        "Wilson",
        "https://dontstarve.fandom.com/wiki/Wilson",
        "historical comparison article coverage",
    ),
    SourceTopicProbe(
        "fandom",
        "core_entity",
        "Crock Pot",
        "crock-pot",
        "Crock Pot",
        "https://dontstarve.fandom.com/wiki/Crock_Pot",
        "historical comparison item/structure mechanics",
    ),
    SourceTopicProbe(
        "fandom",
        "boss",
        "Ancient Fuelweaver",
        "ancient-fuelweaver",
        "Ancient Fuelweaver",
        "https://dontstarve.fandom.com/wiki/Ancient_Fuelweaver",
        "historical comparison boss mechanics",
    ),
    SourceTopicProbe(
        "fextralife",
        "core_entity",
        "Wilson",
        "wilson",
        "Wilson",
        "https://dontstarve.wiki.fextralife.com/Wilson",
        "competitor article coverage signal",
    ),
    SourceTopicProbe(
        "fextralife",
        "core_entity",
        "Crock Pot",
        "crock-pot",
        "Crock Pot",
        "https://dontstarve.wiki.fextralife.com/Crock+Pot",
        "competitor item/structure coverage signal",
    ),
    SourceTopicProbe(
        "fextralife",
        "boss",
        "Ancient Fuelweaver",
        "ancient-fuelweaver",
        "Ancient Fuelweaver",
        "https://dontstarve.wiki.fextralife.com/Ancient+Fuelweaver",
        "competitor boss coverage signal",
    ),
    SourceTopicProbe(
        "klei",
        "official_product",
        "Don't Starve Together",
        "dont-starve-together",
        "Don't Starve Together",
        "https://www.klei.com/games/dont-starve-together",
        "official product verification",
    ),
    SourceTopicProbe(
        "klei",
        "official_product",
        "Don't Starve Elsewhere",
        "dont-starve-elsewhere",
        "Don't Starve Elsewhere",
        "https://www.klei.com/games/dont-starve-elsewhere",
        "official product verification",
    ),
    SourceTopicProbe(
        "steam",
        "official_product",
        "Don't Starve Elsewhere",
        "dont-starve-elsewhere",
        "Don't Starve Elsewhere",
        "https://store.steampowered.com/app/2239770/Dont_Starve_Elsewhere/",
        "official store verification",
    ),
)


def probe_source_topics(
    conn,
    *,
    probes: Iterable[SourceTopicProbe] = TOPIC_PROBES,
    timeout: int = 20,
    session=None,
) -> dict[str, object]:
    session = session or _session()
    results = [
        _probe_one(probe, timeout=timeout, session=session)
        for probe in probes
    ]
    written = write_source_topic_probes(conn, results)
    return _summary(results, records_written=written)


def write_source_topic_probes(conn, results: Iterable[SourceTopicProbeResult]) -> int:
    catalog_ids = {
        row["source_key"]: int(row["id"])
        for row in conn.execute("select id, source_key from source_catalog").fetchall()
    }
    count = 0
    for result in results:
        probe = result.probe
        conn.execute(
            """
            insert into source_topic_probes (
                source_catalog_id, source_key, probe_group, probe_title,
                entity_slug, entity_title, url, expected_use, status,
                status_code, method, final_url, page_title, summary,
                payload_json, checked_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            on conflict(source_key, probe_group, probe_title, url) do update set
                source_catalog_id=excluded.source_catalog_id,
                entity_slug=excluded.entity_slug,
                entity_title=excluded.entity_title,
                expected_use=excluded.expected_use,
                status=excluded.status,
                status_code=excluded.status_code,
                method=excluded.method,
                final_url=excluded.final_url,
                page_title=excluded.page_title,
                summary=excluded.summary,
                payload_json=excluded.payload_json,
                checked_at=current_timestamp
            """,
            (
                catalog_ids.get(probe.source_key),
                probe.source_key,
                probe.probe_group,
                probe.probe_title,
                probe.entity_slug,
                probe.entity_title,
                probe.url,
                probe.expected_use,
                result.status,
                result.status_code,
                result.method,
                result.final_url,
                result.page_title,
                result.summary,
                json.dumps(result.payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        count += 1
    conn.commit()
    return count


def relink_source_topic_probes(conn) -> int:
    conn.execute(
        """
        update source_topic_probes
        set source_catalog_id = (
            select source_catalog.id
            from source_catalog
            where source_catalog.source_key = source_topic_probes.source_key
        )
        """
    )
    conn.commit()
    row = conn.execute("select count(*) as count from source_topic_probes").fetchone()
    return int(row["count"])


def _probe_one(probe: SourceTopicProbe, *, timeout: int, session) -> SourceTopicProbeResult:
    try:
        response = _get_probe(session, probe.url, timeout)
        status_code = int(response.status_code)
        ok = 200 <= status_code < 400
        text = getattr(response, "text", "") or ""
        page_title = _html_title(text) if text else ""
        final_url = str(getattr(response, "url", probe.url) or probe.url)
        return SourceTopicProbeResult(
            probe=probe,
            status="ok" if ok else "failed",
            status_code=status_code,
            method="GET",
            final_url=final_url,
            page_title=page_title,
            summary=f"HTTP {status_code}" + (f"; {page_title}" if page_title else ""),
            payload={
                "content_type": _header(response, "content-type"),
                "content_length": _header(response, "content-length"),
                "url_slug": quote(probe.probe_title.replace(" ", "_"), safe="_'"),
            },
        )
    except requests.RequestException as exc:
        return SourceTopicProbeResult(
            probe=probe,
            status="failed",
            status_code=None,
            method="GET",
            final_url="",
            page_title="",
            summary=str(exc),
            payload={"error": str(exc)},
        )


def _get_probe(session, url: str, timeout: int):
    return session.get(url, timeout=timeout)


def _summary(results: Iterable[SourceTopicProbeResult], *, records_written: int) -> dict[str, object]:
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_group: dict[str, int] = {}
    total = 0
    records = []
    for result in results:
        probe = result.probe
        total += 1
        by_source[probe.source_key] = by_source.get(probe.source_key, 0) + 1
        by_status[result.status] = by_status.get(result.status, 0) + 1
        by_group[probe.probe_group] = by_group.get(probe.probe_group, 0) + 1
        records.append(
            {
                "source_key": probe.source_key,
                "probe_group": probe.probe_group,
                "probe_title": probe.probe_title,
                "entity_slug": probe.entity_slug,
                "url": probe.url,
                "expected_use": probe.expected_use,
                "status": result.status,
                "status_code": result.status_code,
                "final_url": result.final_url,
                "page_title": result.page_title,
                "summary": result.summary,
            }
        )
    return {
        "records_written": records_written,
        "records_seen": total,
        "by_source": by_source,
        "by_status": by_status,
        "by_group": by_group,
        "records": records,
    }


def _header(response, key: str) -> str:
    headers = getattr(response, "headers", {}) or {}
    return str(headers.get(key, headers.get(key.title(), "")) or "")


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.parts.append(data)


def _html_title(html: str) -> str:
    parser = _TitleParser()
    parser.feed(html or "")
    return " ".join(part.strip() for part in parser.parts if part.strip())


def _session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session
