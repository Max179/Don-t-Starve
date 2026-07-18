# Don't Starve Wiki Database

This workspace builds an auditable SQLite database for English-first Don't Starve / Don't Starve Together wiki data.

Current committed output: `data/dont_starve_wiki.sqlite` contains a full Fandom historical comparison build with 2,252 pages, 2,252 entity coverage rows, 2,252 entity JSON profiles with 22,921 embedded attribute rows, 22,921 parsed attributes, 6,866 normalized stat rows, 6,844 parsed stat value rows, 5,142 per-entity stat rollups, 409 combat profile rows, 454 food profile rows, 788 item profile rows, 249 world profile rows, 72 character profile rows, 412 creature profile rows, 783 recipe profile rows, 1,874 registered infobox images, 44,437 page-level image references, 46,311 unified entity media asset rows, 46,311 media download manifest rows, 1,224 entity media profile rows, 419 image-variant candidates, 43,734 resolved wiki-link targets, 4,502 typed gameplay relationship edges, 23,810 taxonomy tags, 12,973 category links, 8,690 identity keys for cross-source matching, 1,282 variant records, 2,982 merged entity variant summary rows, 1,954 structured recipe ingredients, 1,816 resolved recipe ingredient targets, 1,246 structured drop/source/sold/spawn facts, 435 resolved fact targets, 161 official Steam/Klei verification records, 55 normalized official product records, 223 official product media URLs, 50 normalized official update events, 80 normalized official update sections, 397 official update section items, 5 official update media URLs, 678 official-record entity mentions, 8 ranked source catalog rows, 26 source catalog evidence rows, 21 curated community guide source rows, 77 community guide topic rows, 5 community guide topic-index rows, and 9 source-access audit records. The official layer includes appdetails for all 53 Steam-listed DLC ids, with official header, capsule, and description image URLs. See [docs/progress.md](docs/progress.md).

The pipeline keeps raw MediaWiki page wikitext and parsed records side by side:

- `raw_pages`: source page evidence, revision ids, categories, templates, image references, and gzip-capable wikitext payloads. Use `dst_wiki_db.raw_pages.decode_wikitext` to read compressed `wikitext` rows.
- `entities`: canonical entry records, keyed by normalized English titles.
- `entity_sources`: cross-source page mappings.
- `entity_attributes`: infobox fields such as health, damage, attack range, speed, spawn code, recipe data, and DS/DST-specific variants.
- `entity_stats`: normalized query rows for health, damage, attack range, speed, hunger, sanity, durability, stack size, spoil time, and similar numeric or raw stat fields.
- `entity_stat_values`: per-number stat rows for multi-value fields, keeping order and local context such as player/mob damage or casual/aggressive speed.
- `entity_stat_rollups`: one row per entity/stat/type/unit summarizing min/max values, raw text variants, evidence counts, source counts, and variant counts.
- `entity_combat_profiles`: one-row combat/movement stat summaries for entities with combat or movement data, including health, damage, attack range, attack period, walk speed, run speed, raw text, and evidence counts.
- `entity_food_profiles`: one-row food/restoration summaries with health, hunger, sanity, food value, spoil time, cook time, priority, raw text, and evidence counts.
- `entity_item_profiles`: one-row item/equipment summaries with damage, durability, protection, water resistance, stack, stack limit, burn time, tier, resources, renew, priority, raw text, and item-card flags.
- `entity_world_profiles`: one-row plant/structure/biome summaries with biome, spawn codes, renewability, resources, tool, perk, special ability, growth/season text, and world-object combat stats.
- `entity_character_profiles`: one-row character summaries with nicknames, mottos, birthdays, gender/species/voice/games, spawn codes, perks, survivability, bio, favorite food, start items, character items, and core health/hunger/sanity/damage stats.
- `entity_creature_profiles`: one-row mob/boss summaries with biome, spawn codes, special abilities, perks, drops, spawn facts, combat/movement stats, sanity effects, and gameplay relationship counts.
- `entity_recipe_profiles`: one-row crafting/cooking summaries with ingredient slots, resolved ingredient targets, reverse used-in links, recipe counts, and JSON details for direct crafting cards.
- `entity_images`: infobox image names, roles, variants, URLs, hashes, dimensions, and optional local files.
- `page_images`: page-level image references from MediaWiki metadata, including gallery, page, and transcluded file references with source file-page URLs.
- `image_variants`: filename-derived image variant candidates such as build, burnt, phase, animation, crop growth, and oversized crop forms.
- `entity_media_assets`: unified infobox/page media rows with URLs, file pages, primary flags, and variant metadata.
- `entity_media_downloads`: media download manifest rows with deterministic target paths, URL status, priority, queue reasons, and downloader status fields.
- `entity_media_profiles`: one-row media summaries for entities with images, including primary image metadata, direct/file-page/missing URL counts, download-state counts, variant image counts, and compact primary/variant JSON arrays.
- `entity_relations`: wiki links with resolved `target_entity_id` values when the target exists in `entities`.
- `recipe_ingredient_targets`: entity bridges from crafted entries to ingredient entries.
- `entity_fact_targets`: entity bridges for parsed drops, dropped-by, sold-by, spawn-from, and spawns facts.
- `entity_gameplay_edges`: typed forward and inverse gameplay relationships for ingredients, drops, sellers, and spawn relationships.
- `entity_taxonomy`: multi-label kind, source category, gameplay, DLC/game-mode, and data-availability tags for filtering and faceted browsing.
- `entity_coverage`: per-entry coverage score, evidence counts, and missing-data summary for triage.
- `entity_variant_summary`: merged per-entry variant evidence across attributes, stats, recipes, facts, explicit variants, and media assets.
- `entity_profile_json`: one compressed JSON profile per entity for direct wiki/API consumption, aggregating identity, coverage, raw/normalized infobox attributes, media, media profile, stats, stat rollups, combat profile, food profile, item profile, world profile, character profile, creature profile, recipe profile, variants, categories, facts, recipes, typed relationships, taxonomy, and official mentions. Use `dst_wiki_db.entity_profiles.load_profile_json` to decode `profile_json`.
- `verification_checks`: source-presence and cross-source verification records.
- `official_records`: official Steam/Klei products, DLC listings, DLC appdetails, update posts, and page probes with source payloads.
- `official_products`: queryable Steam product facts derived from official appdetails records.
- `official_product_media`: official product image URLs from Steam media fields and product descriptions.
- `official_update_events`: queryable Steam news/update events with dates, authors, event type, text, and mention counts.
- `official_update_sections`: ordered headings and bodies parsed from official update event text.
- `official_update_section_items`: sentence-like patch-note items linked to their event and section.
- `official_update_media`: official update image URLs extracted from Steam news content.
- `official_record_mentions`: high-confidence links from official Steam/Klei records back to matching wiki entities.
- `source_audits`: robots, API, and official-source availability checks.
- `source_catalog`: ranked wiki, official, competitor, and community-signal source candidates.
- `source_catalog_evidence`: search, official, audit, and manual-review evidence for each ranked source.
- `community_guide_sources`: curated Chinese community guide metadata for Bilibili, Zhihu, Gamersky, TapTap, and Xiaohongshu discovery.
- `community_guide_topics`: topic tags for guide sources.
- `community_guide_topic_index`: recommended source ids and verification reminders for beginner, food, farming, caves, and boss guide themes.

