from __future__ import annotations

from pathlib import Path
import re
import sqlite3
from typing import Union


PathLike = Union[str, Path]


def connect(path: PathLike) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("pragma foreign_keys = on")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        create table if not exists sources (
            id integer primary key,
            key text not null unique,
            name text not null,
            base_url text not null,
            api_url text not null,
            role text not null,
            license text,
            fetched_at text,
            siteinfo_json text
        );

        create table if not exists raw_pages (
            id integer primary key,
            source_id integer not null references sources(id) on delete cascade,
            pageid integer not null,
            ns integer not null default 0,
            title text not null,
            revid integer,
            parentid integer,
            source_timestamp text,
            canonical_url text not null,
            wikitext text not null,
            categories_json text,
            templates_json text,
            images_json text,
            externallinks_json text,
            fetched_at text not null,
            unique (source_id, pageid)
        );

        create index if not exists idx_raw_pages_title on raw_pages(source_id, title);

        create table if not exists entities (
            id integer primary key,
            slug text not null unique,
            canonical_title text not null,
            kind text not null,
            primary_source_id integer references sources(id) on delete set null,
            primary_page_id integer,
            canonical_url text,
            summary text,
            confidence real not null default 1.0,
            updated_at text not null default current_timestamp
        );

        create table if not exists entity_sources (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            source_title text not null,
            source_pageid integer not null,
            source_revid integer,
            source_timestamp text,
            source_url text not null,
            match_method text not null,
            confidence real not null default 1.0,
            unique (entity_id, source_id, source_pageid)
        );

        create table if not exists entity_attributes (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            template_index integer not null default 0,
            template_name text,
            raw_name text not null,
            canonical_name text not null,
            value_text text not null,
            value_number real,
            unit text,
            variant_key text,
            unique (entity_id, raw_page_id, template_index, template_name, raw_name, variant_key)
        );

        create table if not exists entity_stats (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            attribute_id integer not null references entity_attributes(id) on delete cascade,
            template_index integer not null default 0,
            stat_name text not null,
            stat_type text not null,
            raw_name text not null,
            value_text text not null,
            value_number real,
            unit text not null,
            variant_key text not null default '',
            unique (attribute_id, stat_name)
        );

        create index if not exists idx_entity_stats_entity on entity_stats(entity_id);
        create index if not exists idx_entity_stats_name on entity_stats(stat_name);

        create table if not exists entity_stat_values (
            id integer primary key,
            entity_stat_id integer not null references entity_stats(id) on delete cascade,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            attribute_id integer not null references entity_attributes(id) on delete cascade,
            stat_name text not null,
            value_index integer not null,
            raw_value text not null,
            value_number real not null,
            context_text text not null,
            unit text not null,
            variant_key text not null default '',
            unique (entity_stat_id, value_index)
        );

        create index if not exists idx_entity_stat_values_entity
            on entity_stat_values(entity_id);
        create index if not exists idx_entity_stat_values_stat
            on entity_stat_values(stat_name);

        create table if not exists entity_images (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer references raw_pages(id) on delete set null,
            image_name text not null,
            role text not null,
            original_url text,
            description_url text,
            local_path text,
            width integer,
            height integer,
            mime text,
            sha1 text,
            variant_key text,
            unique (entity_id, source_id, image_name, role, variant_key)
        );

        create table if not exists page_images (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            image_title text not null,
            image_name text not null,
            image_slug text not null,
            role text not null default 'page_reference',
            description_url text,
            local_path text,
            unique (entity_id, source_id, raw_page_id, image_slug, role)
        );

        create index if not exists idx_page_images_entity on page_images(entity_id);

        create table if not exists image_variants (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            page_image_id integer not null references page_images(id) on delete cascade,
            image_name text not null,
            image_slug text not null,
            variant_key text not null,
            variant_type text not null,
            label text not null,
            match_method text not null,
            confidence real not null default 0.5,
            unique (entity_id, source_id, raw_page_id, page_image_id, variant_key)
        );

        create index if not exists idx_image_variants_entity on image_variants(entity_id);

        create table if not exists entity_media_assets (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer references raw_pages(id) on delete set null,
            asset_source text not null,
            entity_image_id integer references entity_images(id) on delete cascade,
            page_image_id integer references page_images(id) on delete cascade,
            image_name text not null,
            image_slug text not null,
            role text not null,
            original_url text,
            description_url text,
            local_path text,
            width integer,
            height integer,
            mime text,
            sha1 text,
            variant_key text not null default '',
            variant_type text not null default '',
            variant_label text not null default '',
            is_variant integer not null default 0,
            is_primary integer not null default 0,
            confidence real not null default 1.0,
            unique (entity_id, asset_source, image_slug, role, entity_image_id, page_image_id)
        );

        create index if not exists idx_entity_media_assets_entity
            on entity_media_assets(entity_id);
        create index if not exists idx_entity_media_assets_variant
            on entity_media_assets(is_variant, variant_type);

        create table if not exists entity_relations (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer references raw_pages(id) on delete set null,
            relation_type text not null,
            target_title text not null,
            target_slug text not null,
            target_entity_id integer references entities(id) on delete set null,
            raw_value text,
            unique (entity_id, source_id, raw_page_id, relation_type, target_slug)
        );

        create table if not exists verification_checks (
            id integer primary key,
            entity_id integer references entities(id) on delete cascade,
            check_type text not null,
            source_key text not null,
            target_key text,
            status text not null,
            details_json text,
            checked_at text not null default current_timestamp,
            unique (entity_id, check_type, source_key, target_key)
        );

        create table if not exists official_records (
            id integer primary key,
            provider text not null,
            record_type text not null,
            external_id text not null,
            title text not null,
            url text,
            status text not null,
            summary text,
            payload_json text not null,
            fetched_at text not null default current_timestamp,
            unique (provider, record_type, external_id)
        );

        create table if not exists official_record_mentions (
            id integer primary key,
            official_record_id integer not null references official_records(id) on delete cascade,
            entity_id integer not null references entities(id) on delete cascade,
            provider text not null,
            record_type text not null,
            external_id text not null,
            entity_title text not null,
            mention_text text not null,
            match_field text not null,
            match_method text not null,
            confidence real not null default 0.5,
            context_text text not null,
            unique (official_record_id, entity_id, match_field, mention_text)
        );

        create index if not exists idx_official_record_mentions_entity
            on official_record_mentions(entity_id);
        create index if not exists idx_official_record_mentions_record
            on official_record_mentions(official_record_id);

        create table if not exists official_products (
            id integer primary key,
            official_record_id integer not null references official_records(id) on delete cascade,
            provider text not null,
            record_type text not null,
            external_id text not null,
            product_type text not null,
            title text not null,
            url text,
            parent_external_id text,
            parent_title text,
            short_description text,
            release_date_text text,
            is_free integer,
            required_age integer,
            controller_support text,
            website text,
            supported_languages text,
            unique (official_record_id)
        );

        create index if not exists idx_official_products_external
            on official_products(provider, external_id);
        create index if not exists idx_official_products_parent
            on official_products(provider, parent_external_id);

        create table if not exists official_product_media (
            id integer primary key,
            official_product_id integer not null references official_products(id) on delete cascade,
            official_record_id integer not null references official_records(id) on delete cascade,
            provider text not null,
            external_id text not null,
            media_role text not null,
            media_index integer not null default 0,
            media_url text not null,
            width integer,
            height integer,
            source_field text not null,
            unique (official_record_id, media_role, media_index, media_url)
        );

        create index if not exists idx_official_product_media_product
            on official_product_media(official_product_id);
        create index if not exists idx_official_product_media_external
            on official_product_media(provider, external_id);

        create table if not exists official_update_events (
            id integer primary key,
            official_record_id integer not null references official_records(id) on delete cascade,
            provider text not null,
            record_type text not null,
            external_id text not null,
            appid integer,
            title text not null,
            url text,
            author text,
            published_at_unix integer,
            published_at_iso text,
            event_type text not null,
            summary text,
            content_text text not null,
            content_length integer not null default 0,
            mentioned_entity_count integer not null default 0,
            unique (official_record_id)
        );

        create index if not exists idx_official_update_events_appid
            on official_update_events(provider, appid);
        create index if not exists idx_official_update_events_published
            on official_update_events(published_at_unix);
        create index if not exists idx_official_update_events_type
            on official_update_events(event_type);

        create table if not exists official_update_media (
            id integer primary key,
            official_update_event_id integer not null references official_update_events(id) on delete cascade,
            official_record_id integer not null references official_records(id) on delete cascade,
            provider text not null,
            external_id text not null,
            media_role text not null,
            media_index integer not null default 0,
            media_url text not null,
            width integer,
            height integer,
            source_field text not null,
            unique (official_record_id, media_role, media_index, media_url)
        );

        create index if not exists idx_official_update_media_event
            on official_update_media(official_update_event_id);
        create index if not exists idx_official_update_media_external
            on official_update_media(provider, external_id);

        create table if not exists official_update_sections (
            id integer primary key,
            official_update_event_id integer not null references official_update_events(id) on delete cascade,
            official_record_id integer not null references official_records(id) on delete cascade,
            provider text not null,
            external_id text not null,
            section_index integer not null,
            heading_text text not null,
            section_type text not null,
            body_text text not null,
            item_count integer not null default 0,
            unique (official_update_event_id, section_index)
        );

        create index if not exists idx_official_update_sections_event
            on official_update_sections(official_update_event_id);
        create index if not exists idx_official_update_sections_type
            on official_update_sections(section_type);

        create table if not exists official_update_section_items (
            id integer primary key,
            official_update_section_id integer not null references official_update_sections(id) on delete cascade,
            official_update_event_id integer not null references official_update_events(id) on delete cascade,
            official_record_id integer not null references official_records(id) on delete cascade,
            provider text not null,
            external_id text not null,
            section_index integer not null,
            section_type text not null,
            item_index integer not null,
            item_text text not null,
            character_length integer not null,
            unique (official_update_section_id, item_index)
        );

        create index if not exists idx_official_update_section_items_section
            on official_update_section_items(official_update_section_id);
        create index if not exists idx_official_update_section_items_event
            on official_update_section_items(official_update_event_id);

        create table if not exists source_audits (
            id integer primary key,
            source_id integer references sources(id) on delete set null,
            source_key text not null,
            check_type text not null,
            url text not null,
            status text not null,
            status_code integer,
            allowed integer,
            title text not null,
            summary text,
            payload_json text not null,
            checked_at text not null default current_timestamp,
            unique (source_key, check_type, url)
        );

        create table if not exists source_catalog (
            id integer primary key,
            source_id integer references sources(id) on delete set null,
            source_key text not null unique,
            rank integer not null unique,
            tier text not null,
            source_type text not null,
            role text not null,
            name text not null,
            base_url text not null,
            api_url text,
            access_method text not null,
            ingestion_status text not null,
            license_summary text not null,
            coverage_summary text not null,
            verification_use text not null,
            notes text not null,
            last_verified text not null
        );

        create index if not exists idx_source_catalog_tier
            on source_catalog(tier);
        create index if not exists idx_source_catalog_status
            on source_catalog(ingestion_status);

        create table if not exists source_catalog_evidence (
            id integer primary key,
            source_catalog_id integer not null references source_catalog(id) on delete cascade,
            source_id integer references sources(id) on delete set null,
            source_key text not null,
            evidence_type text not null,
            provider text not null,
            url text not null,
            title text not null,
            summary text not null,
            checked_date text not null,
            unique (source_key, evidence_type, url, title)
        );

        create index if not exists idx_source_catalog_evidence_source
            on source_catalog_evidence(source_catalog_id);

        create table if not exists entity_coverage (
            id integer primary key,
            entity_id integer not null unique references entities(id) on delete cascade,
            slug text not null,
            canonical_title text not null,
            kind text not null,
            source_count integer not null default 0,
            raw_page_count integer not null default 0,
            attribute_count integer not null default 0,
            stat_count integer not null default 0,
            stat_value_count integer not null default 0,
            infobox_image_count integer not null default 0,
            page_image_count integer not null default 0,
            variant_count integer not null default 0,
            category_count integer not null default 0,
            relation_count integer not null default 0,
            resolved_relation_count integer not null default 0,
            fact_count integer not null default 0,
            resolved_fact_count integer not null default 0,
            recipe_ingredient_count integer not null default 0,
            resolved_recipe_ingredient_count integer not null default 0,
            official_mention_count integer not null default 0,
            has_source integer not null default 0,
            has_attributes integer not null default 0,
            has_stats integer not null default 0,
            has_images integer not null default 0,
            has_variants integer not null default 0,
            has_categories integer not null default 0,
            has_relations integer not null default 0,
            has_facts integer not null default 0,
            has_recipes integer not null default 0,
            has_official_mentions integer not null default 0,
            coverage_score integer not null default 0,
            missing_summary text not null
        );

        create index if not exists idx_entity_coverage_kind
            on entity_coverage(kind);
        create index if not exists idx_entity_coverage_score
            on entity_coverage(coverage_score);

        create table if not exists recipe_ingredients (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            template_index integer not null default 0,
            ingredient_slot integer not null,
            ingredient_name text not null,
            ingredient_slug text not null,
            quantity_text text,
            quantity_number real,
            variant_key text not null default '',
            unique (entity_id, raw_page_id, template_index, ingredient_slot, variant_key)
        );

        create table if not exists recipe_ingredient_targets (
            id integer primary key,
            recipe_ingredient_id integer not null references recipe_ingredients(id) on delete cascade,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            ingredient_entity_id integer not null references entities(id) on delete cascade,
            ingredient_name text not null,
            ingredient_slug text not null,
            match_method text not null,
            confidence real not null default 1.0,
            unique (recipe_ingredient_id, ingredient_entity_id, match_method)
        );

        create table if not exists entity_facts (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            template_index integer not null default 0,
            fact_index integer not null default 0,
            fact_type text not null,
            raw_name text not null,
            value_text text not null,
            target_title text,
            target_slug text not null default '',
            probability_text text,
            quantity_text text,
            quantity_number real,
            variant_key text not null default '',
            unique (entity_id, raw_page_id, template_index, fact_type, raw_name, fact_index, variant_key)
        );

        create table if not exists entity_fact_targets (
            id integer primary key,
            entity_fact_id integer not null references entity_facts(id) on delete cascade,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            target_entity_id integer not null references entities(id) on delete cascade,
            target_title text not null,
            target_slug text not null,
            match_method text not null,
            confidence real not null default 1.0,
            unique (entity_fact_id, target_entity_id, match_method)
        );

        create table if not exists entity_variants (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            template_index integer not null default 0,
            variant_key text not null,
            variant_type text not null,
            label text not null,
            source_field text not null,
            unique (entity_id, source_id, raw_page_id, template_index, variant_key, variant_type)
        );

        create table if not exists entity_variant_summary (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            slug text not null,
            canonical_title text not null,
            kind text not null,
            variant_key text not null,
            variant_type text not null,
            label text not null,
            attribute_count integer not null default 0,
            stat_count integer not null default 0,
            fact_count integer not null default 0,
            recipe_ingredient_count integer not null default 0,
            entity_variant_count integer not null default 0,
            media_asset_count integer not null default 0,
            primary_media_asset_count integer not null default 0,
            has_data integer not null default 0,
            has_media integer not null default 0,
            has_stats integer not null default 0,
            has_facts integer not null default 0,
            has_recipes integer not null default 0,
            confidence real not null default 0.5,
            source_summary text not null,
            unique (entity_id, variant_key)
        );

        create index if not exists idx_entity_variant_summary_entity
            on entity_variant_summary(entity_id);
        create index if not exists idx_entity_variant_summary_type
            on entity_variant_summary(variant_type);

        create table if not exists entity_categories (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer not null references raw_pages(id) on delete cascade,
            category_name text not null,
            category_slug text not null,
            unique (entity_id, source_id, raw_page_id, category_slug)
        );

        create table if not exists entity_identity_keys (
            id integer primary key,
            entity_id integer not null references entities(id) on delete cascade,
            source_id integer not null references sources(id) on delete cascade,
            raw_page_id integer references raw_pages(id) on delete set null,
            key_type text not null,
            key_value text not null,
            source_field text not null,
            confidence real not null default 1.0,
            unique (entity_id, source_id, key_type, key_value, source_field)
        );

        create table if not exists cross_source_matches (
            id integer primary key,
            left_entity_id integer not null references entities(id) on delete cascade,
            right_entity_id integer not null references entities(id) on delete cascade,
            key_type text not null,
            key_value text not null,
            confidence real not null default 1.0,
            match_method text not null,
            unique (left_entity_id, right_entity_id, key_type, key_value)
        );

        create table if not exists run_metadata (
            key text primary key,
            value text not null,
            updated_at text not null default current_timestamp
        );
        """
    )


def upsert_source(
    conn: sqlite3.Connection,
    *,
    key: str,
    name: str,
    base_url: str,
    api_url: str,
    role: str,
    license: str | None = None,
    fetched_at: str | None = None,
    siteinfo_json: str | None = None,
) -> int:
    conn.execute(
        """
        insert into sources (key, name, base_url, api_url, role, license, fetched_at, siteinfo_json)
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(key) do update set
            name=excluded.name,
            base_url=excluded.base_url,
            api_url=excluded.api_url,
            role=excluded.role,
            license=excluded.license,
            fetched_at=coalesce(excluded.fetched_at, sources.fetched_at),
            siteinfo_json=coalesce(excluded.siteinfo_json, sources.siteinfo_json)
        """,
        (key, name, base_url, api_url, role, license, fetched_at, siteinfo_json),
    )
    row = conn.execute("select id from sources where key=?", (key,)).fetchone()
    return int(row["id"])


def upsert_entity(
    conn: sqlite3.Connection,
    *,
    canonical_title: str,
    kind: str,
    primary_source_id: int,
    primary_page_id: int,
    canonical_url: str,
    summary: str,
    slug: str | None = None,
    confidence: float = 1.0,
) -> int:
    entity_slug = slug or slugify(canonical_title)
    conn.execute(
        """
        insert into entities (
            slug, canonical_title, kind, primary_source_id, primary_page_id,
            canonical_url, summary, confidence, updated_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
        on conflict(slug) do update set
            canonical_title=excluded.canonical_title,
            kind=excluded.kind,
            primary_source_id=excluded.primary_source_id,
            primary_page_id=excluded.primary_page_id,
            canonical_url=excluded.canonical_url,
            summary=excluded.summary,
            confidence=excluded.confidence,
            updated_at=current_timestamp
        """,
        (
            entity_slug,
            canonical_title,
            kind,
            primary_source_id,
            primary_page_id,
            canonical_url,
            summary,
            confidence,
        ),
    )
    row = conn.execute("select id from entities where slug=?", (entity_slug,)).fetchone()
    return int(row["id"])


def upsert_official_record(conn: sqlite3.Connection, record) -> int:
    import json

    conn.execute(
        """
        insert into official_records (
            provider, record_type, external_id, title, url, status, summary, payload_json, fetched_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
        on conflict(provider, record_type, external_id) do update set
            title=excluded.title,
            url=excluded.url,
            status=excluded.status,
            summary=excluded.summary,
            payload_json=excluded.payload_json,
            fetched_at=current_timestamp
        """,
        (
            record.provider,
            record.record_type,
            record.external_id,
            record.title,
            record.url,
            record.status,
            record.summary,
            json.dumps(record.payload, ensure_ascii=False),
        ),
    )
    row = conn.execute(
        """
        select id from official_records
        where provider=? and record_type=? and external_id=?
        """,
        (record.provider, record.record_type, record.external_id),
    ).fetchone()
    return int(row["id"])


def slugify(title: str) -> str:
    slug = title.strip().lower()
    slug = slug.replace("&", " and ")
    slug = slug.replace("'", "")
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")
