from dst_wiki_db.character_profiles import rebuild_entity_character_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_character_profiles_pivots_character_facts_and_stats(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Wigfrid", "character")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "nick", "The Performance Artist")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "motto", '"All the world is a stage."')
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "birthday", "July 23")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "perk", "Excels in Battle")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "start_item", "Battle Spear")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "spawn_code", '"wathgrithr"')
    _insert_rollup(conn, entity_id, "Wigfrid", "character", "health", "combat", 200, 200, "200")
    _insert_rollup(conn, entity_id, "Wigfrid", "character", "hunger", "survival", 120, 120, "120")
    _insert_rollup(conn, entity_id, "Wigfrid", "character", "sanity", "survival", 120, 120, "120")
    _insert_rollup(conn, entity_id, "Wigfrid", "character", "damage", "combat", 0.75, 1.25, "0.75x taken | 1.25x caused")

    result = rebuild_entity_character_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, nick_text, motto_text, birthday_text,
               perk_text, start_item_text, spawn_code_text,
               health_max, hunger_max, sanity_max, damage_min, damage_max,
               attribute_count, stat_count, has_core_stats, has_perks,
               has_start_items, has_bio
        from entity_character_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "canonical_title": "Wigfrid",
        "nick_text": "The Performance Artist",
        "motto_text": '"All the world is a stage."',
        "birthday_text": "July 23",
        "perk_text": "Excels in Battle",
        "start_item_text": "Battle Spear",
        "spawn_code_text": "wathgrithr",
        "health_max": 200.0,
        "hunger_max": 120.0,
        "sanity_max": 120.0,
        "damage_min": 0.75,
        "damage_max": 1.25,
        "attribute_count": 6,
        "stat_count": 4,
        "has_core_stats": 1,
        "has_perks": 1,
        "has_start_items": 1,
        "has_bio": 0,
    }


def test_rebuild_entity_character_profiles_keeps_bio_and_identity_text(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Wormwood", "character")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "bio", "A plant-like lunar friend.")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "gender", "Male")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "species", "Plant")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "voice", "Reed")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "games", "Don't Starve Together")

    assert rebuild_entity_character_profiles(conn) == 1
    row = conn.execute(
        """
        select bio_text, gender_text, species_text, voice_text, games_text,
               has_bio, has_core_stats
        from entity_character_profiles
        """
    ).fetchone()
    assert dict(row) == {
        "bio_text": "A plant-like lunar friend.",
        "gender_text": "Male",
        "species_text": "Plant",
        "voice_text": "Reed",
        "games_text": "Don't Starve Together",
        "has_bio": 1,
        "has_core_stats": 0,
    }


def test_rebuild_entity_character_profiles_skips_non_characters(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id, raw_page_id, entity_id = _seed_entity(conn, "Spear", "item")
    _insert_attribute(conn, entity_id, source_id, raw_page_id, "nick", "Pointy")
    _insert_rollup(conn, entity_id, "Spear", "item", "damage", "combat", 34, 34, "34")

    assert rebuild_entity_character_profiles(conn) == 0
    assert conn.execute("select count(*) from entity_character_profiles").fetchone()[0] == 0


def _seed_entity(conn, canonical_title, kind):
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title=canonical_title,
        kind=kind,
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url=f"https://example.test/{canonical_title.replace(' ', '_')}",
        summary="",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, ?, 'https://example.test/Page', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id, canonical_title),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    return source_id, raw_page_id, entity_id


def _insert_attribute(conn, entity_id, source_id, raw_page_id, canonical_name, value_text):
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text, variant_key
        )
        values (?, ?, ?, 0, 'Character Infobox', ?, ?, ?, '')
        """,
        (entity_id, source_id, raw_page_id, canonical_name, canonical_name, value_text),
    )


def _insert_rollup(
    conn,
    entity_id,
    canonical_title,
    kind,
    stat_name,
    stat_type,
    value_min,
    value_max,
    value_texts,
):
    conn.execute(
        """
        insert into entity_stat_rollups (
            entity_id, slug, canonical_title, kind, stat_name, stat_type,
            unit, value_min, value_max, value_count, evidence_count,
            source_count, variant_count, value_texts
        )
        values (?, ?, ?, ?, ?, ?, 'points', ?, ?, 1, 1, 1, 0, ?)
        """,
        (
            entity_id,
            canonical_title.lower().replace(" ", "-"),
            canonical_title,
            kind,
            stat_name,
            stat_type,
            value_min,
            value_max,
            value_texts,
        ),
    )
