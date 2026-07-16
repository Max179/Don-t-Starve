# Current Database Progress

Last updated: 2026-07-16 Asia/Shanghai.

## Committed Database

The repository now includes a generated SQLite database at `data/dont_starve_wiki.sqlite` built from the Fandom Don't Starve Wiki as a historical comparison source.

Build command:

```bash
python3 scripts/build_database.py \
  --db data/dont_starve_wiki.sqlite \
  --sources fandom \
  --limit 0 \
  --batch-size 25 \
  --sleep 0.05 \
  --download-images none \
  --coverage reports/coverage.json
```

Coverage:

- Raw pages: 2,252
- Entities: 2,252
- Source mappings: 2,252
- Parsed attributes: 22,921
- Registered infobox images: 1,874
- Registered images with fetched URL metadata: 1,785
- Wiki-link relations: 58,997
- Resolved wiki-link targets: 43,734
- Source-presence verification checks: 2,252
- Official Steam/Klei verification records: 108
- Structured recipe ingredients: 1,954
- Structured drop/source/sold/spawn facts: 1,246
- Resolved drop/source/sold/spawn fact targets: 435
- Variant records: 1,282
- Entity category links: 12,973
- Entities with category links: 2,190
- Distinct category slugs: 288
- Identity keys for source alignment: 8,690
- Source-access audit records: 9

Entity kind distribution:

- `item`: 787
- `page`: 520
- `mob`: 286
- `structure`: 205
- `boss`: 159
- `character`: 135
- `food`: 61
- `biome`: 53
- `plant`: 46

## Verified Parser Improvements

Some wiki pages contain repeated infoboxes for variants or alternate forms. For example, Abigail has multiple `Mob Infobox` blocks. The schema now records `template_index` on `entity_attributes`, so repeated fields such as `health` and `damage` are preserved instead of overwritten or rejected.

The entity classifier now prefers infobox type over loose categories. This fixes cases such as:

- `Abigail`: `mob`, not `character`
- `Abigail's Flower`: `item`, not `character`
- `Ageless Watch`: `item`, not `character`

## Official Verification Layer

The database now includes an `official_records` table populated by:

```bash
python3 scripts/fetch_official_sources.py \
  --db data/dont_starve_wiki.sqlite \
  --steam-news-count 25 \
  --timeout 30 \
  --report reports/official_sources.json
```

Official records currently include:

- Steam appdetails: 2 records (`Don't Starve`, `Don't Starve Together`)
- Steam DLC ids: 53 records
- Steam news/update records: 50 records
- Klei official page probes: 3 records

Klei page probe statuses:

- `https://www.klei.com/games/dont-starve`: `ok`
- `https://www.klei.com/games/dont-starve-together`: `ok`
- `https://forums.kleientertainment.com/game-updates/dst/`: `failed` during this run because the endpoint returned a Cloudflare 502 page. The failure is stored in `official_records` instead of being hidden.

## Derived Recipe Table

The database now includes a `recipe_ingredients` table derived from parsed infobox attributes:

```bash
python3 scripts/rebuild_derived_tables.py \
  --db data/dont_starve_wiki.sqlite \
  --report reports/derived_tables.json
```

This pass generated 1,954 structured ingredient rows. Examples verified in the current database:

- `Alchemy Engine`: Boards x4, Cut Stone x2, Gold Nugget x6
- `Anchor`: Boards x2, Rope x3, Cut Stone x3
- `Alarming Clock`: Time Pieces x3, Marble x4, Nightmare Fuel x8

## Derived Relation Facts

The database now includes an `entity_facts` table derived from relation-like infobox fields:

- `drops`
- `dropped_by`
- `sold_by`
- `spawn_from`
- `spawns`

This pass generated 1,246 rows:

- `dropped_by`: 483
- `drops`: 437
- `spawn_from`: 125
- `sold_by`: 122
- `spawns`: 79

The table preserves the original value text and extracts targets, percentages, and quantities when possible. Examples verified in the current database:

- `Cave Spider` drops Monster Meat at 50%, Silk at 25%, and Spider Gland at 25%.
- `Clockwork Knight` drops Gears x2.
- `Blue Whale` drops Raw Fish x4 and Blubber x4.
- `Ancient Key` is recorded as obtained from Mumsy / Coin x3.

## Entity Target Resolution

The database now resolves parsed targets back to entity IDs where the normalized target title matches an existing entry:

- `entity_relations.target_entity_id`: 43,734 wiki-link relation rows now point at target entities.
- `entity_fact_targets`: 435 parsed drops, dropped-by, sold-by, spawn-from, and spawns rows now have target entity bridges.

Examples verified in the current database:

- `Abigail's Flower` `dropped_by` -> `Abigail`
- `Ancient Key` `dropped_by` -> `Mumsy` and `Coin`
- `Beard Hair` `dropped_by` -> `Wilson`
- `Berries` `dropped_by` -> `Berry Bush`
- `Blue Gem` `dropped_by` -> `Ancient Statue` and `Pick/Axe`

## Derived Variant Table

The database now includes an `entity_variants` table derived from explicit variant keys, image roles, growth stage fields, DS/DST fields, and repeated infobox instances.

This pass generated 1,282 rows:

- `infobox_instance`: 617
- `game_scope`: 323
- `numbered_variant`: 307
- `growth_stage`: 35

Examples verified in the current database:

