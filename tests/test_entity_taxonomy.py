from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.taxonomy import rebuild_entity_taxonomy


def test_rebuild_entity_taxonomy_derives_kind_category_and_gameplay_tags(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
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
        canonical_title="Bee",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Bee",
        summary="A buzzing mob.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, 'Bee', 'https://example.test/Bee', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    for name, slug in (
        ("Mobs", "mobs"),
        ("Hostile Creatures", "hostile-creatures"),
        ("Mob Dropped Items", "mob-dropped-items"),
        ("Don't Starve Together", "dont-starve-together"),
    ):
        conn.execute(
            """
            insert into entity_categories (
                entity_id, source_id, raw_page_id, category_name, category_slug
            )
            values (?, ?, ?, ?, ?)
            """,
            (entity_id, source_id, raw_page_id, name, slug),
        )
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name,
            raw_name, canonical_name, value_text
        )
        values (?, ?, ?, 0, 'Mob Infobox', 'spawnCode',
                'spawn_code', 'bee')
        """,
        (entity_id, source_id, raw_page_id),
    )
    attribute_id = conn.execute("select id from entity_attributes").fetchone()["id"]
    for stat_name, stat_type, raw_name, value_text, value_number, unit in (
        ("health", "combat", "health", "100", 100, "hp"),
        ("damage", "combat", "damage", "10", 10, "damage"),
    ):
        conn.execute(
            """
            insert into entity_stats (
                entity_id, source_id, raw_page_id, attribute_id, stat_name,
                stat_type, raw_name, value_text, value_number, unit, variant_key
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
            """,
            (
                entity_id,
                source_id,
                raw_page_id,
                attribute_id,
                stat_name,
                stat_type,
                raw_name,
                value_text,
                value_number,
                unit,
            ),
        )

    result = rebuild_entity_taxonomy(conn)

    assert result == 11
    rows = {
        (row["taxonomy_type"], row["taxonomy_key"]): dict(row)
        for row in conn.execute(
            """
            select taxonomy_type, taxonomy_key, label, confidence,
                   evidence_source, evidence_count
            from entity_taxonomy
            where entity_id = ?
            order by taxonomy_type, taxonomy_key
            """,
            (entity_id,),
        )
    }
    assert rows[("kind", "mob")] == {
        "taxonomy_type": "kind",
        "taxonomy_key": "mob",
        "label": "Mob",
        "confidence": 1.0,
        "evidence_source": "entities.kind",
        "evidence_count": 1,
    }
    assert rows[("source_category", "mobs")]["label"] == "Mobs"
    assert rows[("source_category", "hostile-creatures")]["label"] == "Hostile Creatures"
    assert rows[("source_category", "mob-dropped-items")]["label"] == "Mob Dropped Items"
    assert rows[("source_category", "dont-starve-together")]["label"] == "Don't Starve Together"
    assert rows[("gameplay", "hostile")]["evidence_count"] == 1
    assert rows[("gameplay", "drop_source")]["label"] == "Drop Source"
    assert rows[("game_mode", "dst")]["label"] == "Don't Starve Together"
    assert rows[("data", "has_stats")]["evidence_count"] == 2
    assert rows[("data", "has_spawn_code")]["evidence_count"] == 1


def test_rebuild_entity_taxonomy_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_entity_taxonomy(conn)
    second = rebuild_entity_taxonomy(conn)

    assert first == second == 0
