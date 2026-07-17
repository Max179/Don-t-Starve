#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.raw_pages import compress_raw_page_wikitexts
from dst_wiki_db.schema import connect, init_db


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Compress raw_pages.wikitext payloads and vacuum the SQLite DB."
    )
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument(
        "--no-vacuum",
        action="store_true",
        help="Skip VACUUM after updating rows.",
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    before_size = args.db.stat().st_size if args.db.exists() else 0
    conn = connect(args.db)
    init_db(conn)
    compressed = compress_raw_page_wikitexts(conn)
    if not args.no_vacuum:
        conn.execute("vacuum")
    conn.execute("pragma optimize")
    after_size = args.db.stat().st_size if args.db.exists() else 0
    payload = {
        "compressed_raw_pages": compressed,
        "before_bytes": before_size,
        "after_bytes": after_size,
        "saved_bytes": before_size - after_size,
        "vacuumed": not args.no_vacuum,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
