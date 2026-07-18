# Current Database Progress

Last updated: 2026-07-19 Asia/Shanghai.

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
- Entity coverage rows: 2,252
- Entity JSON profiles: 2,252
- Source mappings: 2,252
- Parsed attributes: 22,921
- Embedded profile attribute rows: 22,921
- Normalized stat rows: 6,866
- Parsed stat value rows: 6,844
- Registered infobox images: 1,874
- Registered images with fetched URL metadata: 1,785
- Page-level image references: 44,437
- Unified entity media assets: 46,311
- Entity media profile rows: 1,224
- Entities with page-level image references: 275
- Image-variant candidates: 419
- Wiki-link relations: 58,997
- Resolved wiki-link targets: 43,734
- Entity link profile rows: 2,198
- Entity prefab profile rows: 1,647
- Source-presence verification checks: 2,252
- Official Steam/Klei verification records: 161
- Steam DLC appdetails records: 53
- Normalized official product records: 55
- Official product media URLs: 223
- Normalized official update events: 50
- Normalized official update sections: 80
- Official update section items: 397
- Official update media URLs: 5
- Official-record entity mentions: 678
- Ranked source catalog rows: 8
- Source catalog evidence rows: 26
- Structured recipe ingredients: 1,954
- Resolved recipe ingredient targets: 1,816
- Structured drop/source/sold/spawn facts: 1,246
- Resolved drop/source/sold/spawn fact targets: 435
- Variant records: 1,282
- Merged entity variant summary rows: 2,982
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

## Entity Coverage Audit

The database now includes an `entity_coverage` table with one row per entity. It summarizes source mappings, raw page evidence, attributes, stats, image coverage, variants, categories, relation targets, fact targets, recipe targets, official mentions, a 0-100 coverage score, and a pipe-delimited missing-data summary.

Coverage score distribution:

- 90: 13 entities
- 80: 197 entities
- 70: 457 entities
- 60: 691 entities
- 50: 360 entities
- 40: 152 entities
- 30: 330 entities
- 20: 39 entities
- 10: 13 entities

Average coverage score by entity kind:

- `structure`: 66.63 across 205 entities
- `mob`: 62.13 across 286 entities
- `item`: 61.93 across 787 entities
- `food`: 61.80 across 61 entities
- `plant`: 61.09 across 46 entities
- `boss`: 59.81 across 159 entities
- `character`: 51.48 across 135 entities
- `biome`: 48.49 across 53 entities
- `page`: 37.48 across 520 entities

Current high-priority missing dimensions:

- Entities missing image coverage: 1,028
- Entities missing stat rows: 685
- Entities missing variant rows: 1,782
- Entities missing official mentions: 2,106
- Entities missing source mappings: 0

Examples with 90/100 coverage include `Abigail's Flower`, `Battle Call Canister`, `Bundling Wrap`, `Deconstruction Staff`, `Ghost`, `Grave`, `Hound`, `Meat`, `Midsummer Cawnival`, and `Royal Tapestry`.

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
- Steam DLC appdetails: 53 records
- Steam news/update records: 50 records
- Klei official page probes: 3 records

All 53 Steam DLC appdetails requests succeeded. Each record preserves its parent appid and the official Steam data payload. All 53 records contain both `header_image` and `capsule_image` URLs. Examples include:

- `Don't Starve Soundtrack` (`219750`)
- `Don't Starve Together: Starter Pack 2026` (`4211520`)
- `Don't Starve Together: Blooming Verdant Chest` (`2377640`)
- `Don't Starve Together: Complete Roseate Chest` (`3155070`)

The database now also includes `official_products` and `official_product_media` derived from Steam appdetails records. The product table generated 55 normalized rows:

- `dlc`: 52
- `game`: 2
- `music`: 1

The official media table generated 223 image URL rows:

- `description_image`: 58
- `capsule_image`: 55
- `capsule_imagev5`: 55
- `header_image`: 55

Examples verified in the current database:

