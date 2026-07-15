from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterable, Iterator, List, Mapping, Sequence
from urllib.parse import quote

from dst_wiki_db.mediawiki import MediaWikiClient, page_revision, page_wikitext
from dst_wiki_db.parser import ParsedImage, ParsedPage, parse_page
from dst_wiki_db.schema import connect, init_db, slugify, upsert_entity, upsert_source


@dataclass(frozen=True)
class SourceDefinition:
    key: str
    name: str
    base_url: str
    api_url: str
    role: str
    license: str
    notes: str = ""
    api_restricted_by_robots: bool = False


SOURCE_DEFINITIONS = {
    "wiki.gg": SourceDefinition(
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
        license="CC BY-SA 4.0",
        notes="Largest current community wiki; API use should respect wiki.gg robots/permission.",
        api_restricted_by_robots=True,
    ),
    "fandom": SourceDefinition(
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
        license="CC BY-SA / Fandom licensing",
        notes="Historical comparison source; not preferred canonical.",
    ),
    "klei": SourceDefinition(
        key="klei",
        name="Klei Entertainment",
        base_url="https://www.klei.com",
        api_url="https://www.klei.com",
        role="official_verification",
        license="Official website; not a bulk reusable content license.",
        notes="Use for product/update verification, not as a wiki dump.",
    ),
    "steam": SourceDefinition(
        key="steam",
        name="Steam Store / Steam Web API",
        base_url="https://store.steampowered.com",
        api_url="https://store.steampowered.com/api/appdetails",
        role="official_verification",
        license="Store metadata and media rights belong to Valve/Klei/rightsholders.",
        notes="Use for product/appid/DLC verification.",
    ),
}


def canonical_slug(title: str) -> str:
    return slugify(title)


def source_url(base_url: str, title: str) -> str:
    encoded = quote(title.replace(" ", "_"), safe="/()'!,:")
    return f"{base_url.rstrip('/')}/wiki/{encoded}"


def canonical_field_name(raw_name: str) -> str:
    name = _snake_case(raw_name.strip())
    name = re.sub(r"^(?:dst|ds)_", "", name)
    name = re.sub(r"_(?:dst|ds)$", "", name)
    aliases = {
        "dsthealth": "health",
        "dshealth": "health",
        "spawncode": "spawn_code",
        "spawn_code": "spawn_code",
        "attackrange": "attack_range",
        "attack_range": "attack_range",
        "attackperiod": "attack_period",
        "attack_period": "attack_period",
        "walkspeed": "walk_speed",
        "walk_speed": "walk_speed",
        "runspeed": "run_speed",
        "run_speed": "run_speed",
        "planardamage": "planar_damage",
        "planar_damage": "planar_damage",
        "d_s_thealth": "health",
        "d_s_health": "health",
        "d_s_t_health": "health",
    }
    return aliases.get(name, name)


def variant_key_from_raw_name(raw_name: str) -> str:
    lowered = raw_name.strip().lower()
    snake = _snake_case(raw_name)
    if lowered.startswith("dst") or lowered.endswith(" dst") or snake.endswith("_dst"):
        return "dst"
    if lowered.startswith("ds") or lowered.endswith(" ds") or snake.endswith("_ds"):
        return "ds"
    phase_names = {
        "seed",
        "sprout",
        "small",
        "med",
        "medium",
        "large",
        "bolting",
        "picked",
        "raw",
        "cooked",
    }
    if snake in phase_names:
        return snake
    match = re.search(r"(\d+)$", snake)
    if match:
        return match.group(1)
    return ""


def extract_number(value: str) -> float | int | None:
    match = re.search(r"[-+]?\d+(?:\.\d+)?", value.replace(",", ""))
    if not match:
        return None
    number = float(match.group(0))
    if number.is_integer():
        return int(number)
    return number


