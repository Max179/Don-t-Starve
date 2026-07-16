from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import json
from typing import Iterable, List, Mapping, Sequence

import requests

from dst_wiki_db.schema import upsert_official_record


USER_AGENT = "CodexDSTOfficialVerifier/0.1 (local research database)"


@dataclass(frozen=True)
class OfficialRecord:
    provider: str
    record_type: str
    external_id: str
    title: str
    url: str | None
    status: str
    summary: str | None
    payload: Mapping[str, object]


def records_from_steam_appdetails(appid: int, payload: Mapping[str, object]) -> List[OfficialRecord]:
    app_payload = payload.get(str(appid), {})
    if not isinstance(app_payload, Mapping):
        return [
            OfficialRecord(
                provider="steam",
                record_type="appdetails",
                external_id=str(appid),
                title=f"Steam app {appid}",
                url=f"https://store.steampowered.com/app/{appid}/",
                status="invalid_payload",
                summary=None,
                payload={"payload": payload},
            )
        ]
    if not app_payload.get("success"):
        return [
            OfficialRecord(
                provider="steam",
                record_type="appdetails",
                external_id=str(appid),
                title=f"Steam app {appid}",
                url=f"https://store.steampowered.com/app/{appid}/",
                status="failed",
                summary=None,
                payload=app_payload,
            )
        ]

    data = app_payload.get("data", {})
    if not isinstance(data, Mapping):
        data = {}
    title = str(data.get("name") or f"Steam app {appid}")
    records = [
        OfficialRecord(
            provider="steam",
            record_type="appdetails",
            external_id=str(appid),
            title=title,
            url=f"https://store.steampowered.com/app/{appid}/",
            status="ok",
            summary=_optional_text(data.get("short_description")),
            payload=data,
        )
    ]
    for dlc_id in data.get("dlc") or []:
        records.append(
            OfficialRecord(
                provider="steam",
                record_type="steam_dlc_id",
                external_id=str(dlc_id),
                title=f"Steam DLC {dlc_id}",
                url=f"https://store.steampowered.com/app/{dlc_id}/",
                status="listed",
                summary=f"Listed as DLC for {title}.",
                payload={"parent_appid": appid, "dlc_appid": dlc_id},
            )
        )
    return records


def records_from_steam_dlc_appdetails(
    dlc_appid: int,
    parent_appid: int,
    payload: Mapping[str, object],
) -> OfficialRecord:
    app_payload = payload.get(str(dlc_appid), {})
    if not isinstance(app_payload, Mapping):
        return OfficialRecord(
            provider="steam",
            record_type="dlc_appdetails",
            external_id=str(dlc_appid),
            title=f"Steam DLC {dlc_appid}",
            url=f"https://store.steampowered.com/app/{dlc_appid}/",
            status="invalid_payload",
            summary=None,
            payload={"parent_appid": parent_appid, "payload": payload},
        )
    if not app_payload.get("success"):
        return OfficialRecord(
            provider="steam",
            record_type="dlc_appdetails",
            external_id=str(dlc_appid),
            title=f"Steam DLC {dlc_appid}",
            url=f"https://store.steampowered.com/app/{dlc_appid}/",
            status="failed",
            summary=None,
            payload={"parent_appid": parent_appid, "payload": app_payload},
        )

    data = app_payload.get("data", {})
    if not isinstance(data, Mapping):
        return OfficialRecord(
            provider="steam",
            record_type="dlc_appdetails",
            external_id=str(dlc_appid),
            title=f"Steam DLC {dlc_appid}",
            url=f"https://store.steampowered.com/app/{dlc_appid}/",
            status="invalid_payload",
            summary=None,
            payload={"parent_appid": parent_appid, "payload": app_payload},
        )

    title = str(data.get("name") or f"Steam DLC {dlc_appid}")
    return OfficialRecord(
        provider="steam",
        record_type="dlc_appdetails",
        external_id=str(dlc_appid),
        title=title,
        url=f"https://store.steampowered.com/app/{dlc_appid}/",
        status="ok",
        summary=_optional_text(data.get("short_description")),
        payload={"parent_appid": parent_appid, "data": data},
    )


def records_from_steam_news(appid: int, payload: Mapping[str, object]) -> List[OfficialRecord]:
    appnews = payload.get("appnews", {})
    if not isinstance(appnews, Mapping):
        return []
    records: List[OfficialRecord] = []
    for item in appnews.get("newsitems") or []:
        if not isinstance(item, Mapping):
            continue
        gid = str(item.get("gid") or "")
        if not gid:
            continue
        records.append(
            OfficialRecord(
                provider="steam",
                record_type="news",
                external_id=gid,
                title=str(item.get("title") or f"Steam news {gid}"),
                url=_optional_text(item.get("url")),
                status="ok",
                summary=_optional_text(item.get("contents")),
                payload=item,
            )
        )
    return records


def record_from_http_probe(
    *,
    provider: str,
    record_type: str,
    external_id: str,
    url: str,
    status_code: int | None,
    body: str,
    error: str | None = None,
) -> OfficialRecord:
    title = _html_title(body) or external_id
    status = "ok" if status_code and 200 <= status_code < 400 else "failed"
    return OfficialRecord(
        provider=provider,
        record_type=record_type,
        external_id=external_id,
        title=title,
        url=url,
        status=status,
        summary=_text_excerpt(body, 500) if status == "ok" else error,
        payload={
            "status_code": status_code,
            "error": error,
            "body_excerpt": _text_excerpt(body, 2000),
        },
    )


