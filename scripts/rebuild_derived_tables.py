#!/usr/bin/env python3
from pathlib import Path
import json
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dst_wiki_db.facts import rebuild_entity_facts
from dst_wiki_db.categories import rebuild_entity_categories
from dst_wiki_db.image_variants import rebuild_image_variants
from dst_wiki_db.identity import rebuild_identity_keys
from dst_wiki_db.official_mentions import rebuild_official_record_mentions
from dst_wiki_db.page_images import rebuild_page_images
from dst_wiki_db.recipes import rebuild_recipe_ingredients
from dst_wiki_db.stats import rebuild_entity_stat_values, rebuild_entity_stats
from dst_wiki_db.targets import rebuild_entity_targets
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
    stat_count = rebuild_entity_stats(conn)
    stat_value_count = rebuild_entity_stat_values(conn)
    fact_count = rebuild_entity_facts(conn)
    variant_count = rebuild_entity_variants(conn)
    category_count = rebuild_entity_categories(conn)
    page_image_count = rebuild_page_images(conn)
    image_variant_count = rebuild_image_variants(conn)
    official_mention_count = rebuild_official_record_mentions(conn)
    identity_count = rebuild_identity_keys(conn)
    target_counts = rebuild_entity_targets(conn)
    payload = {
        "recipe_ingredients": recipe_count,
        "recipe_ingredient_targets": target_counts["recipe_ingredient_targets"],
        "entity_stats": stat_count,
        "entity_stat_values": stat_value_count,
        "entity_facts": fact_count,
        "entity_fact_targets": target_counts["entity_fact_targets"],
        "entity_relation_targets": target_counts["entity_relation_targets"],
        "entity_variants": variant_count,
        "entity_categories": category_count,
        "page_images": page_image_count,
        "image_variants": image_variant_count,
        "official_record_mentions": official_mention_count,
        "entity_identity_keys": identity_count,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