- `Don't Starve Together` (`322330`): official game product row with Steam short description and direct media URLs.
- `Don't Starve Together: Starter Pack 2026` (`4211520`): parent app `322330`, parent title `Don't Starve Together`, and 8 description images plus header/capsule media.
- `Don't Starve Soundtrack` (`219750`): product type `music`, parent app `219740`, and soundtrack-specific description images.

Steam news records are also normalized into `official_update_events` and `official_update_media`. This pass generated 50 update/event rows and 5 valid Steam clan image URLs. Event type distribution:

- `announcement`: 18
- `hotfix`: 14
- `update`: 11
- `event`: 6
- `milestone`: 1

44 of the 50 update rows have at least one linked wiki entity mention through `official_record_mentions`. Examples verified in the current database:

- `Hotfix 740477`: `hotfix`, published `2026-07-06T22:58:25Z`, author `JesseB_Klei`.
- `Midsummer Cawnival is Back!`: `event`, published `2026-06-25T18:37:41Z`, 3 mentioned entities.
- `Don't Starve Together: From Beyond - Cursed Confrontation Pt. 1 & Klei Fest 2026`: `event`, 8 mentioned entities.
- `Don't Starve Together peaks at 122k players`: `milestone`, source author `SteamDB`.

Official update text is also split into 80 ordered section rows and 397 searchable item rows. Section distribution:

- `body`: 23 sections, 122 items
- `bug_fixes`: 18 sections, 129 items
- `changes`: 13 sections, 37 items
- `introduction`: 13 sections, 60 items
- `highlights`: 8 sections, 27 items
- `adjustments`: 2 sections, 6 items
- `login_rewards`: 1 section, 8 items
- `other_additions`: 2 sections, 8 items

Examples verified in the current database:

- `Hotfix 712852`: glued source headings are separated into `Changes` and `Bug Fixes`, yielding 1 change item and 8 bug-fix items.
- `Hotfix 740256`: 5 `Changes` items and 10 `Bug Fixes` items.
- `Don't Starve Together: From Beyond - Cursed Confrontation Pt. 1 & Klei Fest 2026`: ordered `Introduction`, `Highlights`, `Other Additions`, and `Changes` sections.

The Steam clan image extractor only stores URLs ending in known image extensions, avoiding truncated or text-contaminated URLs such as placeholders ending in `...` or `pngThe`.

The database also includes an `official_record_mentions` table that links official Steam/Klei records back to matching wiki entities by conservative title-phrase matching. With DLC titles and descriptions included, this pass generated 678 official-record entity mentions:

- `steam:dlc_appdetails`: 386
- `steam:news`: 176
- `steam:steam_dlc_id`: 102
- `steam:appdetails`: 9
- `klei:http_probe`: 5

Top entities mentioned by DLC appdetails include:

- `Don't Starve`: 53
- `Don't Starve Together`: 49
- `Wilson`: 18
- `The Constant`: 17
- `Wendy`: 13
- `Willow`: 13
- `Webber`: 12
- `WX-78`: 11
- `Winona`: 11
- `Wolfgang`: 11
- `Wortox`: 11

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

The database now also includes `entity_variant_summary`, which merges variant keys from `entity_attributes`, `entity_stats`, `entity_facts`, `recipe_ingredients`, `entity_variants`, and `entity_media_assets`. This pass generated 2,982 merged variant summary rows:

- `numbered_variant`: 1,680
- `infobox_instance`: 617
- `visual_variant`: 336
- `game_scope`: 234
- `growth_stage`: 47
- `animation`: 26
- `build_state`: 23
- `map_icon`: 5
- `state`: 5
- `oversized_form`: 4
- `reference_asset`: 4
- `phase`: 1

Evidence coverage across variant summary rows:

- Rows with data evidence: 2,566
- Rows with media evidence: 590
- Rows with stat evidence: 227
- Rows with fact evidence: 6
- Rows with recipe evidence: 1,464

Examples verified in the current database:

- `Battle Songs`: numbered variants merge attribute, recipe, explicit variant, and media evidence.
- `Berry Bush`: numbered variants merge data, recipe, explicit variant, and media evidence.
- `Chess Pieces`: numbered variants preserve several media-backed forms.

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