- `Wilson`: `ds` game-scope variant from `image ds`
- `Carrot`: growth-stage variants `seed`, `sprout`, `small`, `med`
- `Aloe`: numbered variants `1` and `2` from health/form fields
- `Abigail`: repeated `Mob Infobox` variants are preserved as `template:1` and `template:2`

Recipe slots such as `ingredient1` and `ingredient2` are deliberately excluded from variants and live in `recipe_ingredients`.

## Derived Category Index

The database now includes an `entity_categories` table derived from each raw MediaWiki page's `categories_json`. It preserves source and raw-page provenance while exposing normalized category slugs for filtering and cross-source alignment.

This pass generated 12,973 category links across 2,190 entities and 288 distinct category slugs.

Top categories in the current database include:

- `Items`: 977
- `Don't Starve Together`: 872
- `Craftable Items`: 496
- `Mobs`: 279
- `Structures`: 278
- `Food`: 184
- `Craftable Structures`: 165

Examples verified in the current database:

- `Wilson`: Characters, Lore, Wilson
- `Alchemy Engine`: Craftable Structures, Science, Structures, Prototypers, Science Tier 1
- `Carrot`: Food, Items, Mob Dropped Items, Plants, Vegetables
- `Cave Spider`: Cave Creatures, Hostile Creatures, Mobs, Monsters, Spiders

## Cross-Source Identity Keys

The database now includes an `entity_identity_keys` table and a `cross_source_matches` table. `entity_identity_keys` is populated from source-title slugs, spawn codes, image names, and image SHA1 hashes. It provides stable evidence for matching the same entity across wiki.gg, Fandom, and any future source imports.

This pass generated 8,690 identity keys:

- `spawn_code`: 2,779
- `title_slug`: 2,252
- `image_name`: 1,874
- `image_sha1`: 1,785

Examples verified in the current database:

- `Anchor`: `title_slug=anchor`, `spawn_code=anchor_item`, `spawn_code=anchor`, and two image SHA1 keys
- `Alchemy Engine`: `spawn_code=researchlab2`
- `Abigail`: `spawn_code=abigail` and two image SHA1 keys
- `Wilson`: `title_slug=wilson` and image SHA1 key

`cross_source_matches` is currently empty because the committed snapshot contains one wiki source (`fandom`). Once wiki.gg is ingested, shared identity keys will be used to populate cross-source matches.

## Source Access Audit

The database now includes a `source_audits` table populated by:

```bash
python3 scripts/audit_sources.py \
  --db data/dont_starve_wiki.sqlite \
  --timeout 30 \
  --report reports/source_audits.json
```

This pass generated 9 source-access records:

- `wiki.gg`: 2 records
- `fandom`: 2 records
- `klei`: 3 records
- `steam`: 2 records

Status distribution:

- `ok`: 6
- `restricted_by_robots`: 1
- `failed`: 2

Latest audit observations:

- wiki.gg `robots.txt` returned HTTP 200 and explicitly disallows `/api.php`; the audit records wiki.gg API siteinfo as `restricted_by_robots` and does not fetch it by default.
- Fandom `api.php` siteinfo returned HTTP 200 with 2,252 articles and 25,319 images; Fandom `robots.txt` returned HTTP 403 through Cloudflare during this audit.
- Klei product pages for Don't Starve and Don't Starve Together returned HTTP 200; the Klei DST update forum returned HTTP 403 during this audit.
- Steam appdetails probes for app ids `322330` and `219740` returned HTTP 200.

## Approved XML Dump Import Path

The project now includes a MediaWiki XML dump importer for an approved canonical source dump:

```bash
python3 scripts/import_xml_dump.py path/to/dump.xml.bz2 \
  --db data/dont_starve_wiki.sqlite \
  --source wiki.gg \
  --limit 0 \
  --report reports/xml_dump_import.json
```

The importer supports `.xml`, `.xml.gz`, and `.xml.bz2`, streams main-namespace non-redirect pages, stores XML `siteinfo` on the selected source, and writes each page through the same parser and schema used by the API importer. It registers raw pages, canonical entities, infobox attributes, infobox images, wiki links, categories, templates, and source provenance. After importing a real dump, run `scripts/rebuild_derived_tables.py` to rebuild recipes, facts, variants, categories, identity keys, and cross-source matches.

Latest wiki.gg discovery probe:

- `/sitemap.xml`: no usable sitemap XML exposed.
- `/sitemap_index.xml`: no usable sitemap XML exposed.
- `/dump.xml`: no usable XML dump exposed; a GET probe hit a wiki.gg rate-limit/interstitial page.
- `Special:Statistics`, `Special:AllPages`, and normal article pages responded to lightweight HEAD probes, but Special pages remain unsuitable as a bulk ingestion path.

## Remaining Work Toward The Full Goal

- Confirm permission or obtain an approved wiki.gg XML dump/API access path, then build the canonical source database.
- Expand Klei update verification when the Klei forums endpoint is reachable or an RSS/API endpoint is confirmed.
- Improve cross-source mapping beyond title slug matching using spawn code, prefab code, image hash, infobox type, and category confidence.
- Normalize remaining relationships such as upgrades, skins, cooked/raw form labels, and more advanced fuzzy/alias target matching into dedicated relation tables.
- Store actual image files in a GitHub-friendly asset strategy. Git LFS is not installed in the current environment, so this pass stores image URLs and metadata in SQLite rather than committing thousands of binary files.
