#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.build import SOURCE_DEFINITIONS
from dst_wiki_db.schema import connect, init_db
from dst_wiki_db.xml_dump import import_mediawiki_xml_dump


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Import a MediaWiki XML dump into the Don't Starve wiki database."
    )
    parser.add_argument("dump", type=Path, help="Path to .xml, .xml.gz, or .xml.bz2 dump.")
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument(
        "--source",
        choices=sorted(key for key in SOURCE_DEFINITIONS if key in {"wiki.gg", "fandom"}),
        default="wiki.gg",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum mainspace pages; 0 means all.")
    parser.add_argument("--include-redirects", action="store_true")
    parser.add_argument("--report", type=Path, default=Path("reports/xml_dump_import.json"))
    args = parser.parse_args(argv)

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = connect(args.db)
    init_db(conn)
    payload = import_mediawiki_xml_dump(
        conn,
        dump_path=args.dump,
        source_key=args.source,
        limit=None if args.limit == 0 else args.limit,
        include_redirects=args.include_redirects,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
