#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.report import database_counts, sample_entities
from dst_wiki_db.schema import connect, init_db


def main(argv=None):
    args = argv or sys.argv[1:]
    if len(args) != 1:
        print("Usage: scripts/inspect_database.py path/to/wiki.sqlite", file=sys.stderr)
        return 2
    conn = connect(args[0])
    init_db(conn)
    payload = {
        "counts": database_counts(conn),
        "sample_entities": sample_entities(conn, limit=20),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
