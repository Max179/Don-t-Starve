from __future__ import annotations

from html.parser import HTMLParser
import json
import sqlite3
from typing import Mapping


DIRECT_MEDIA_FIELDS = (
    "header_image",
    "capsule_image",
    "capsule_imagev5",
    "background",
    "background_raw",
)
HTML_MEDIA_FIELDS = (
    ("detailed_description", "description_image"),
    ("about_the_game", "about_image"),
)


def rebuild_official_products(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("delete from official_product_media")
    conn.execute("delete from official_products")
    records = conn.execute(
        """
        select id, provider, record_type, external_id, title, url, summary, payload_json
        from official_records
        where provider='steam'
          and record_type in ('appdetails', 'dlc_appdetails')
          and status='ok'
        order by id
        """
    ).fetchall()

    product_count = 0
    media_count = 0
    for record in records:
        payload = _json_object(str(record["payload_json"] or "{}"))
        data, parent_appid = _product_data(str(record["record_type"]), payload)
        if not data:
            continue
        parent_external_id, parent_title = _parent_fields(data, parent_appid)
        release_date = data.get("release_date")
        if not isinstance(release_date, Mapping):
            release_date = {}
        cursor = conn.execute(
            """
            insert into official_products (
                official_record_id, provider, record_type, external_id,
                product_type, title, url, parent_external_id, parent_title,
                short_description, release_date_text, is_free, required_age,
                controller_support, website, supported_languages
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(record["id"]),
                str(record["provider"]),
                str(record["record_type"]),
                str(record["external_id"]),
                str(data.get("type") or "unknown"),
                str(data.get("name") or record["title"]),
                record["url"],
                parent_external_id,
                parent_title,
                _optional_text(data.get("short_description") or record["summary"]),
                _optional_text(release_date.get("date")),
                _bool_int(data.get("is_free")),
                _optional_int(data.get("required_age")),
                _optional_text(data.get("controller_support")),
                _optional_text(data.get("website")),
                _optional_text(data.get("supported_languages")),
            ),
        )
        official_product_id = int(cursor.lastrowid)
        product_count += 1
        media_count += _insert_media(
            conn,
            official_product_id=official_product_id,
            official_record_id=int(record["id"]),
            provider=str(record["provider"]),
            external_id=str(record["external_id"]),
            data=data,
        )
    conn.commit()
    return {
        "official_products": product_count,
        "official_product_media": media_count,
    }


def _product_data(record_type: str, payload: Mapping[str, object]) -> tuple[dict, object]:
    if record_type == "dlc_appdetails":
        data = payload.get("data")
        return (dict(data), payload.get("parent_appid")) if isinstance(data, Mapping) else ({}, None)
    return dict(payload), None


def _parent_fields(data: Mapping[str, object], parent_appid: object) -> tuple[str | None, str | None]:
    fullgame = data.get("fullgame")
    if isinstance(fullgame, Mapping):
        parent_external_id = _optional_text(fullgame.get("appid") or parent_appid)
        parent_title = _optional_text(fullgame.get("name"))
        return parent_external_id, parent_title
    return _optional_text(parent_appid), None


def _insert_media(
    conn: sqlite3.Connection,
    *,
    official_product_id: int,
    official_record_id: int,
    provider: str,
    external_id: str,
    data: Mapping[str, object],
) -> int:
    count = 0
    seen_urls: set[str] = set()
    for media_role in DIRECT_MEDIA_FIELDS:
        media_url = _optional_text(data.get(media_role))
        if not media_url or media_url in seen_urls:
            continue
        seen_urls.add(media_url)
        _insert_media_row(
            conn,
            official_product_id=official_product_id,
            official_record_id=official_record_id,
            provider=provider,
            external_id=external_id,
            media_role=media_role,
            media_index=0,
            media_url=media_url,
            width=None,
            height=None,
            source_field=media_role,
        )
        count += 1

    for source_field, media_role in HTML_MEDIA_FIELDS:
        html = _optional_text(data.get(source_field))
        if not html:
            continue
        media_index = 0
        for media_url, width, height in _html_images(html):
            if media_url in seen_urls:
                continue
            seen_urls.add(media_url)
            _insert_media_row(
                conn,
                official_product_id=official_product_id,
                official_record_id=official_record_id,
                provider=provider,
                external_id=external_id,
                media_role=media_role,
                media_index=media_index,
                media_url=media_url,
                width=width,
                height=height,
                source_field=source_field,
            )
            count += 1
            media_index += 1
    return count


def _insert_media_row(
    conn: sqlite3.Connection,
    *,
    official_product_id: int,
    official_record_id: int,
    provider: str,
    external_id: str,
    media_role: str,
    media_index: int,
    media_url: str,
    width: int | None,
    height: int | None,
    source_field: str,
) -> None:
    conn.execute(
        """
        insert into official_product_media (
            official_product_id, official_record_id, provider, external_id,
            media_role, media_index, media_url, width, height, source_field
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            official_product_id,
            official_record_id,
            provider,
            external_id,
            media_role,
            media_index,
            media_url,
            width,
            height,
            source_field,
        ),
    )


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


def _html_images(html: str) -> list[tuple[str, int | None, int | None]]:
    parser = _ImageParser()
    parser.feed(html)
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


def _bool_int(value: object) -> int | None:
    if value is None:
        return None
    return int(bool(value))