## Unified Entity Media Assets

The database now includes an `entity_media_assets` table derived from `entity_images`, `page_images`, and `image_variants`. It provides one query surface for infobox images, page-reference images, primary image flags, file-page URLs, source URLs, local paths, and image variant metadata.

This pass generated 46,311 media asset rows:

- `infobox`: 1,874
- `page_reference`: 44,437
- Primary asset rows: 1,663
- Variant asset rows: 629

Variant media asset distribution:

- `visual_variant`: 339
- `infobox_variant`: 133
- `game_scope`: 77
- `animation`: 26
- `build_state`: 23
- `growth_stage`: 12
- `map_icon`: 5
- `state`: 5
- `oversized_form`: 4
- `reference_asset`: 4
- `phase`: 1

Examples verified in the current database:

- `Alchemy Engine`: page-reference media assets for `Build`, `Burnt`, and animation images.
- `Ancient Guardian`: `Phase 2` page-reference media asset.
- `Axe`: `Dropped` state and `Wall Decoration` visual-variant media assets.

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

## Entity Prefab Profiles

The database now includes `entity_prefab_profiles`, a one-row prefab/spawn-code summary table derived from `entity_identity_keys.key_type = 'spawn_code'`. It makes prefab lookup queryable without scanning all identity keys and records upgrade-like prefab categories from conservative code-pattern evidence.

This pass generated 1,647 prefab profile rows:

- Spawn-code/prefab values summarized: 2,779
- Upgraded prefab codes: 14
- Reskin prefab codes: 1
- Mast-upgrade prefab codes: 4
- Chest-upgrade prefab codes: 1
- Merm-upgrade prefab codes: 4

Example prefab profiles:

- `Armermry`: `merm_armory | merm_armory_upgraded`, with `merm_upgrade` and `upgraded` flags.
- `Chest`: `treasurechest | treasurechest_upgraded`, with `upgraded` flag.
- `Clean Sweeper`: `reskin_tool`, with `reskin` flag.
- `Elastispacer`: `chestupgrade_stacksize`, with `chest_upgrade` and `upgraded` flags.
- `Berry Bush`: `berrybush | berrybush2`, standard prefab codes.

Each compressed entity profile now includes a nullable `prefab_profile` object with the primary prefab, full prefab code list, source fields, category text, category counts, and upgrade/reskin flags. This gives applications a direct way to map wiki entries to game prefab names and to flag upgrade-related prefab forms while keeping the noisier material names such as `Pig Skin` out of upgrade/skin relationship tables.

## Source Access Audit

The database now includes a `source_catalog` table and `source_catalog_evidence` table for ranked source discovery and verification planning. This pass generated 8 source catalog rows and 26 evidence rows:

- `wiki.gg`: rank 1, `primary`, canonical community wiki, `permission_required`
- `klei`: rank 2, `official`, official verification, `active`
- `steam`: rank 3, `official`, official product/update metadata, `active`
- `fandom`: rank 4, `comparison`, historical community wiki, `active_with_caution`
- `fextralife`: rank 5, `competitor`, reference-only coverage checks
- `wikipedia`: rank 6, `context`, general product context only
- `reddit`: rank 7, `community_signal`, source-discovery signal only
- `patchbot`: rank 8, `community_signal`, update-discovery signal only

Evidence row counts by source:

- `klei`: 6
- `steam`: 5
- `wiki.gg`: 5
- `fandom`: 5
- `fextralife`: 2
- `patchbot`: 1
- `reddit`: 1
- `wikipedia`: 1

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

## Entity JSON Profiles

The database now includes an `entity_profile_json` table with one consumable JSON profile per entity. This pass generated 2,252 rows, matching the `entities` table.

Profile payloads are stored as `gzip+json` bytes in `profile_json` to keep the committed SQLite database below GitHub's 100 MiB file limit while preserving full profile detail. Use `dst_wiki_db.entity_profiles.load_profile_json` to decode rows; the loader also supports older `gzip+base64+json` rows. After binary profile compression, embedded attributes, media profile expansion, link profile expansion, prefab profile expansion, and `VACUUM`, `data/dont_starve_wiki.sqlite` is 98,291,712 bytes, about 94 MiB.

