#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.build import SOURCE_DEFINITIONS, register_reference_sources
from dst_wiki_db.schema import connect, init_db
from dst_wiki_db.source_audit import (
    audit_http_endpoint,
    audit_mediawiki_source,
    summarize_source_audits,
    write_source_audits,
)


OFFICIAL_HTTP_TARGETS = [
    (
        "klei",
        "official_http_probe",
        "https://www.klei.com/games/dont-starve-together",
        "Klei Don't Starve Together product page",
    ),
    (
        "klei",
        "official_http_probe",
        "https://www.klei.com/games/dont-starve",
        "Klei Don't Starve product page",
    ),
    (
        "klei",
        "official_http_probe",
        "https://forums.kleientertainment.com/game-updates/dst/",
        "Klei DST update forum",
    ),
    (
        "steam",
        "official_http_probe",
        "https://store.steampowered.com/api/appdetails?appids=322330&filters=basic",
        "Steam appdetails 322330",
    ),
    (
        "steam",
        "official_http_probe",
        "https://store.steampowered.com/api/appdetails?appids=219740&filters=basic",
        "Steam appdetails 219740",
    ),
]


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Audit wiki and official source availability.")
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--report", type=Path, default=Path("reports/source_audits.json"))
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    register_reference_sources(conn)

    records = []
    for key in ("wiki.gg", "fandom"):
        records.extend(
            audit_mediawiki_source(
                SOURCE_DEFINITIONS[key],
                timeout=args.timeout,
            )
        )
    for source_key, check_type, url, title in OFFICIAL_HTTP_TARGETS:
        records.append(
            audit_http_endpoint(
                source_key=source_key,
                check_type=check_type,
                url=url,
                title=title,
                timeout=args.timeout,
            )
        )

    count = write_source_audits(conn, records)
    payload = summarize_source_audits(records)
    payload["records_written"] = count
    payload["records"] = [
        {
            "source_key": record.source_key,
            "check_type": record.check_type,
            "url": record.url,
            "status": record.status,
            "status_code": record.status_code,
            "allowed": record.allowed,
            "title": record.title,
            "summary": record.summary,
            "payload": record.payload,
        }
        for record in records
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
