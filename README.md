# Don't Starve Wiki Database

This workspace builds an auditable SQLite database for English-first Don't Starve / Don't Starve Together wiki data.

Current committed output: `data/dont_starve_wiki.sqlite` contains a full Fandom historical comparison build with 2,252 pages, 22,921 parsed attributes, 1,874 registered infobox images, 12,973 category links, 1,282 variant records, 1,954 structured recipe ingredients, 1,246 structured drop/source/sold/spawn facts, and 108 official Steam/Klei verification records. See [docs/progress.md](docs/progress.md).

The pipeline keeps raw MediaWiki page wikitext and parsed records side by side:

- `raw_pages`: source page evidence, revision ids, categories, templates, image references.
- `entities`: canonical entry records, keyed by normalized English titles.
- `entity_sources`: cross-source page mappings.
- `entity_attributes`: infobox fields such as health, damage, attack range, speed, spawn code, recipe data, and DS/DST-specific variants.
- `entity_images`: image names, roles, variants, URLs, hashes, dimensions, and optional local files.
- `entity_relations`: wiki links and future relationship facts.
- `verification_checks`: source-presence and cross-source verification records.

## Source Strategy

The current source ranking is:

1. `wiki.gg` Don't Starve Wiki: canonical community wiki, largest current coverage.
2. Klei official site/forums: official verification for updates, releases, and mechanics changes.
3. Steam Store / Steam Web API: official product metadata and DLC verification.
4. Fandom Don't Starve Wiki: historical comparison and cross-source checks.

Important: public research found that wiki.gg robots rules restrict `/api.php`. This project supports wiki.gg API ingestion, but the CLI skips that source unless `--allow-restricted-api` is passed. Only use that flag if you have permission or an acceptable data-access arrangement. Fandom is useful for testing the pipeline and historical comparison, but it should not be treated as the primary source of truth.

See [docs/sources.md](docs/sources.md) for source details and links.

## Install

```bash
python3 -m pip install -r requirements.txt
```

## Build In GitHub, Not Locally

Generated databases, image assets, caches, and reports are ignored by git in this workspace. Use the manual GitHub Actions workflow, **Build wiki database**, to create the SQLite database and optional image downloads on GitHub runners. The workflow uploads the result as a GitHub artifact named `dont-starve-wiki-database`.

Recommended workflow inputs for a small verification run:

- `sources`: `fandom`
- `limit`: `25`
- `download_images`: `none`
- `allow_restricted_api`: `false`

After wiki.gg API permission is confirmed, use:

- `sources`: `wiki.gg fandom`
- `limit`: `0`
- `download_images`: `primary` or `all`
- `allow_restricted_api`: `true`

## Optional Local Smoke Test

This builds a small Fandom comparison database without downloading images:

```bash
python3 scripts/build_database.py \
  --db data/dont_starve_wiki.sqlite \
  --sources fandom \
  --limit 25 \
  --download-images none \
  --coverage reports/coverage.json
```

The generated local files are ignored by git. Remove them after a smoke test if you want the machine clean:

```bash
rm -f data/dont_starve_wiki.sqlite reports/coverage.json reports/inspect.json
rm -rf data/images
```

Inspect the output:

```bash
python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite
```

Run tests:

```bash
python3 -m pytest -q
```

## Full Canonical Build On GitHub

After wiki.gg API permission is confirmed, run the GitHub workflow with:

- `sources`: `wiki.gg fandom`
- `limit`: `0`
- `download_images`: `primary`
- `allow_restricted_api`: `true`

`--limit 0` means all pages. Until permission is confirmed, use small positive limits for verification.

## Current Limitations

- The parser is infobox-first and stores raw field names, canonical field names, numeric values, and variant keys. It does not yet fully normalize all recipe/drops/spawn relationships.
- Image rows are registered from infobox image fields first. Page gallery and navbox images are intentionally not treated as primary entity images.
- Cross-source mapping currently uses normalized title slugs. Future passes should add spawn code, prefab code, image hash, and template/category confidence scoring.
- Official Klei and Steam sources are registered as verification sources but are not yet ingested into structured update/product tables.