def write_parsed_page(
    conn: sqlite3.Connection,
    *,
    source_id: int,
    raw_page_id: int,
    source_title: str,
    source_pageid: int,
    source_revid: int | None,
    source_timestamp: str | None,
    page_url: str,
    parsed: ParsedPage,
    primary: bool,
) -> int:
    slug = canonical_slug(source_title)
    existing = conn.execute("select id from entities where slug=?", (slug,)).fetchone()
    if primary or existing is None:
        entity_id = upsert_entity(
            conn,
            slug=slug,
            canonical_title=source_title,
            kind=parsed.kind,
            primary_source_id=source_id,
            primary_page_id=source_pageid,
            canonical_url=page_url,
            summary=parsed.summary,
            confidence=1.0 if primary else 0.8,
        )
    else:
        entity_id = int(existing["id"])

    conn.execute(
        """
        insert into entity_sources (
            entity_id, source_id, raw_page_id, source_title, source_pageid,
            source_revid, source_timestamp, source_url, match_method, confidence
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(entity_id, source_id, source_pageid) do update set
            raw_page_id=excluded.raw_page_id,
            source_title=excluded.source_title,
            source_revid=excluded.source_revid,
            source_timestamp=excluded.source_timestamp,
            source_url=excluded.source_url,
            match_method=excluded.match_method,
            confidence=excluded.confidence
        """,
        (
            entity_id,
            source_id,
            raw_page_id,
            source_title,
            source_pageid,
            source_revid,
            source_timestamp,
            page_url,
            "title_slug",
            1.0 if primary else 0.85,
        ),
    )

    _replace_attributes(conn, entity_id, source_id, raw_page_id, parsed)
    _replace_images(conn, entity_id, source_id, raw_page_id, parsed.images)
    _replace_relations(conn, entity_id, source_id, raw_page_id, parsed.links)
    return entity_id


def build_database(
    *,
    db_path: Path,
    selected_sources: Sequence[str],
    limit: int | None,
    batch_size: int,
    sleep_seconds: float,
    download_images: str,
    image_dir: Path,
    coverage_path: Path | None,
    allow_restricted_api: bool,
) -> dict:
    conn = connect(db_path)
    init_db(conn)
    register_reference_sources(conn)

    coverage = {
        "started_at": _utc_now(),
        "sources": {},
        "warnings": [],
    }

    for key in selected_sources:
        source = SOURCE_DEFINITIONS[key]
        if source.api_restricted_by_robots and not allow_restricted_api:
            coverage["warnings"].append(
                {
                    "source": key,
                    "warning": "Skipped API fetch because this source is marked robots-restricted. Pass --allow-restricted-api only if you have permission.",
                }
            )
            continue

        client = MediaWikiClient(key, source.api_url, sleep_seconds=sleep_seconds)
        siteinfo = client.fetch_siteinfo()
        source_id = upsert_source(
            conn,
            key=source.key,
            name=source.name,
            base_url=source.base_url,
            api_url=source.api_url,
            role=source.role,
            license=source.license,
            fetched_at=_utc_now(),
            siteinfo_json=json.dumps(siteinfo, ensure_ascii=False),
        )

        titles = [row["title"] for row in client.iter_main_pages(limit=limit)]
        source_counts = {
            "titles_seen": len(titles),
            "pages_written": 0,
            "entities_written": 0,
            "images_registered": 0,
        }

        for batch in batched(titles, batch_size):
            pages = client.fetch_page_batch(batch)
            for page in pages:
                if page.get("missing"):
                    continue
                raw_page_id = write_raw_page(conn, source_id, source, page)
                text = page_wikitext(page)
                parsed = parse_page(str(page.get("title", "")), text)
                revision = page_revision(page)
                page_url = source_url(source.base_url, str(page.get("title", "")))
                entity_id = write_parsed_page(
                    conn,
                    source_id=source_id,
                    raw_page_id=raw_page_id,
                    source_title=str(page.get("title", "")),
                    source_pageid=int(page.get("pageid", 0)),
                    source_revid=_optional_int(revision.get("revid")),
                    source_timestamp=_optional_str(revision.get("timestamp")),
                    page_url=page_url,
                    parsed=parsed,
                    primary=source.role == "canonical",
                )
                source_counts["pages_written"] += 1
                source_counts["entities_written"] += 1
                source_counts["images_registered"] += len(parsed.images)
                _enrich_images(
                    conn,
                    client,
                    entity_id,
                    source_id,
                    raw_page_id,
                    parsed.images,
                    download_images=download_images,
                    image_dir=image_dir / source.key,
                )
            conn.commit()

        _write_source_verification(conn, source_id, key)
        conn.commit()
        coverage["sources"][key] = source_counts

    coverage["finished_at"] = _utc_now()
    coverage["database"] = str(db_path)
    if coverage_path:
        coverage_path.parent.mkdir(parents=True, exist_ok=True)
        coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, indent=2))
    return coverage