## Source Strategy

The current source ranking is also stored in `source_catalog`:

1. `wiki.gg` Don't Starve Wiki: canonical community wiki, largest current coverage.
2. Klei official site/forums: official verification for updates, releases, and mechanics changes.
3. Steam Store / Steam Web API: official product metadata and DLC verification.
4. Fandom Don't Starve Wiki: historical comparison and cross-source checks.
5. Fextralife Don't Starve Wiki: competitor/reference-only coverage check.
6. Wikipedia: general product context only.
7. Reddit/r/dontstarve: source-discovery signal only.
8. PatchBot: update-discovery signal only, verified back to official sources before use.

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
rm -f data/dont_starve_wiki.sqlite reports/coverage.json reports/inspect.json reports/source_audits.json
rm -rf data/images
```

Audit sources and inspect the output:

```bash
python3 scripts/audit_sources.py \
  --db data/dont_starve_wiki.sqlite \
  --report reports/source_audits.json
python3 scripts/inspect_database.py data/dont_starve_wiki.sqlite
```

Resolve a small batch of file-page-only media rows into direct URLs:

```bash
python3 scripts/resolve_media_file_pages.py \
  --db data/dont_starve_wiki.sqlite \
  --source-key fandom \
  --limit 250 \
  --batch-size 50 \
  --report reports/media_file_page_resolution.json
```

By default this also refreshes `entity_media_profiles` and `entity_profile_json` so media URL counts in profile payloads stay in sync with resolved file-page URLs.

Download a small batch of direct media URLs from the manifest:

```bash
python3 scripts/download_media_assets.py \
  --db data/dont_starve_wiki.sqlite \
  --output-root . \
  --limit 25 \
  --dry-run \
  --report reports/media_downloads.json
```

Remove `--dry-run` to write files under the manifest's `data/images/{source_key}/{entity_slug}/{image_slug}` paths. Downloaded binary files remain ignored by git; commit the database/report metadata, not the image payloads.

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

## Import An Approved XML Dump

If wiki.gg or another approved source provides a MediaWiki XML dump, import it without using the restricted wiki.gg API:

```bash
python3 scripts/import_xml_dump.py path/to/dump.xml.bz2 \
  --db data/dont_starve_wiki.sqlite \
  --source wiki.gg \
  --limit 0 \
  --report reports/xml_dump_import.json
python3 scripts/rebuild_derived_tables.py \
  --db data/dont_starve_wiki.sqlite \
  --report reports/derived_tables.json
```

The importer supports `.xml`, `.xml.gz`, and `.xml.bz2`, reads main-namespace non-redirect pages by default, and writes into the same raw/entity/attribute/image/category structures as the API importer.

## Current Limitations

- The parser is infobox-first and stores raw field names, canonical field names, numeric values, and variant keys. Stats, recipe ingredients, selected drop/source/sold/spawn facts, categories, variants, and identity keys are normalized into derived tables, but some relationship families still need dedicated tables.
- Infobox image rows remain the primary entity-image table. Page, gallery, and transcluded image references are stored separately in `page_images`; filename-derived alternates are stored in `image_variants` as candidates with match method and confidence.
- Cross-source matching is ready to use title, spawn-code, image-name, and image-hash identity keys. The committed snapshot has only one wiki source, so `cross_source_matches` stays empty until wiki.gg or another wiki source is ingested.
- Official Klei and Steam sources are registered as verification sources and source-audited. Steam product/DLC appdetails and Steam news records now retain normalized product facts, update events, media URLs, and entity mentions. More granular patch-note change tables still need expansion.
