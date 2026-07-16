from __future__ import annotations

from dataclasses import dataclass, field
import fnmatch
import json
from typing import Iterable, Mapping
from urllib.parse import urlparse

import requests


USER_AGENT = "DontStarveWikiDatabaseAudit/0.1 (+https://github.com/Max179/Don-t-Starve)"


@dataclass(frozen=True)
class RobotPolicy:
    allow: tuple[str, ...] = ()
    disallow: tuple[str, ...] = ()
    content_signals: Mapping[str, str] = field(default_factory=dict)

    def is_allowed(self, path: str) -> bool:
        matches: list[tuple[int, str]] = []
        for rule in self.allow:
            if _robot_rule_matches(rule, path):
                matches.append((_rule_specificity(rule), "allow"))
        for rule in self.disallow:
            if _robot_rule_matches(rule, path):
                matches.append((_rule_specificity(rule), "disallow"))
        if not matches:
            return True
        matches.sort(key=lambda item: item[0], reverse=True)
        return matches[0][1] == "allow"


@dataclass(frozen=True)
class SourceAuditRecord:
    source_key: str
    check_type: str
    url: str
    status: str
    status_code: int | None
    allowed: bool | None
    title: str
    summary: str | None
    payload: Mapping[str, object]


def parse_robot_policy(text: str) -> RobotPolicy:
    allow: list[str] = []
    disallow: list[str] = []
    content_signals: dict[str, str] = {}
    active_for_star = False

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            active_for_star = value == "*"
            continue
        if not active_for_star:
            continue
        if key == "allow" and value:
            allow.append(value)
        elif key == "disallow" and value:
            disallow.append(value)
        elif key == "content-signal":
            content_signals.update(_parse_content_signals(value))

    return RobotPolicy(
        allow=tuple(allow),
        disallow=tuple(disallow),
        content_signals=content_signals,
    )


def audit_mediawiki_source(source, *, session=None, timeout: int = 30) -> list[SourceAuditRecord]:
    session = session or _session()
    records: list[SourceAuditRecord] = []
    robots_url = source.base_url.rstrip("/") + "/robots.txt"
    policy = RobotPolicy()

    try:
        response = session.get(robots_url, timeout=timeout)
        policy = parse_robot_policy(response.text)
        robots_ok = 200 <= response.status_code < 400
        records.append(
            SourceAuditRecord(
                source_key=source.key,
                check_type="robots_txt",
                url=robots_url,
                status="ok" if robots_ok else "failed",
                status_code=response.status_code,
                allowed=robots_ok,
                title="robots.txt",
                summary=_robots_summary(policy) if robots_ok else f"HTTP {response.status_code}",
                payload={
                    "allow": list(policy.allow),
                    "disallow": list(policy.disallow),
                    "content_signals": dict(policy.content_signals),
                },
            )
        )
    except requests.RequestException as exc:
        records.append(
            SourceAuditRecord(
                source_key=source.key,
                check_type="robots_txt",
                url=robots_url,
                status="failed",
                status_code=None,
                allowed=None,
                title="robots.txt",
                summary=str(exc),
                payload={"error": str(exc)},
            )
        )

    api_allowed = policy.is_allowed(_url_path(source.api_url))
    if not api_allowed or getattr(source, "api_restricted_by_robots", False):
        records.append(
            SourceAuditRecord(
                source_key=source.key,
                check_type="mediawiki_siteinfo",
                url=source.api_url,
                status="restricted_by_robots",
                status_code=None,
                allowed=False,
                title="MediaWiki siteinfo",
                summary="API access is marked restricted by robots/source policy; siteinfo fetch skipped.",
                payload={
                    "api_path": _url_path(source.api_url),
                    "source_flag_api_restricted_by_robots": bool(
                        getattr(source, "api_restricted_by_robots", False)
                    ),
                    "robots_disallow": list(policy.disallow),
                    "content_signals": dict(policy.content_signals),
                },
            )
        )
        return records

    try:
        response = session.get(
            source.api_url,
            params={
                "action": "query",
                "meta": "siteinfo",
                "siprop": "general|statistics",
                "format": "json",
            },
            timeout=timeout,
        )
        payload = response.json()
        query = payload.get("query", {}) if isinstance(payload, Mapping) else {}
        general = query.get("general", {}) if isinstance(query, Mapping) else {}
        statistics = query.get("statistics", {}) if isinstance(query, Mapping) else {}
        stable_payload = _stable_siteinfo_payload(general, statistics)
        records.append(
            SourceAuditRecord(
                source_key=source.key,
                check_type="mediawiki_siteinfo",
                url=source.api_url,
                status="ok" if 200 <= response.status_code < 400 else "failed",
                status_code=response.status_code,
                allowed=True,
                title="MediaWiki siteinfo",
                summary=_siteinfo_summary(
                    stable_payload["general"],
                    stable_payload["statistics"],
                ),
                payload=stable_payload,
            )
        )
    except (requests.RequestException, ValueError) as exc:
        records.append(
            SourceAuditRecord(
                source_key=source.key,
                check_type="mediawiki_siteinfo",
                url=source.api_url,
                status="failed",
                status_code=None,
                allowed=True,
                title="MediaWiki siteinfo",
                summary=str(exc),
                payload={"error": str(exc)},
            )
        )
    return records