def register_reference_sources(conn: sqlite3.Connection) -> None:
    for source in SOURCE_DEFINITIONS.values():
        upsert_source(
            conn,
            key=source.key,
            name=source.name,
            base_url=source.base_url,
            api_url=source.api_url,
            role=source.role,
            license=source.license,
        )


def write_raw_page(
    conn: sqlite3.Connection,
    source_id: int,
    source: SourceDefinition,
    page: Mapping[str, object],
) -> int:
    revision = page_revision(page)
    title = str(page.get("title", ""))
    pageid = int(page.get("pageid", 0))
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, parentid, source_timestamp,
            canonical_url, wikitext, categories_json, templates_json, images_json,
            externallinks_json, fetched_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(source_id, pageid) do update set
            ns=excluded.ns,
            title=excluded.title,
            revid=excluded.revid,
            parentid=excluded.parentid,
            source_timestamp=excluded.source_timestamp,
            canonical_url=excluded.canonical_url,
            wikitext=excluded.wikitext,
            categories_json=excluded.categories_json,
            templates_json=excluded.templates_json,
            images_json=excluded.images_json,
            externallinks_json=excluded.externallinks_json,
            fetched_at=excluded.fetched_at
        """,
        (
            source_id,
            pageid,
            int(page.get("ns", 0)),
            title,
            _optional_int(revision.get("revid")),
            _optional_int(revision.get("parentid")),
            _optional_str(revision.get("timestamp")),
            source_url(source.base_url, title),
            page_wikitext(page),
            json.dumps(page.get("categories", []), ensure_ascii=False),
            json.dumps(page.get("templates", []), ensure_ascii=False),
            json.dumps(page.get("images", []), ensure_ascii=False),
            json.dumps(page.get("externallinks", []), ensure_ascii=False),
            _utc_now(),
        ),
    )
    row = conn.execute(
        "select id from raw_pages where source_id=? and pageid=?", (source_id, pageid)
    ).fetchone()
    return int(row["id"])


def batched(items: Sequence[str], size: int) -> Iterator[List[str]]:
    for index in range(0, len(items), size):
        yield list(items[index : index + size])


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a Don't Starve wiki SQLite database.")
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--sources", nargs="+", choices=["wiki.gg", "fandom"], default=["fandom"])
    parser.add_argument("--limit", type=int, default=100, help="Maximum pages per source; use 0 for all pages.")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--sleep", type=float, default=0.25)
    parser.add_argument("--download-images", choices=["none", "primary", "all"], default="primary")
    parser.add_argument("--image-dir", type=Path, default=Path("data/images"))
    parser.add_argument("--coverage", type=Path, default=Path("reports/coverage.json"))
    parser.add_argument(
        "--allow-restricted-api",
        action="store_true",
        help="Permit sources marked as robots-restricted. Use only with permission.",
    )
    args = parser.parse_args(argv)

    args.db.parent.mkdir(parents=True, exist_ok=True)
    coverage = build_database(
        db_path=args.db,
        selected_sources=args.sources,
        limit=None if args.limit == 0 else args.limit,
        batch_size=args.batch_size,
        sleep_seconds=args.sleep,
        download_images=args.download_images,
        image_dir=args.image_dir,
        coverage_path=args.coverage,
        allow_restricted_api=args.allow_restricted_api,
    )
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    return 0


def _replace_attributes(
    conn: sqlite3.Connection,
    entity_id: int,
    source_id: int,
    raw_page_id: int,
    parsed: ParsedPage,
) -> None:
    conn.execute(
        "delete from entity_attributes where entity_id=? and source_id=? and raw_page_id=?",
        (entity_id, source_id, raw_page_id),
    )
    for template_index, infobox in enumerate(parsed.infoboxes):
        for raw_name, value in infobox.params.items():
            variant = variant_key_from_raw_name(raw_name)
            conn.execute(
                """
                insert into entity_attributes (
                    entity_id, source_id, raw_page_id, template_index, template_name, raw_name,
                    canonical_name, value_text, value_number, unit, variant_key
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entity_id,
                    source_id,
                    raw_page_id,
                    template_index,
                    infobox.name,
                    raw_name,
                    canonical_field_name(raw_name),
                    value,
                    extract_number(value),
                    None,
                    variant,
                ),
            )


