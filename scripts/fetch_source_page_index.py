#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.schema import connect, init_db
from dst_wiki_db.source_page_gaps import rebuild_source_page_gaps
from dst_wiki_db.source_page_index import fetch_source_page_index


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch a MediaWiki source title index and match it to local entities."
    )
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--source-key", default="wiki.gg", choices=["wiki.gg", "fandom"])
    parser.add_argument("--limit", type=int, default=0, help="0 means no limit.")
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/source_page_index.json"),
    )
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    result = fetch_source_page_index(
        conn,
        source_key=args.source_key,
        limit=None if args.limit == 0 else args.limit,
        sleep_seconds=args.sleep,
    )
    result["source_page_gaps"] = rebuild_source_page_gaps(
        conn, source_key=args.source_key
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
