#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.official import fetch_klei_records, fetch_steam_records, write_official_records
from dst_wiki_db.schema import connect, init_db


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Fetch official Steam/Klei verification records.")
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--steam-news-count", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--report", type=Path, default=Path("reports/official_sources.json"))
    parser.add_argument(
        "--skip-steam-dlc-details",
        action="store_true",
        help="Only store parent-listed DLC ids; skip individual Steam DLC appdetails requests.",
    )
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    records = []
    records.extend(
        fetch_steam_records(
            appids=[322330, 219740, 2239770],
            news_count=args.steam_news_count,
            timeout=args.timeout,
            include_dlc_details=not args.skip_steam_dlc_details,
        )
    )
    records.extend(fetch_klei_records(timeout=args.timeout))
    count = write_official_records(conn, records)

    payload = {
        "records_written": count,
        "by_provider": {},
        "by_type": {},
    }
    for record in records:
        payload["by_provider"][record.provider] = payload["by_provider"].get(record.provider, 0) + 1
        key = f"{record.provider}:{record.record_type}"
        payload["by_type"][key] = payload["by_type"].get(key, 0) + 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
