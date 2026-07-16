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
- Normalized stat rows: 6,866
- Parsed stat value rows: 6,844
- Registered infobox images: 1,874
- Registered images with fetched URL metadata: 1,785
- Page-level image references: 44,437
- Entities with page-level image references: 275
- Image-variant candidates: 419
- Wiki-link relations: 58,997
- Resolved wiki-link targets: 43,734
- Source-presence verification checks: 2,252
- Official Steam/Klei verification records: 108
- Official-record entity mentions: 292
- Structured recipe ingredients: 1,954
- Resolved recipe ingredient targets: 1,816
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

The database now also includes an `official_record_mentions` table that links official Steam/Klei records back to matching wiki entities by conservative title-phrase matching. This pass generated 292 official-record entity mentions:

- `steam:news`: 176
- `steam:steam_dlc_id`: 102
- `steam:appdetails`: 9
- `klei:http_probe`: 5

Top matched entities include:

- `Don't Starve`: 74
- `Don't Starve Together`: 55
- `Klei Entertainment`: 13
- `WX-78`: 9
- `The Constant`: 8
- `Wilson`: 5
- `Beefalo`: 4
- `Wheeler`: 4
- `Wormwood`: 4

The matcher skips generic single-word non-creature entries such as `Time`, `Things`, and `Farm`; those three currently have 0 official mentions after filtering.

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

This pass generated 1,954 structured ingredient rows and 1,816 exact ingredient-to-entity target bridges. Examples verified in the current database:

- `Alchemy Engine`: Boards x4, Cut Stone x2, Gold Nugget x6
- `Anchor`: Boards x2, Rope x3, Cut Stone x3
- `Alarming Clock`: Time Pieces x3, Marble x4, Nightmare Fuel x8

## Derived Stats Table

The database now includes an `entity_stats` table derived from parsed infobox attributes. It keeps raw text and source provenance, normalizes stat names, groups rows by stat type, assigns units, and preserves variant keys such as DS/DST or numbered food forms. It also includes `entity_stat_values`, a child table that splits multi-value stat text into ordered numeric rows with local context.

This pass generated 6,866 normalized stat rows:

- `item`: 3,203
- `combat`: 1,245
- `survival`: 1,216
- `food`: 651
- `movement`: 453
- `stat`: 98

It also generated 6,844 parsed stat value rows. Top value-bearing stat names include:

- `tier`: 702
- `health`: 646
- `damage`: 531
- `stack`: 495
- `durability`: 426
- `resources`: 418
- `sanity_restored`: 376
- `burn_time`: 357
- `spoil`: 350
- `walk_speed`: 280

Top normalized stat names include:

- `stack`: 1,145
- `tier`: 716
- `health`: 615
- `damage`: 384
- `spoil`: 377
- `durability`: 371
- `walk_speed`: 252
- `attack_period`: 214
- `run_speed`: 201
- `attack_range`: 176

Examples verified in the current database:

- `Ancient Guardian`: health 2,500, DST health 10,000, damage 100, attack ranges 25 and 4.6, attack period 2 seconds, run speed 17, walk speed 5
- `Antlion`: damage values 50, 75, and 100 to player plus 100, 150, and 200 to mobs are split into ordered child rows
- `Bearger`: walk speed values 3 (casual) and 6 (aggressive) are split into separate child rows with context
- `Bee`: health 100, damage 10, attack range 0.6, attack periods 2 and 3 seconds, walk speed 4, run speed 6
- `Carrot`: food health/hunger/sanity/spoil stats keep raw/cooked variant keys; food value now parses `32px|link=Vegetables × 1` as 1.0 instead of the icon size
- `Berries`: food value now parses `32px|link=Fruit × 0.5` as 0.5

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
- `recipe_ingredient_targets`: 1,816 recipe ingredient rows now point at ingredient entities.
- `entity_fact_targets`: 435 parsed drops, dropped-by, sold-by, spawn-from, and spawns rows now have target entity bridges.

Examples verified in the current database:

- `'The Sty' Oddities Emporium` recipe ingredient -> `Boards`, `Ball Pein Hammer`, and `Pig Skin`
- `Abigail's Flower` recipe ingredient -> `Mourning Glory` and `Nightmare Fuel`
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

## Derived Page Image Index

The database now includes a `page_images` table derived from each raw MediaWiki page's `images_json`. This table is separate from `entity_images`: `entity_images` keeps infobox image roles and fetched image metadata, while `page_images` records broader page-level file references from article content, galleries, navboxes, and transcluded templates.

This pass generated 44,437 page-level image references across 275 entities.

Examples verified in the current database:

- `Alchemy Engine`: `Alchemy Engine.png`, `Alchemy Engine Build.png`, `Alchemy Engine Burnt.png`, and related crafting/gallery references
- `Ancient Guardian`: `Ancient Guardian.png`, `Ancient Guardian Phase 2.png`, and related figure/art references
- File-page URLs are stored as source-specific `description_url` values, for example `https://dontstarve.fandom.com/wiki/File:Alchemy_Engine.png`

## Derived Image Variant Candidates

The database now includes an `image_variants` table derived from `page_images`. It detects page images whose filenames start with the owning entity slug, excludes exact matches that are already separate entity titles, and stores the candidate's variant key, variant type, match method, and confidence.

This pass generated 419 image-variant candidates:

- `visual_variant`: 339
- `animation`: 26
- `build_state`: 23
- `growth_stage`: 12
- `map_icon`: 5
- `state`: 5
- `oversized_form`: 4
- `reference_asset`: 4
- `phase`: 1

Examples verified in the current database:

- `Alchemy Engine`: `Alchemy Engine Build.png` as `build_state`, `Alchemy Engine Burnt.png` as `state`
- `Ancient Guardian`: `Ancient Guardian Phase 2.png` as `phase`
- `Carrot`: `Carrot Plant Seed/Small/Med/Full/Sprout.png` as `growth_stage`, oversized plant images as `oversized_form`
- `Corn`: `Corn Stalk Seed/Small/Med/Full/Sprout.png` as `growth_stage`, oversized stalk images as `oversized_form`
- `Bee Box.png` is not counted as a Bee image variant because `Bee Box` is its own entity

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
