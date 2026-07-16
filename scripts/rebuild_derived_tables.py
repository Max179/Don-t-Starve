#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.facts import rebuild_entity_facts
from dst_wiki_db.categories import rebuild_entity_categories
from dst_wiki_db.recipes import rebuild_recipe_ingredients
from dst_wiki_db.variants import rebuild_entity_variants
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
    fact_count = rebuild_entity_facts(conn)
    variant_count = rebuild_entity_variants(conn)
    category_count = rebuild_entity_categories(conn)
    payload = {
        "recipe_ingredients": recipe_count,
        "entity_facts": fact_count,
        "entity_variants": variant_count,
        "entity_categories": category_count,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