Each profile aggregates:

- identity: id, slug, title, kind, canonical URL, and summary
- coverage: coverage score, detailed evidence counts, boolean coverage flags, and missing-data labels
- attributes: raw and normalized infobox fields with source id/key, raw page id, template name/index, raw name, canonical name, value text, parsed number, unit, and variant key
- media: unified infobox/page media assets with primary flags, URLs, dimensions, local paths, and variant metadata
- media_profile: query-ready primary image, variant image, URL-readiness, and download-state summary
- stats: normalized stat rows with raw field names, numeric values when available, units, and variant keys
- variants: merged variant evidence from data, recipes, facts, explicit variants, and media
- categories, taxonomy tags, facts, recipe ingredients, typed gameplay relationships, wiki-link profile, prefab profile, and official Steam/Klei mentions

The table also stores queryable top-level counts such as `attribute_count`, `media_count`, `stat_count`, `variant_count`, `category_count`, `taxonomy_count`, `fact_count`, `recipe_ingredient_count`, `relationship_count`, `wiki_link_count`, `prefab_count`, and `official_mention_count` so applications can build lists without parsing JSON.

## Entity Link Profiles

The database now includes `entity_link_profiles`, a one-row navigation and cross-reference summary built from the full `entity_relations` table. It keeps the 58,997 raw wiki-link rows intact while exposing compact per-entry counts and top targets for API/list/detail use.

This pass generated 2,198 link profile rows:

- Source wiki-link rows summarized: 58,997
- Resolved links to known entities: 43,734
- Unresolved links kept as unresolved target summaries: 15,263

Example link profiles:

- `Don't Starve Together`: 325 wiki links, 274 resolved, 51 unresolved, 9 target kinds.
- `Crock Pot`: 122 wiki links, 97 resolved, 25 unresolved, 7 target kinds.
- `Deerclops`: 76 wiki links, 57 resolved, 19 unresolved, 6 target kinds.
- `Berry Bush`: 54 wiki links, 40 resolved, 14 unresolved, 8 target kinds.
- `Wilson`: 54 wiki links, 28 resolved, 26 unresolved, 5 target kinds.
- `Spear`: 17 wiki links, 11 resolved, 6 unresolved, 4 target kinds.

Each compressed entity profile now includes a nullable `link_profile` object with resolved/unresolved counts, unique target counts, target-kind distributions, and compact top resolved/unresolved target arrays. The top-target arrays are capped at 10 items per direction so the committed SQLite database stays below GitHub's 100 MiB file limit; full relation evidence remains queryable in `entity_relations`.

## Raw Wikitext Compression

The committed database now stores all 2,252 `raw_pages.wikitext` payloads with `wikitext_encoding = 'gzip'`. This keeps the original MediaWiki evidence inside SQLite while reducing the database from 100,032,512 bytes to 84,021,248 bytes after `VACUUM`, saving 16,011,264 bytes and keeping the repository below GitHub's 100 MiB single-file hard limit.

Use `dst_wiki_db.raw_pages.decode_wikitext(value, encoding)` to read the stored page text. New API ingests write gzip-encoded raw wikitext through `dst_wiki_db.raw_pages.encode_wikitext`, while tests and direct fixtures can still insert plain text because the schema defaults `wikitext_encoding` to `text`.

The compression pass is reproducible with:

```bash
python3 scripts/compress_raw_wikitext.py \
  --db data/dont_starve_wiki.sqlite \
  --report reports/raw_wikitext_compression.json
```

## Community Guide Library

The database now includes a curated Chinese community-guide discovery layer. It is intentionally separate from canonical mechanics tables: guide rows are metadata, summaries, reliability labels, topic tags, and verification reminders rather than copied article bodies or promoted gameplay facts.

This pass imported [data/community_guides_seed.json](../data/community_guides_seed.json) into SQLite:

