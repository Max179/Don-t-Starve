#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.community_guides import import_community_guides
from dst_wiki_db.schema import connect, init_db


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(
        description="Import curated community guide source metadata into SQLite."
    )
    parser.add_argument(
        "seed",
        type=Path,
        nargs="?",
        default=Path("data/community_guides_seed.json"),
    )
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    result = import_community_guides(conn, args.seed)
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(payload + "\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
