from __future__ import annotations

from pathlib import Path
import time
from typing import Dict, Iterable, Iterator, List, Mapping, MutableMapping, Sequence

import requests


DEFAULT_USER_AGENT = (
    "CodexDSTDatabaseBot/0.1 "
    "(local research database; respects MediaWiki API continuation)"
)


class MediaWikiClient:
    def __init__(
        self,
        key: str,
        api_url: str,
        *,
        session=None,
        sleep_seconds: float = 0.2,
        timeout: int = 30,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.key = key
        self.api_url = api_url
        self.session = session or requests.Session()
        self.sleep_seconds = sleep_seconds
        self.timeout = timeout
        self.user_agent = user_agent
        if hasattr(self.session, "headers"):
            self.session.headers.update({"User-Agent": user_agent})

    def query(self, params: Mapping[str, object]) -> dict:
        merged: Dict[str, object] = {
            "format": "json",
            "formatversion": "2",
        }
        merged.update(params)
        response = self.session.get(self.api_url, params=merged, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            error = payload["error"]
            raise RuntimeError(f"MediaWiki API error for {self.key}: {error}")
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        return payload

    def query_all(self, params: Mapping[str, object]) -> Iterator[dict]:
        current: MutableMapping[str, object] = dict(params)
        while True:
            payload = self.query(current)
            rows = _extract_query_list(payload)
            for row in rows:
                yield row
            continuation = payload.get("continue")
            if not continuation:
                break
            current.update(continuation)

    def fetch_siteinfo(self) -> dict:
        return self.query(
            {
                "action": "query",
                "meta": "siteinfo",
                "siprop": "general|statistics|rightsinfo",
            }
        )

    def iter_main_pages(self, *, limit: int | None = None) -> Iterator[dict]:
        count = 0
        for row in self.query_all(
            {
                "action": "query",
                "list": "allpages",
                "apnamespace": "0",
                "apfilterredir": "nonredirects",
                "aplimit": "max",
            }
        ):
            yield row
            count += 1
            if limit is not None and count >= limit:
                break

    def fetch_page_batch(self, titles: Sequence[str]) -> List[dict]:
        if not titles:
            return []
        payload = self.query(
            {
                "action": "query",
                "titles": "|".join(titles),
                "prop": "revisions|categories|templates|images",
                "rvprop": "ids|timestamp|content",
                "rvslots": "main",
                "cllimit": "max",
                "tllimit": "max",
                "imlimit": "max",
            }
        )
        return payload.get("query", {}).get("pages", [])

    def fetch_parse_metadata(self, title: str) -> dict:
        payload = self.query(
            {
                "action": "parse",
                "page": title,
                "prop": "templates|images|categories|externallinks|sections|displaytitle",
            }
        )
        return payload.get("parse", {})

    def fetch_imageinfo(self, image_names: Sequence[str]) -> Dict[str, dict]:
        if not image_names:
            return {}
        file_titles = [_file_title(name) for name in image_names]
        payload = self.query(
            {
                "action": "query",
                "titles": "|".join(file_titles),
                "prop": "imageinfo",
                "iiprop": "url|mime|size|sha1",
                "iiurlwidth": "512",
            }
        )
        result: Dict[str, dict] = {}
        for page in payload.get("query", {}).get("pages", []):
            title = page.get("title")
            imageinfo = page.get("imageinfo") or []
            if title and imageinfo:
                result[title] = imageinfo[0]
        return result

    def download_url(self, url: str, destination: Path) -> Path:
        destination.parent.mkdir(parents=True, exist_ok=True)
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        destination.write_bytes(response.content)
        if self.sleep_seconds:
            time.sleep(self.sleep_seconds)
        return destination


def page_wikitext(page: Mapping[str, object]) -> str:
    revisions = page.get("revisions") or []
    if not revisions:
        return ""
    revision = revisions[0]
    if not isinstance(revision, Mapping):
        return ""
    slots = revision.get("slots")
    if isinstance(slots, Mapping):
        main = slots.get("main")
        if isinstance(main, Mapping):
            content = main.get("content", main.get("*", ""))
            return str(content or "")
    return str(revision.get("content", revision.get("*", "")) or "")


def page_revision(page: Mapping[str, object]) -> Mapping[str, object]:
    revisions = page.get("revisions") or []
    if revisions and isinstance(revisions[0], Mapping):
        return revisions[0]
    return {}


def _extract_query_list(payload: Mapping[str, object]) -> List[dict]:
    query = payload.get("query", {})
    if not isinstance(query, Mapping):
        return []
    for value in query.values():
        if isinstance(value, list):
            return value
    return []


def _file_title(name: str) -> str:
    if name.lower().startswith(("file:", "image:")):
        return "File:" + name.split(":", 1)[1].strip()
    return "File:" + name.strip()
