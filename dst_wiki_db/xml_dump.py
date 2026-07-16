from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import bz2
import gzip
import json
import sqlite3
import xml.etree.ElementTree as ET
from typing import Iterator, Mapping

from dst_wiki_db.build import (
    SOURCE_DEFINITIONS,
    source_url,
    write_parsed_page,
    write_raw_page,
)
from dst_wiki_db.parser import ParsedPage, parse_page
from dst_wiki_db.schema import init_db, upsert_source


@dataclass(frozen=True)
class DumpPage:
    title: str
    pageid: int
    ns: int
    revid: int | None
    timestamp: str | None
    text: str
    redirect: bool = False


def iter_mediawiki_xml_dump_pages(
    dump_path: str | Path,
    *,
    namespace: int = 0,
    include_redirects: bool = False,
    limit: int | None = None,
) -> Iterator[DumpPage]:
    yielded = 0
    with _open_dump(dump_path) as handle:
        for event, element in ET.iterparse(handle, events=("end",)):
            if _tag_name(element.tag) != "page":
                continue
            page = _dump_page_from_element(element)
            element.clear()
            if page is None:
                continue
            if page.ns != namespace:
                continue
            if page.redirect and not include_redirects:
                continue
            yield page
            yielded += 1
            if limit is not None and yielded >= limit:
                break


def read_mediawiki_xml_siteinfo(dump_path: str | Path) -> dict[str, str]:
    siteinfo: dict[str, str] = {}
    in_siteinfo = False
    with _open_dump(dump_path) as handle:
        for event, element in ET.iterparse(handle, events=("start", "end")):
            name = _tag_name(element.tag)
            if event == "start" and name == "siteinfo":
                in_siteinfo = True
                continue
            if event != "end" or not in_siteinfo:
                continue
            if name == "siteinfo":
                element.clear()
                return siteinfo
            value = (element.text or "").strip()
            if value:
                siteinfo[name] = value
            element.clear()
    return {}


def import_mediawiki_xml_dump(
    conn: sqlite3.Connection,
    *,
    dump_path: str | Path,
    source_key: str,
    limit: int | None = None,
    include_redirects: bool = False,
) -> dict[str, int | str]:
    init_db(conn)
    source = SOURCE_DEFINITIONS[source_key]
    siteinfo = read_mediawiki_xml_siteinfo(dump_path)
    source_id = upsert_source(
        conn,
        key=source.key,
        name=source.name,
        base_url=source.base_url,
        api_url=source.api_url,
        role=source.role,
        license=source.license,
        fetched_at=_utc_now(),
        siteinfo_json=json.dumps(siteinfo, ensure_ascii=False, sort_keys=True),
    )

    result: dict[str, int | str] = {
        "source": source.key,
        "pages_seen": 0,
        "pages_written": 0,
        "entities_written": 0,
        "images_registered": 0,
    }
    for dump_page in iter_mediawiki_xml_dump_pages(
        dump_path,
        include_redirects=include_redirects,
        limit=limit,
    ):
        result["pages_seen"] = int(result["pages_seen"]) + 1
        parsed = parse_page(dump_page.title, dump_page.text)
        raw_page_id = write_raw_page(
            conn,
            source_id,
            source,
            _page_mapping_from_dump(dump_page, parsed),
        )
        write_parsed_page(
            conn,
            source_id=source_id,
            raw_page_id=raw_page_id,
            source_title=dump_page.title,
            source_pageid=dump_page.pageid,
            source_revid=dump_page.revid,
            source_timestamp=dump_page.timestamp,
            page_url=source_url(source.base_url, dump_page.title),
            parsed=parsed,
            primary=source.role == "canonical",
        )
        result["pages_written"] = int(result["pages_written"]) + 1
        result["entities_written"] = int(result["entities_written"]) + 1
        result["images_registered"] = int(result["images_registered"]) + len(parsed.images)
        conn.commit()
    return result


def _page_mapping_from_dump(page: DumpPage, parsed: ParsedPage) -> Mapping[str, object]:
    revision = {
        "revid": page.revid,
        "timestamp": page.timestamp,
        "slots": {"main": {"content": page.text}},
    }
    return {
        "pageid": page.pageid,
        "ns": page.ns,
        "title": page.title,
        "revisions": [revision],
        "categories": [{"title": f"Category:{category}"} for category in parsed.categories],
        "templates": [{"title": f"Template:{infobox.name}"} for infobox in parsed.infoboxes],
        "images": [{"title": f"File:{image.name}"} for image in parsed.images],
        "externallinks": [],
    }


def _dump_page_from_element(element: ET.Element) -> DumpPage | None:
    title = _child_text(element, "title")
    if not title:
        return None
    pageid = _optional_int(_child_text(element, "id")) or 0
    ns = _optional_int(_child_text(element, "ns")) or 0
    redirect = any(_tag_name(child.tag) == "redirect" for child in list(element))
    revision = _first_child(element, "revision")
    revid = _optional_int(_child_text(revision, "id")) if revision is not None else None
    timestamp = _child_text(revision, "timestamp") if revision is not None else None
    text = _child_text(revision, "text") if revision is not None else ""
    return DumpPage(
        title=title,
        pageid=pageid,
        ns=ns,
        revid=revid,
        timestamp=timestamp,
        text=text or "",
        redirect=redirect,
    )


def _open_dump(path: str | Path):
    dump_path = Path(path)
    if dump_path.suffix == ".gz":
        return gzip.open(dump_path, "rb")
    if dump_path.suffix == ".bz2":
        return bz2.open(dump_path, "rb")
    return dump_path.open("rb")


def _first_child(element: ET.Element | None, name: str) -> ET.Element | None:
    if element is None:
        return None
    for child in list(element):
        if _tag_name(child.tag) == name:
            return child
    return None


def _child_text(element: ET.Element | None, name: str) -> str:
    child = _first_child(element, name)
    if child is None:
        return ""
    return (child.text or "").strip()


def _tag_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