- `community_guide_sources`: 21 rows
- `community_guide_topics`: 77 rows
- `community_guide_topic_index`: 5 rows

Platform coverage:

- `Bilibili`: 8
- `Zhihu`: 5
- `Gamersky`: 4
- `TapTap`: 3
- `Xiaohongshu`: 1 blocked/search placeholder

Status coverage:

- `accepted`: 16
- `accepted_with_caution`: 3
- `candidate`: 1
- `needs_login`: 1

The topic index currently covers beginner routes, food/healing, farming/giant crops, caves/ancient ruins, and bosses. Each topic stores recommended guide ids and explicit verification reminders such as checking food stats, nutrient tables, boss phase mechanics, loot probabilities, and DS-vs-DST differences against the local database, official sources, or current Wiki pages.

## Entity Stat Rollups

The database now includes `entity_stat_rollups`, a query-oriented summary table over all normalized stat rows. It groups by entity, stat name, stat type, and unit, keeping min/max numeric values, raw value texts, numeric value count, evidence row count, source count, and variant count.

This pass generated 5,142 stat rollups across 1,567 entities with stat data. The table covers combat, movement, item, food, survival, and generic stats, so consumers can query one compact row for fields such as health, damage, hunger restored, sanity restored, durability, protection, stack size, spoil time, attack period, and attack range.

Example rollups:

- `Dragonfly`: damage 3-225, health 2,750-27,500, attack range 4-6, walk speed 2-9.1
- `Football Helmet`: durability 315-450, protection 80%, water resistance 20%, tier 2
- `Meatballs`: hunger restored 62.5, sanity restored 5, health restored 3, spoil time 10 days

Each compressed entity profile now includes a `stat_rollups` array next to the raw `stats` array. The raw stats preserve exact extracted fields, while rollups give API consumers a compact summary for filtering, comparison, and card/detail rendering.

## Typed Gameplay Relationship Edges

The database now includes an `entity_gameplay_edges` table that turns resolved recipe and fact targets into typed forward and inverse relationships. This pass generated 4,502 gameplay edges:

- `uses_ingredient`: 1,816
- `ingredient_for`: 1,816
- `drops`: 359
- `dropped_by`: 359
- `spawns`: 74
- `spawned_from`: 74
- `sold_by`: 2
- `sells`: 2

These edges are derived only from resolved target tables, so each row points from one known entity id to another known entity id and keeps source evidence such as source table, source row id, quantity, probability, variant key, and confidence. The `entity_profile_json` profiles now include a `relationships` array and `relationship_count`; 943 entity profiles currently have at least one typed gameplay relationship.

## Entity Taxonomy Tags

The database now includes an `entity_taxonomy` table for faceted browsing and filtering beyond the single `entities.kind` value. This pass generated 23,810 taxonomy rows across all 2,252 entities:

- `source_category`: 12,973
- `gameplay`: 3,353
- `data`: 3,151
- `kind`: 2,252
- `dlc`: 1,165
- `game_mode`: 916

Common taxonomy tags include:

- `data:has_spawn_code`: 1,584 entities
- `data:has_stats`: 1,567 entities
- `source_category:items`: 977 entities
- `game_mode:dst`: 872 entities
- `gameplay:craftable`: 624 entities
- `gameplay:naturally_spawning`: 280 entities
- `gameplay:mob`: 279 entities
- `gameplay:drop_source`: 205 entities

Each compressed entity profile now includes a `taxonomy` array and `taxonomy_count`, so consumers can render labels such as `Mob`, `Hostile`, `Don't Starve Together`, `Craftable`, or `Has Spawn Code` directly from the profile payload.

## Entity Combat Profiles

The database now includes an `entity_combat_profiles` table that pivots normalized combat and movement stats into one queryable row per entity. It uses only `entity_stats.stat_type in ('combat', 'movement')`, so food healing values and other survival stats do not pollute combat health/damage summaries.

This pass generated 409 combat profile rows:

- `mob`: 210
- `item`: 85
- `character`: 58
- `boss`: 41
- `structure`: 7
- `page`: 5
- `plant`: 3

Each row stores min/max values, raw text, and evidence counts for health, damage, attack range, attack period, walk speed, and run speed, plus source and variant counts. Example boss rows now expose:

- `Ancient Guardian`: health 2,500-10,000, damage 100, attack range 4.6-25
- `Bee Queen`: health 22,500, damage 120, attack range 4
- `Deerclops`: health 2,000-4,000, damage 150, attack range 68
- `Dragonfly`: health 2,750-27,500, damage 3-225, attack range 4-6

Each compressed entity profile now includes a nullable `combat_profile` object so API consumers can read these battle/movement summaries directly from `entity_profile_json` without joining the raw stat tables.

## Entity Food Profiles

The database now includes `entity_food_profiles`, a one-row food/restoration summary table built from `entity_stat_rollups`. It normalizes both Food Infobox fields (`health`, `hunger`, `sanity`, `food_value`) and cooked recipe fields (`hp_restored`, `hunger_restored`, `sanity_restored`) into shared health, hunger, and sanity restore columns.

This pass generated 454 food profile rows:

- `item`: 248
- `character`: 61
- `food`: 57
- `boss`: 47
- `mob`: 29
- `structure`: 12

Each row stores min/max values and raw text for health, hunger, sanity, food value, spoil time, cook time, and recipe priority, along with stat/source/variant counts and boolean flags for restore stats and food value evidence.

Example food profiles:

- `Meatballs`: health 3, hunger 62.5, sanity 5, spoil time 10 days
- `Pierogi`: health 40, hunger 37.5, sanity 5, spoil time 20 days
- `Dragonpie`: health 40, hunger 75, sanity 5, spoil time 15 days
- `Berries`: health 0-1, hunger 9.375-12.5, food value 0.5, spoil time 3-6 days
- `Monster Meat`: health -20 to -3, hunger 18.75, sanity -15 to -10, food value 1

Each compressed entity profile now includes a nullable `food_profile` object so applications can render food and restoration cards without joining raw stat tables.

## Entity Item Profiles

The database now includes `entity_item_profiles`, a one-row item/equipment summary table built from `entity_stat_rollups`. It keeps item-oriented fields separate from mob combat profiles by limiting rows to `kind in ('item', 'food')`, while still bringing weapon `damage` from combat stats into item cards.

This pass generated 788 item profile rows:

- `item`: 730
- `food`: 58

Each row stores min/max values and raw text for damage, durability, protection, water resistance, stack, stack limit, burn time, tier, resources, renew, and priority, plus stat/source/variant counts and boolean flags for weapon, armor, and stack evidence.

Example item profiles:

- `Football Helmet`: durability 315-450, protection 80%, water resistance 20%, tier 2, does not stack
- `Log Suit`: durability 315-450, protection 80%, tier 1, does not stack
- `Spear`: durability 150, tier 1, does not stack
- `Tentacle Spike`: damage 51, durability 100
- `Torch`: damage up to 80, water resistance 20%, tier 0
- `Backpack`: tier 1, does not stack

Each compressed entity profile now includes a nullable `item_profile` object so applications can render inventory, equipment, weapon, and armor cards without joining raw stat tables.

## Entity World Profiles

The database now includes `entity_world_profiles`, a one-row summary table for plants, structures, and biome/world objects. It combines selected infobox attributes (`biome`, `spawn_code`, `renew`, `tool`, `perk`, `special_ability`, `growth_formula`, `seasons`) with normalized rollup stats for resources, health, damage, attack range, and attack period.

This pass generated 249 world profile rows:

- `structure`: 202
- `plant`: 45
- `biome`: 2

Each row stores raw text evidence for biome, spawn code, renewability, tools, perks, special abilities, growth formulas, and seasons, plus min/max/text values for resources and world-object combat stats. It also exposes flags for biome evidence, spawn-code evidence, renewable status, resource evidence, growth data, and combat data.

Example world profiles:

- `Berry Bush`: biome `GrasslandForestJungle ()Cultivated ()`, spawn codes `berrybush | berrybush2`, renewable via cave regeneration/world regrowth
- `Evergreen`: biome `ForestGrassland`, spawn codes for tall/normal/short/burnt/stump/sapling forms, resources up to 3
- `Hanging Vine`: biome `Deep Rainforest`, spawn codes `grabbing_vine | hanging_vine`, damage 10, attack range 3, attack period 1
- `Campfire`: spawn codes `campfire | firepit`

Each compressed entity profile now includes a nullable `world_profile` object so plant, structure, and world-object pages can be rendered with habitat, prefab/spawn-code, renewability, resource, and defensive stat details without joining raw attributes.

## Entity Character Profiles

The database now includes `entity_character_profiles`, a one-row summary table for character entries. It combines selected character infobox fields (`nick`, `motto`, `birthday`, `gender`, `species`, `voice`, `games`, `spawn_code`, `perk`, `survivability`, `bio`, `favorite_food`, `start_item`, and `item`) with normalized rollup stats for health, hunger, sanity, and damage.

This pass generated 72 character profile rows.

Each row stores raw text evidence for identity/flavor fields, spawn codes, perks, survivability, biography, favorite food, starting equipment, and character-specific items. It also stores min/max/text values for health, hunger, sanity, and damage, plus flags for core stat coverage, perks, start items, and bio availability.

Example character profiles:

- `Wigfrid`: health 200, hunger 120, sanity 120, damage 0.75-1.25, spawn code `wathgrithr`, nick `The Performance Artist`
- `Wormwood`: health 150, hunger 150, sanity 200, spawn code `wormwood`, nick `The Lonesome`
- `Wendy`: character identity row present, with source coverage currently coming mainly from identity/media fields
- `Wilson`: character identity row present, with source coverage currently coming mainly from identity/media fields

Each compressed entity profile now includes a nullable `character_profile` object so character pages can expose survivability, lore/flavor fields, prefab/spawn-code details, perks, starting items, and core stats without joining raw attributes.

## Entity Creature Profiles

The database now includes `entity_creature_profiles`, a one-row summary table for mob and boss entries. It combines creature infobox fields (`biome`, `spawn_code`, `special_ability`, `perk`, `drops`, `dropped_by`, `spawn_from`, and `spawns`) with normalized rollup stats for health, damage, attack range, attack period, walk speed, run speed, sanity aura, and sanity drain. It also brings in typed gameplay relationship counts for drops and spawn links.

This pass generated 412 creature profile rows:

- `mob`: 267
- `boss`: 145

Each row stores raw text evidence, min/max/text stat values, drop/spawn relationship counts, related title summaries, source/variant counts, and flags for boss status, combat stats, movement stats, sanity effects, drop data, and spawn data.

Example creature profiles:

- `Bee Queen`: health 22,500, damage 120, attack range 4, boss flag enabled
- `Deerclops`: health 2,000-4,000, damage 150, attack range up to 68, spawn code `deerclops`
- `Dragonfly`: health up to 27,500, damage up to 225, attack range 6, drop/spawn relationship data present
- `Spider`: health 100, damage 20, attack range 3, sanity aura -25/min, spawn relationship data present

Each compressed entity profile now includes a nullable `creature_profile` object so mob and boss pages can expose combat, movement, sanity, drop, spawn, and ecology data without joining raw stat, attribute, and relationship tables.

## Entity Recipe Profiles

The database now includes `entity_recipe_profiles`, a one-row crafting and cooking summary table built from `recipe_ingredients`, `recipe_ingredient_targets`, and inverse recipe relationship edges. It preserves original ingredient slots and quantities while also exposing resolved ingredient targets and reverse "used in" links.

This pass generated 783 recipe profile rows:

- `item`: 510
- `structure`: 139
- `boss`: 73
- `mob`: 26
- `food`: 25
- `character`: 6
- `plant`: 3
- `page`: 1

Each row stores recipe count, ingredient count, resolved/unresolved ingredient counts, used-in count, source/variant counts, joined text summaries, and JSON arrays for ingredient details and used-in details.