def _replace_images(
    conn: sqlite3.Connection,
    entity_id: int,
    source_id: int,
    raw_page_id: int,
    images: Sequence[ParsedImage],
) -> None:
    conn.execute(
        "delete from entity_images where entity_id=? and source_id=? and raw_page_id=?",
        (entity_id, source_id, raw_page_id),
    )
    for image in images:
        conn.execute(
            """
            insert into entity_images (
                entity_id, source_id, raw_page_id, image_name, role, variant_key
            )
            values (?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                source_id,
                raw_page_id,
                image.name,
                image.role,
                variant_key_from_raw_name(image.role),
            ),
        )


def _replace_relations(
    conn: sqlite3.Connection,
    entity_id: int,
    source_id: int,
    raw_page_id: int,
    links: Sequence[str],
) -> None:
    conn.execute(
        "delete from entity_relations where entity_id=? and source_id=? and raw_page_id=?",
        (entity_id, source_id, raw_page_id),
    )
    for link in links:
        conn.execute(
            """
            insert or ignore into entity_relations (
                entity_id, source_id, raw_page_id, relation_type,
                target_title, target_slug, raw_value
            )
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            (entity_id, source_id, raw_page_id, "wikilink", link, canonical_slug(link), link),
        )


def _enrich_images(
    conn: sqlite3.Connection,
    client: MediaWikiClient,
    entity_id: int,
    source_id: int,
    raw_page_id: int,
    images: Sequence[ParsedImage],
    *,
    download_images: str,
    image_dir: Path,
) -> None:
    selected = list(images)
    if download_images == "primary":
        selected = selected[:1]
    if not selected:
        return
    info_by_title = client.fetch_imageinfo([image.name for image in selected])
    for image in selected:
        file_title = _file_title(image.name)
        info = info_by_title.get(file_title, {})
        local_path = None
        if download_images != "none" and info.get("url"):
            destination = image_dir / _safe_filename(image.name)
            local_path = str(client.download_url(str(info["url"]), destination))
        conn.execute(
            """
            update entity_images
            set original_url=?, description_url=?, local_path=?, width=?, height=?, mime=?, sha1=?
            where entity_id=? and source_id=? and raw_page_id=? and image_name=? and role=?
            """,
            (
                info.get("url") or info.get("thumburl"),
                info.get("descriptionurl"),
                local_path,
                _optional_int(info.get("width")),
                _optional_int(info.get("height")),
                info.get("mime"),
                info.get("sha1"),
                entity_id,
                source_id,
                raw_page_id,
                image.name,
                image.role,
            ),
        )


def _write_source_verification(conn: sqlite3.Connection, source_id: int, source_key: str) -> None:
    rows = conn.execute(
        """
        select e.id
        from entities e
        join entity_sources es on es.entity_id = e.id
        where es.source_id = ?
        """,
        (source_id,),
    ).fetchall()
    for row in rows:
        conn.execute(
            """
            insert into verification_checks (
                entity_id, check_type, source_key, target_key, status, details_json
            )
            values (?, 'source_presence', ?, ?, 'present', ?)
            on conflict(entity_id, check_type, source_key, target_key) do update set
                status=excluded.status,
                details_json=excluded.details_json,
                checked_at=current_timestamp
            """,
            (
                int(row["id"]),
                source_key,
                source_key,
                json.dumps({"source_id": source_id}, ensure_ascii=False),
            ),
        )


def _snake_case(value: str) -> str:
    replaced = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value.strip())
    replaced = re.sub(r"[^A-Za-z0-9]+", "_", replaced)
    return replaced.strip("_").lower()


def _file_title(name: str) -> str:
    if name.lower().startswith(("file:", "image:")):
        return "File:" + name.split(":", 1)[1].strip()
    return "File:" + name.strip()


def _safe_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
