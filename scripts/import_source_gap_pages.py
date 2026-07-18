#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.schema import connect, init_db
from dst_wiki_db.source_gap_import import import_source_gap_pages


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Import a small batch of unmatched source pages as parsed wiki entities."
    )
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--source-key", default="wiki.gg", choices=["wiki.gg", "fandom"])
    parser.add_argument("--gap-type", default="potential_new_entity")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("reports/source_gap_import.json"),
    )
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    result = import_source_gap_pages(
        conn,
        source_key=args.source_key,
        gap_type=args.gap_type,
        limit=args.limit,
        batch_size=args.batch_size,
        sleep_seconds=args.sleep,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
