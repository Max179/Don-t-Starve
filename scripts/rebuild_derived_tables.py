#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.recipes import rebuild_recipe_ingredients
from dst_wiki_db.schema import connect, init_db


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="Rebuild derived tables from parsed wiki attributes.")
    parser.add_argument("--db", type=Path, default=Path("data/dont_starve_wiki.sqlite"))
    parser.add_argument("--report", type=Path, default=Path("reports/derived_tables.json"))
    args = parser.parse_args(argv)

    conn = connect(args.db)
    init_db(conn)
    recipe_count = rebuild_recipe_ingredients(conn)
    payload = {"recipe_ingredients": recipe_count}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
