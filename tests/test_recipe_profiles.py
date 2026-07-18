import json

from dst_wiki_db.recipe_profiles import rebuild_entity_recipe_profiles
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_rebuild_entity_recipe_profiles_summarizes_recipe_ingredients(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = _source(conn)
    spear_id = _entity(conn, source_id, "Spear", "item", page_id=1)
    twigs_id = _entity(conn, source_id, "Twigs", "item", page_id=2)
    rope_id = _entity(conn, source_id, "Rope", "item", page_id=3)
    flint_id = _entity(conn, source_id, "Flint", "item", page_id=4)
    raw_page_id = _raw_page(conn, source_id, "Spear", page_id=1)
    _ingredient(conn, spear_id, source_id, raw_page_id, 1, "Twigs", "twigs", "2", 2)
    _ingredient(conn, spear_id, source_id, raw_page_id, 2, "Rope", "rope", "1", 1)
    _ingredient(conn, spear_id, source_id, raw_page_id, 3, "Flint", "flint", "1", 1)
    _target(conn, spear_id, twigs_id, 1)
    _target(conn, spear_id, rope_id, 2)
    _target(conn, spear_id, flint_id, 3)

    result = rebuild_entity_recipe_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, kind, recipe_count, ingredient_count,
               resolved_ingredient_count, unresolved_ingredient_count,
               ingredient_names_text, ingredient_targets_text, has_recipe,
               has_resolved_ingredients, is_ingredient, ingredient_summary_json
        from entity_recipe_profiles
        """
    ).fetchone()
    assert row["canonical_title"] == "Spear"
    assert row["kind"] == "item"
    assert row["recipe_count"] == 1
    assert row["ingredient_count"] == 3
    assert row["resolved_ingredient_count"] == 3
    assert row["unresolved_ingredient_count"] == 0
    assert row["ingredient_names_text"] == "Twigs | Rope | Flint"
    assert row["ingredient_targets_text"] == "Twigs | Rope | Flint"
    assert row["has_recipe"] == 1
    assert row["has_resolved_ingredients"] == 1
    assert row["is_ingredient"] == 0
    ingredients = json.loads(row["ingredient_summary_json"])
    assert ingredients[0] == {
        "name": "Twigs",
        "quantity_number": 2.0,
        "quantity_text": "2",
        "slot": 1,
        "slug": "twigs",
        "variant_key": "",
    }


def test_rebuild_entity_recipe_profiles_summarizes_used_in_edges(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = _source(conn)
    spear_id = _entity(conn, source_id, "Spear", "item", page_id=1)
    twigs_id = _entity(conn, source_id, "Twigs", "item", page_id=2)
    _edge(conn, twigs_id, spear_id, source_id, "Spear", "spear", "item", "2", 2)

    result = rebuild_entity_recipe_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select canonical_title, recipe_count, ingredient_count, used_in_count,
               used_in_titles_text, has_recipe, is_ingredient,
               used_in_summary_json
        from entity_recipe_profiles
        """
    ).fetchone()
    assert row["canonical_title"] == "Twigs"
    assert row["recipe_count"] == 0
    assert row["ingredient_count"] == 0
    assert row["used_in_count"] == 1
    assert row["used_in_titles_text"] == "Spear"
    assert row["has_recipe"] == 0
    assert row["is_ingredient"] == 1
    used_in = json.loads(row["used_in_summary_json"])
    assert used_in[0]["title"] == "Spear"
    assert used_in[0]["quantity_number"] == 2.0


def test_rebuild_entity_recipe_profiles_is_idempotent_without_recipe_data(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    assert rebuild_entity_recipe_profiles(conn) == 0
    assert rebuild_entity_recipe_profiles(conn) == 0


def _source(conn):
    return upsert_source(
        conn,
        key="fandom",
        name="Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )


def _entity(conn, source_id, title, kind, *, page_id):
    return upsert_entity(
        conn,
        canonical_title=title,
        kind=kind,
        primary_source_id=source_id,
        primary_page_id=page_id,
        canonical_url=f"https://example.test/{title.replace(' ', '_')}",
        summary="",
    )


def _raw_page(conn, source_id, title, *, page_id):
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, ?, 0, ?, 'https://example.test/Page', '',
                '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id, page_id, title),
    )
    return conn.execute("select id from raw_pages where pageid = ?", (page_id,)).fetchone()["id"]


def _ingredient(
    conn,
    entity_id,
    source_id,
    raw_page_id,
    slot,
    name,
    slug,
    quantity_text,
    quantity_number,
):
    conn.execute(
        """
        insert into recipe_ingredients (
            entity_id, source_id, raw_page_id, template_index,
            ingredient_slot, ingredient_name, ingredient_slug,
            quantity_text, quantity_number, variant_key
        )
        values (?, ?, ?, 0, ?, ?, ?, ?, ?, '')
        """,
        (
            entity_id,
            source_id,
            raw_page_id,
            slot,
            name,
            slug,
            quantity_text,
            quantity_number,
        ),
    )


def _target(conn, entity_id, ingredient_entity_id, slot):
    recipe_ingredient_id = conn.execute(
        """
        select id from recipe_ingredients
        where entity_id = ? and ingredient_slot = ?
        """,
        (entity_id, slot),
    ).fetchone()["id"]
    target = conn.execute(
        "select canonical_title, slug from entities where id = ?",
        (ingredient_entity_id,),
    ).fetchone()
    conn.execute(
        """
        insert into recipe_ingredient_targets (
            recipe_ingredient_id, entity_id, source_id, ingredient_entity_id,
            ingredient_name, ingredient_slug, match_method, confidence
        )
        values (?, ?, 1, ?, ?, ?, 'exact_slug', 1.0)
        """,
        (
            recipe_ingredient_id,
            entity_id,
            ingredient_entity_id,
            target["canonical_title"],
            target["slug"],
        ),
    )


def _edge(
    conn,
    entity_id,
    related_entity_id,
    source_id,
    related_title,
    related_slug,
    related_kind,
    quantity_text,
    quantity_number,
):
    entity = conn.execute(
        "select canonical_title, slug, kind from entities where id = ?",
        (entity_id,),
    ).fetchone()
    conn.execute(
        """
        insert into entity_gameplay_edges (
            entity_id, related_entity_id, source_id, source_table,
            source_row_id, edge_type, edge_group, direction, entity_title,
            entity_slug, entity_kind, related_title, related_slug,
            related_kind, quantity_text, quantity_number, confidence
        )
        values (?, ?, ?, 'recipe_ingredients', 1, 'ingredient_for',
                'recipe', 'inverse', ?, ?, ?, ?, ?, ?, ?, ?, 1.0)
        """,
        (
            entity_id,
            related_entity_id,
            source_id,
            entity["canonical_title"],
            entity["slug"],
            entity["kind"],
            related_title,
            related_slug,
            related_kind,
            quantity_text,
            quantity_number,
        ),
    )
