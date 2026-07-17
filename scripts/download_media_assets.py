#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.media_downloads import download_pending_media
from dst_wiki_db.schema import connect, init_db


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Download pending direct media URLs from entity_media_downloads."
    )
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("."),
        help="Base directory for manifest target_path values; use repo root by default.",
    )
    parser.add_argument("--limit", type=_non_negative_int)
    parser.add_argument("--timeout", type=_positive_int, default=30)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional JSON report path for the downloader result.",
    )
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    result = download_pending_media(
        conn,
        output_root=args.output_root,
        limit=args.limit,
        timeout=args.timeout,
        dry_run=args.dry_run,
    )
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n")
    print(payload)
    return 0


def _positive_int(value: str) -> int:
    parsed = int(value)
    if parsed < 1:
        raise ValueError("expected a positive integer")
    return parsed


def _non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise ValueError("expected a non-negative integer")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
