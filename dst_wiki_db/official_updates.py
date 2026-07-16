from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import re
import sqlite3
from typing import Mapping


STEAM_CLAN_IMAGE_RE = re.compile(
    r"\{STEAM_CLAN_IMAGE\}/(?P<clan_id>\d+)/"
    r"(?P<filename>[A-Za-z0-9._-]+?\.(?:png|jpe?g|gif|webp|avif))",
    re.IGNORECASE,
)
STEAM_CLAN_PLACEHOLDER_RE = re.compile(
    r"\{STEAM_CLAN_IMAGE\}/\d+/[^\s<]+",
    re.IGNORECASE,
)


def rebuild_official_update_events(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("delete from official_update_media")
    conn.execute("delete from official_update_events")
    records = conn.execute(
        """
        select id, provider, record_type, external_id, title, url, summary, payload_json
        from official_records
        where provider='steam' and record_type='news' and status='ok'
        order by id
        """
    ).fetchall()

    event_count = 0
    media_count = 0
    for record in records:
        payload = _json_object(str(record["payload_json"] or "{}"))
        contents = _optional_text(payload.get("contents")) or ""
        published_at_unix = _optional_int(payload.get("date"))
        content_text = _plain_text(contents)
        cursor = conn.execute(
            """
            insert into official_update_events (
                official_record_id, provider, record_type, external_id, appid,
                title, url, author, published_at_unix, published_at_iso,
                event_type, summary, content_text, content_length,
                mentioned_entity_count
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(record["id"]),
                str(record["provider"]),
                str(record["record_type"]),
                str(record["external_id"]),
                _optional_int(payload.get("appid")),
                str(record["title"]),
                record["url"],
                _optional_text(payload.get("author")),
                published_at_unix,
                _iso_timestamp(published_at_unix),
                _event_type(str(record["title"]), _optional_text(payload.get("author"))),
                _optional_text(record["summary"]),
                content_text,
                len(content_text),
                _mention_count(conn, int(record["id"])),
            ),
        )
        official_update_event_id = int(cursor.lastrowid)
        event_count += 1
        media_count += _insert_media(
            conn,
            official_update_event_id=official_update_event_id,
            official_record_id=int(record["id"]),
            provider=str(record["provider"]),
            external_id=str(record["external_id"]),
            contents=contents,
        )
    conn.commit()
    return {
        "official_update_events": event_count,
        "official_update_media": media_count,
    }


def _insert_media(
    conn: sqlite3.Connection,
    *,
    official_update_event_id: int,
    official_record_id: int,
    provider: str,
    external_id: str,
    contents: str,
) -> int:
    count = 0
    seen_urls: set[str] = set()
    clan_index = 0
    for match in STEAM_CLAN_IMAGE_RE.finditer(contents):
        media_url = (
            "https://clan.cloudflare.steamstatic.com/images/"
            f"{match.group('clan_id')}/{match.group('filename')}"
        )
        if media_url in seen_urls:
            continue
        seen_urls.add(media_url)
        _insert_media_row(
            conn,
            official_update_event_id=official_update_event_id,
            official_record_id=official_record_id,
            provider=provider,
            external_id=external_id,
            media_role="steam_clan_image",
            media_index=clan_index,
            media_url=media_url,
            width=None,
            height=None,
        )
        clan_index += 1
        count += 1

    html_index = 0
    for media_url, width, height in _html_images(contents):
        if media_url in seen_urls:
            continue
        seen_urls.add(media_url)
        _insert_media_row(
            conn,
            official_update_event_id=official_update_event_id,
            official_record_id=official_record_id,
            provider=provider,
            external_id=external_id,
            media_role="html_image",
            media_index=html_index,
            media_url=media_url,
            width=width,
            height=height,
        )
        html_index += 1
        count += 1
    return count


def _insert_media_row(
    conn: sqlite3.Connection,
    *,
    official_update_event_id: int,
    official_record_id: int,
    provider: str,
    external_id: str,
    media_role: str,
    media_index: int,
    media_url: str,
    width: int | None,
    height: int | None,
) -> None:
    conn.execute(
        """
        insert into official_update_media (
            official_update_event_id, official_record_id, provider, external_id,
            media_role, media_index, media_url, width, height, source_field
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, 'contents')
        """,
        (
            official_update_event_id,
            official_record_id,
            provider,
            external_id,
            media_role,
            media_index,
            media_url,
            width,
            height,
        ),
    )


def _mention_count(conn: sqlite3.Connection, official_record_id: int) -> int:
    row = conn.execute(
        """
        select count(distinct entity_id) as count
        from official_record_mentions
        where official_record_id=?
        """,
        (official_record_id,),
    ).fetchone()
    return int(row["count"] if hasattr(row, "keys") else row[0])


def _event_type(title: str, author: str | None) -> str:
    title_key = title.casefold()
    if "hotfix" in title_key:
        return "hotfix"
    if (author or "").casefold() == "steamdb" or "peaks at" in title_key:
        return "milestone"
    event_terms = (
        "cawnival",
        "winter's feast",
        "hallowed nights",
        "year of the",
        "klei fest",
        " is back",
        "has arrived",
    )
    if any(term in title_key for term in event_terms):
        return "event"
    if "update" in title_key or "available" in title_key or "from beyond" in title_key:
        return "update"
    return "announcement"


def _iso_timestamp(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _plain_text(contents: str) -> str:
    parser = _TextParser()
    without_valid_images = STEAM_CLAN_IMAGE_RE.sub(" ", contents)
    parser.feed(STEAM_CLAN_PLACEHOLDER_RE.sub(" ", without_valid_images))
    return " ".join(" ".join(parser.parts).split())


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data):
        if data.strip():
            self.parts.append(data)


class _ImageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.images: list[tuple[str, int | None, int | None]] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "img":
            return
        values = {str(key).lower(): value for key, value in attrs}
        src = _optional_text(values.get("src"))
        if not src:
            return
        self.images.append(
            (
                src,
                _optional_int(values.get("width")),
                _optional_int(values.get("height")),
            )
        )


def _html_images(contents: str) -> list[tuple[str, int | None, int | None]]:
    parser = _ImageParser()
    parser.feed(contents)
    return parser.images


def _json_object(payload_json: str) -> dict:
    try:
        payload = json.loads(payload_json or "{}")
    except json.JSONDecodeError:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