def fetch_steam_records(
    *,
    appids: Sequence[int],
    news_count: int,
    timeout: int,
    session=None,
    include_dlc_details: bool = True,
) -> List[OfficialRecord]:
    session = session or _session()
    records: List[OfficialRecord] = []
    dlc_pairs: List[tuple[int, int]] = []
    seen_dlc_pairs: set[tuple[int, int]] = set()
    for appid in appids:
        try:
            app_payload = _get_json(
                session,
                "https://store.steampowered.com/api/appdetails",
                {"appids": str(appid), "filters": "basic"},
                timeout,
            )
            app_records = records_from_steam_appdetails(appid, app_payload)
            records.extend(app_records)
            for record in app_records:
                if record.record_type != "steam_dlc_id" or record.status != "listed":
                    continue
                dlc_appid = _optional_int(record.payload.get("dlc_appid"))
                parent_appid = _optional_int(record.payload.get("parent_appid"))
                if dlc_appid is None or parent_appid is None:
                    continue
                pair = (dlc_appid, parent_appid)
                if pair not in seen_dlc_pairs:
                    seen_dlc_pairs.add(pair)
                    dlc_pairs.append(pair)
        except requests.RequestException as exc:
            records.append(_failed_steam_record(appid, "appdetails", exc))

        try:
            news_payload = _get_json(
                session,
                "https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/",
                {
                    "appid": str(appid),
                    "count": str(news_count),
                    "maxlength": "1000",
                    "format": "json",
                },
                timeout,
            )
            records.extend(records_from_steam_news(appid, news_payload))
        except requests.RequestException as exc:
            records.append(_failed_steam_record(appid, "news", exc))
    if include_dlc_details:
        for dlc_appid, parent_appid in dlc_pairs:
            try:
                dlc_payload = _get_json(
                    session,
                    "https://store.steampowered.com/api/appdetails",
                    {"appids": str(dlc_appid), "filters": "basic"},
                    timeout,
                )
                records.append(
                    records_from_steam_dlc_appdetails(dlc_appid, parent_appid, dlc_payload)
                )
            except requests.RequestException as exc:
                records.append(_failed_steam_dlc_record(dlc_appid, parent_appid, exc))
    return records


def fetch_klei_records(*, timeout: int, session=None) -> List[OfficialRecord]:
    session = session or _session()
    targets = [
        (
            "klei_dst_page",
            "https://www.klei.com/games/dont-starve-together",
        ),
        (
            "klei_ds_page",
            "https://www.klei.com/games/dont-starve",
        ),
        (
            "klei_dst_updates",
            "https://forums.kleientertainment.com/game-updates/dst/",
        ),
    ]
    records: List[OfficialRecord] = []
    for external_id, url in targets:
        try:
            response = session.get(url, timeout=timeout)
            body = response.text
            records.append(
                record_from_http_probe(
                    provider="klei",
                    record_type="http_probe",
                    external_id=external_id,
                    url=url,
                    status_code=response.status_code,
                    body=body,
                )
            )
        except requests.RequestException as exc:
            records.append(
                record_from_http_probe(
                    provider="klei",
                    record_type="http_probe",
                    external_id=external_id,
                    url=url,
                    status_code=None,
                    body="",
                    error=str(exc),
                )
            )
    return records


def write_official_records(conn, records: Iterable[OfficialRecord]) -> int:
    count = 0
    for record in records:
        upsert_official_record(conn, record)
        count += 1
    conn.commit()
    return count


def _get_json(session, url: str, params: Mapping[str, str], timeout: int) -> Mapping[str, object]:
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _failed_steam_record(appid: int, record_type: str, exc: Exception) -> OfficialRecord:
    return OfficialRecord(
        provider="steam",
        record_type=record_type,
        external_id=str(appid),
        title=f"Steam {record_type} {appid}",
        url=f"https://store.steampowered.com/app/{appid}/",
        status="failed",
        summary=str(exc),
        payload={"error": str(exc), "appid": appid, "record_type": record_type},
    )


def _failed_steam_dlc_record(dlc_appid: int, parent_appid: int, exc: Exception) -> OfficialRecord:
    return OfficialRecord(
        provider="steam",
        record_type="dlc_appdetails",
        external_id=str(dlc_appid),
        title=f"Steam DLC {dlc_appid}",
        url=f"https://store.steampowered.com/app/{dlc_appid}/",
        status="failed",
        summary=str(exc),
        payload={
            "error": str(exc),
            "parent_appid": parent_appid,
            "dlc_appid": dlc_appid,
            "record_type": "dlc_appdetails",
        },
    )


def _session():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _text_excerpt(value: str, limit: int) -> str:
    text = " ".join(value.split())
    return text[:limit]


class _TitleParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_title = False
        self.parts: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "title":
            self.in_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.parts.append(data)


def _html_title(html: str) -> str | None:
    parser = _TitleParser()
    parser.feed(html or "")
    title = " ".join(part.strip() for part in parser.parts if part.strip())
    return title or None
