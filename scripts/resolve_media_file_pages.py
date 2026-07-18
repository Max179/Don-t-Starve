#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.media_downloads import resolve_file_page_download_urls
from dst_wiki_db.media_profiles import rebuild_entity_media_profiles
from dst_wiki_db.entity_profiles import rebuild_entity_profile_json
from dst_wiki_db.schema import connect, init_db


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Resolve file-page-only media manifest rows to direct download URLs."
    )
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--source-key")
    parser.add_argument("--limit", type=_non_negative_int)
    parser.add_argument("--batch-size", type=_positive_int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-derived-refresh",
        action="store_true",
        help="Skip rebuilding media/profile JSON summaries after URL resolution.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional JSON report path for the resolver result.",
    )
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    result = resolve_file_page_download_urls(
        conn,
        source_key=args.source_key,
        limit=args.limit,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )
    if not args.dry_run and not args.skip_derived_refresh:
        result["derived_refresh"] = {
            "entity_media_profiles": rebuild_entity_media_profiles(conn),
            "entity_profile_json": rebuild_entity_profile_json(conn),
        }
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
