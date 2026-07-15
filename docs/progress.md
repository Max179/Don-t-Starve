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
- Source-presence verification checks: 2,252
- Official Steam/Klei verification records: 108
- Structured recipe ingredients: 1,954

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

## Remaining Work Toward The Full Goal

- Confirm permission or an approved access path for wiki.gg full API/database ingestion, then build the canonical source database.
- Expand Klei update verification when the Klei forums endpoint is reachable or an RSS/API endpoint is confirmed.
- Improve cross-source mapping beyond title slug matching using spawn code, prefab code, image hash, infobox type, and category confidence.
- Normalize remaining relationships such as drops, spawn sources, upgrades, growth stages, skins, and cooked/raw forms into dedicated relation tables.
- Store actual image files in a GitHub-friendly asset strategy. Git LFS is not installed in the current environment, so this pass stores image URLs and metadata in SQLite rather than committing thousands of binary files.
