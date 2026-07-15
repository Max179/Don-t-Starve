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

## Remaining Work Toward The Full Goal

- Confirm permission or an approved access path for wiki.gg full API/database ingestion, then build the canonical source database.
- Add structured official verification tables for Klei update posts and Steam app/DLC metadata.
- Improve cross-source mapping beyond title slug matching using spawn code, prefab code, image hash, infobox type, and category confidence.
- Normalize relationships such as recipes, drops, spawn sources, upgrades, growth stages, skins, and cooked/raw forms into dedicated relation tables.
- Store actual image files in a GitHub-friendly asset strategy. Git LFS is not installed in the current environment, so this pass stores image URLs and metadata in SQLite rather than committing thousands of binary files.