def audit_http_endpoint(
    *,
    source_key: str,
    check_type: str,
    url: str,
    title: str,
    session=None,
    timeout: int = 30,
) -> SourceAuditRecord:
    session = session or _session()
    try:
        response, method = _status_probe(session, url, timeout)
        ok = 200 <= response.status_code < 400
        return SourceAuditRecord(
            source_key=source_key,
            check_type=check_type,
            url=url,
            status="ok" if ok else "failed",
            status_code=response.status_code,
            allowed=True,
            title=title,
            summary=f"HTTP {response.status_code}",
            payload={
                "method": method,
                "final_url": response.url,
                "headers": _selected_headers(getattr(response, "headers", {})),
            },
        )
    except requests.RequestException as exc:
        return SourceAuditRecord(
            source_key=source_key,
            check_type=check_type,
            url=url,
            status="failed",
            status_code=None,
            allowed=True,
            title=title,
            summary=str(exc),
            payload={"error": str(exc)},
        )


def write_source_audits(conn, records: Iterable[SourceAuditRecord]) -> int:
    count = 0
    for record in records:
        row = conn.execute("select id from sources where key=?", (record.source_key,)).fetchone()
        source_id = int(row["id"]) if row is not None else None
        conn.execute(
            """
            insert into source_audits (
                source_id, source_key, check_type, url, status, status_code,
                allowed, title, summary, payload_json, checked_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            on conflict(source_key, check_type, url) do update set
                source_id=excluded.source_id,
                status=excluded.status,
                status_code=excluded.status_code,
                allowed=excluded.allowed,
                title=excluded.title,
                summary=excluded.summary,
                payload_json=excluded.payload_json,
                checked_at=current_timestamp
            """,
            (
                source_id,
                record.source_key,
                record.check_type,
                record.url,
                record.status,
                record.status_code,
                None if record.allowed is None else int(record.allowed),
                record.title,
                record.summary,
                json.dumps(record.payload, ensure_ascii=False, sort_keys=True),
            ),
        )
        count += 1
    conn.commit()
    return count


def summarize_source_audits(records: Iterable[SourceAuditRecord]) -> dict[str, object]:
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    by_type: dict[str, int] = {}
    total = 0
    for record in records:
        total += 1
        by_source[record.source_key] = by_source.get(record.source_key, 0) + 1
        by_status[record.status] = by_status.get(record.status, 0) + 1
        by_type[record.check_type] = by_type.get(record.check_type, 0) + 1
    return {
        "records_written": total,
        "by_source": by_source,
        "by_status": by_status,
        "by_type": by_type,
    }


def _parse_content_signals(value: str) -> dict[str, str]:
    signals: dict[str, str] = {}
    for part in value.split(","):
        if "=" not in part:
            continue
        key, signal_value = part.split("=", 1)
        signals[key.strip()] = signal_value.strip()
    return signals


def _robot_rule_matches(rule: str, path: str) -> bool:
    if not rule:
        return False
    if "*" in rule or "$" in rule:
        pattern = rule.rstrip("$")
        if "$" in rule:
            return fnmatch.fnmatch(path, pattern)
        return fnmatch.fnmatch(path, pattern + "*")
    return path.startswith(rule)


def _rule_specificity(rule: str) -> int:
    return len(rule.replace("*", "").replace("$", ""))


def _url_path(url: str) -> str:
    parsed = urlparse(url)
    return parsed.path or "/"


def _robots_summary(policy: RobotPolicy) -> str:
    signals = ", ".join(f"{key}={value}" for key, value in sorted(policy.content_signals.items()))
    suffix = f"; content signals: {signals}" if signals else ""
    return f"{len(policy.allow)} allow rules, {len(policy.disallow)} disallow rules{suffix}"


def _siteinfo_summary(general: object, statistics: object) -> str | None:
    if not isinstance(general, Mapping) or not isinstance(statistics, Mapping):
        return None
    site_name = general.get("sitename") or "MediaWiki"
    articles = statistics.get("articles")
    images = statistics.get("images")
    if articles is None and images is None:
        return str(site_name)
    return f"{site_name}: {articles} articles, {images} images"


def _stable_siteinfo_payload(general: object, statistics: object) -> dict[str, dict[str, object]]:
    general_fields = (
        "sitename",
        "base",
        "generator",
        "lang",
        "articlepath",
        "server",
        "wikiid",
        "rights",
        "rightsurl",
    )
    statistic_fields = ("pages", "articles", "edits", "images", "activeusers")
    general_map = general if isinstance(general, Mapping) else {}
    statistics_map = statistics if isinstance(statistics, Mapping) else {}
    return {
        "general": {
            field: general_map[field]
            for field in general_fields
            if field in general_map and general_map[field] is not None
        },
        "statistics": {field: statistics_map.get(field) for field in statistic_fields},
    }


def _status_probe(session, url: str, timeout: int):
    if hasattr(session, "head"):
        response = session.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code not in (405, 501):
            return response, "HEAD"
    return _streaming_get_probe(session, url, timeout), "GET"


def _streaming_get_probe(session, url: str, timeout: int):
    try:
        response = session.get(
            url,
            timeout=timeout,
            stream=True,
            headers={"Range": "bytes=0-0"},
        )
    except TypeError:
        response = session.get(url, timeout=timeout)
    close = getattr(response, "close", None)
    if callable(close):
        close()
    return response


def _selected_headers(headers: Mapping[str, object]) -> dict[str, str]:
    selected = {}
    wanted = {"content-type"}
    for key, value in headers.items():
        lowered = str(key).lower()
        if lowered in wanted:
            selected[lowered] = str(value)
    return dict(sorted(selected.items()))


def _session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session
