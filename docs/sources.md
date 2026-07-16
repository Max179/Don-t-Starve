# Don't Starve Data Sources

Checked on 2026-07-16 Asia/Shanghai during this build session.

## 1. Don't Starve Wiki on wiki.gg

- URL: https://dontstarve.wiki.gg/
- API: https://dontstarve.wiki.gg/api.php
- Role: canonical community source, pending permission for bulk API access.
- Observed API statistics: about 234,233 pages, 3,231 articles, 38,029 images, 569,208 edits, and 56 active users.
- License: CC BY-SA 4.0 according to API rights/siteinfo.
- Useful API patterns:
  - `action=query&list=allpages`
  - `action=query&prop=revisions|categories|templates|images`
  - `action=query&prop=imageinfo&iiprop=url|mime|size|sha1`
- Constraint: robots research indicated `/api.php`, `/rest.php`, and `/wiki/File:` are disallowed for automated crawling. Use only with permission or an approved access method.
- Current source audit: `robots.txt` returned HTTP 200 and declared `search=yes`, `ai-train=no`, and `use=reference`. The project records wiki.gg `mediawiki_siteinfo` as `restricted_by_robots` and skips API access by default.
- Dump discovery: common unauthenticated paths such as `/sitemap.xml`, `/sitemap_index.xml`, and `/dump.xml` did not expose a usable XML dump during the latest probe. `Special:Statistics`, `Special:AllPages`, and normal article pages returned HTTP 200 on lightweight HEAD probes, but Special pages are not used as a bulk ingestion path.
- Approved dump path: if wiki.gg or another approved source provides a MediaWiki XML dump, use `scripts/import_xml_dump.py` to import it into the canonical database without calling `/api.php`.

## 2. Klei Official Site And Forums

- Game page: https://www.klei.com/games/dont-starve-together
- DST updates: https://forums.kleientertainment.com/game-updates/dst/
- Role: official verification.
- Best use: verify releases, update notes, official descriptions, and mechanic changes.
- Constraint: official text and media are not a bulk reusable wiki license. Store facts, citations, URLs, and timestamps rather than copying long announcement bodies.
- Current source audit: the two Klei game pages returned HTTP 200. The DST update forum returned HTTP 403 during the latest audit and is stored as a failed source-access record.

## 3. Steam Store / Steam Web API

- DST Store: https://store.steampowered.com/app/322330/Dont_Starve_Together/
- DS Store: https://store.steampowered.com/app/219740/Dont_Starve/
- DST API: https://store.steampowered.com/api/appdetails?appids=322330&filters=basic
- DS API: https://store.steampowered.com/api/appdetails?appids=219740&filters=basic
- Role: official product and DLC verification.
- Best use: app ids, DLC ids, release metadata, supported platforms, store descriptions, and news pointers.
- Current source audit: both appdetails probes returned HTTP 200.

## 4. Don't Starve Wiki on Fandom

- URL: https://dontstarve.fandom.com/
- API: https://dontstarve.fandom.com/api.php
- Role: historical comparison source.
- Observed API statistics: about 219,384 pages, 2,252 articles, 25,319 images, 533,981 edits, and 8 active users.
- License: CC-BY-SA / Fandom licensing.
- Best use: cross-source title matches, older page history, and difference checks against wiki.gg.
- Constraint: Fandom pages include platform wrappers and may be sensitive to high-frequency requests. Use low request rates and cache raw pages.
- Current source audit: `robots.txt` returned HTTP 403 through Cloudflare in the latest audit, while `api.php` siteinfo returned HTTP 200.

## Common Wiki Structures

Core categories to prioritize:

- `Characters`
- `Items`
- `Mobs`
- `Boss Monsters`
- `Plants`
- `Structures`
- `Biomes`
- `Food`
- `Crafting`
- `Craftable Items`
- `Craftable Structures`
- `Skin Icons`
- `Don't Starve Together`
- `Reign of Giants`
- `Shipwrecked`
- `Hamlet`

Core templates to parse:

- `Character Infobox`
- `Item Infobox`
- `Mob Infobox`
- `Object Infobox`
- `Food Infobox`
- `Plant Infobox`
- `Biome Infobox`
- `Craft Infobox`
- `Item Fish Infobox`
- `Turf Infobox`
- `SkinInfo`

Important field patterns:

- Health: `health`, `DSThealth`, `health ds`, `health dst`, `healthBoat`
- Damage: `damage`, `planar_damage`, `damage ds`, `damage dst`
- Attack: `attackRange`, `attackPeriod`, `range`
- Speed: `walkSpeed`, `runSpeed`, `speed ds`, `speed dst`
- Spawn code: `spawnCode`, `spawnCode ds`, `spawnCode dst`, `spawnCode1`, `spawnCode2`
- Images: `image`, `icon`, `image ds`, `image dst`, `image1`, `image2`, `seed`, `sprout`, `small`, `med`, `bolting`, `picked`

## Attribution Requirements

For any redistributed database, keep source URL, source title, revision id, fetch timestamp, and license fields. Because wiki content is ShareAlike, a public derivative database likely needs compatible licensing and visible attribution to the source wiki contributors.