Example recipe profiles:

- `Spear`: 1 recipe, 3 ingredients (`Twigs | Rope | Flint`), 3 resolved ingredient targets, used in 8 other recipes
- `Crock Pot`: 1 recipe, 3 ingredients (`Cut Stone | Charcoal | Twigs`)
- `Alchemy Engine`: 1 recipe, 3 ingredients (`Boards | Cut Stone | Gold Nugget`)
- `Twigs`: 1 recipe from `Log`, and used in 88 other recipes
- `Cut Stone`: 1 recipe from `Rocks`, and used in 46 other recipes

Each compressed entity profile now includes a nullable `recipe_profile` object so item, food, structure, and ingredient pages can render crafting cards and reverse ingredient usage without joining recipe tables.

## Entity Media Profiles

The database now includes `entity_media_profiles`, a one-row media summary table for entities with image evidence. It is built from `entity_media_assets` and `entity_media_downloads`, so list/detail APIs can read primary images, variant-image summaries, URL readiness, and download status without scanning the full 46,311-row manifest.

This pass generated 1,224 media profile rows.

URL readiness across the underlying media manifest:

- `direct_url`: 2,034 rows
- `file_page_only`: 44,188 rows
- `missing_url`: 89 rows

Example media profiles:

- `Berry Bush`: 2 media rows, 2 variant rows, 2 direct URLs, variant images for numbered infobox forms.
- `Crock Pot`: 501 media rows, 2 primary rows, 3 variant rows, primary image `Crock Pot Build.png`.
- `Deerclops`: 449 media rows, 35 variant rows, 35 direct URLs.
- `Wilson`: 50 media rows, 3 variant rows, 1 direct URL.

Each compressed entity profile now includes a nullable `media_profile` object with query-ready counts, flags, primary image metadata, and compact primary/variant asset arrays. The file-page resolver refreshes both `entity_media_profiles` and `entity_profile_json` after non-dry-run URL resolution so profile payloads keep the same direct/file-page/missing counts as `entity_media_downloads`.

## Media Download Manifest

The database now includes an `entity_media_downloads` table with one pending download manifest row per unified media asset. This pass generated 46,311 manifest rows, matching `entity_media_assets`.

URL readiness after resolving a first 250-row file-page batch:

- `direct_url`: 2,034 rows
- `file_page_only`: 44,188 rows
- `missing_url`: 89 rows

Queue reasons:

- `page_reference|file_page_only`: 44,018
- `primary|direct_url`: 1,579
- `variant|direct_url`: 454
- `variant|file_page_only`: 170
- `primary|missing_url`: 84
- `variant|missing_url`: 5
- `page_reference|direct_url`: 1

Each row stores source key, entity slug/title/kind, image name/slug, direct download URL when available, file-page URL, deterministic `data/images/{source_key}/{entity_slug}/{image_slug}` target path, download status, priority, queue reason, and variant metadata. Downloader state columns now record local path, content length, downloaded timestamp, and error text.

File-page rows are resolvable through MediaWiki imageinfo without downloading binaries:

```bash
python3 scripts/resolve_media_file_pages.py \
  --db data/dont_starve_wiki.sqlite \
  --source-key fandom \
  --limit 250 \
  --batch-size 50 \
  --report reports/media_file_page_resolution.json
```

The latest resolver batch attempted 250 rows, resolved 249 direct URLs, and left 1 missing. Both `entity_media_downloads` and `entity_media_assets` now have 2,034 direct media URLs.

The manifest is executable with `scripts/download_media_assets.py`. A safe downloader smoke run is:

```bash
python3 scripts/download_media_assets.py \
  --db data/dont_starve_wiki.sqlite \
  --output-root . \
  --limit 25 \
  --dry-run \
  --report reports/media_downloads.json
```

Only rows with `url_status = 'direct_url'` and `download_status = 'pending'` are fetched. Binary image files remain out of git by default; the downloader updates database/report metadata while leaving the image payloads in ignored `data/images/` paths.
