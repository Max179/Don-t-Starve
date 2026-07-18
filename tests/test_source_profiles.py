import json

from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from dst_wiki_db.source_profiles import rebuild_entity_source_profiles


def test_rebuild_entity_source_profiles_summarizes_matched_source_pages(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Axe",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Axe",
        summary="",
    )
    _index_and_match(
        conn,
        source_id,
        entity_id,
        pageid=10,
        title="Axe",
        slug="axe",
        method="alias:canonical_title",
        confidence=1.0,
    )
    _index_and_match(
        conn,
        source_id,
        entity_id,
        pageid=11,
        title="Axe/DST",
        slug="axe-dst",
        method="alias_game_variant_suffix:canonical_title",
        confidence=0.88,
    )
    _index_and_match(
        conn,
        source_id,
        entity_id,
        pageid=12,
        title="goldenaxe",
        slug="goldenaxe",
        method="alias:prefab_code",
        confidence=0.98,
    )

    result = rebuild_entity_source_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select source_key, matched_page_count, exact_page_count,
               game_variant_page_count, prefab_page_count, image_page_count,
               method_count, primary_page_title, primary_page_url,
               match_methods_json, matched_pages_json, has_exact_page,
               has_game_variant_pages, has_prefab_page, has_image_page
        from entity_source_profiles
        where entity_id = ?
        """,
        (entity_id,),
    ).fetchone()
    assert row["source_key"] == "wiki.gg"
    assert row["matched_page_count"] == 3
    assert row["exact_page_count"] == 1
    assert row["game_variant_page_count"] == 1
    assert row["prefab_page_count"] == 1
    assert row["image_page_count"] == 0
    assert row["method_count"] == 3
    assert row["primary_page_title"] == "Axe"
    assert row["primary_page_url"] == "https://dontstarve.wiki.gg/wiki/Axe"
    assert json.loads(row["match_methods_json"]) == [
        {"count": 1, "method": "alias:canonical_title"},
        {"count": 1, "method": "alias:prefab_code"},
        {"count": 1, "method": "alias_game_variant_suffix:canonical_title"},
    ]
    pages = json.loads(row["matched_pages_json"])
    assert [page["title"] for page in pages] == ["Axe", "Axe/DST", "goldenaxe"]
    assert row["has_exact_page"] == 1
    assert row["has_game_variant_pages"] == 1
    assert row["has_prefab_page"] == 1
    assert row["has_image_page"] == 0


def test_rebuild_entity_source_profiles_is_idempotent_without_matches(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    assert rebuild_entity_source_profiles(conn) == 0
    assert rebuild_entity_source_profiles(conn) == 0


def _index_and_match(
    conn,
    source_id,
    entity_id,
    *,
    pageid,
    title,
    slug,
    method,
    confidence,
):
    conn.execute(
        """
        insert into source_page_index (
            source_id, source_key, source_pageid, ns, title, title_slug,
            page_url, index_status
        )
        values (?, 'wiki.gg', ?, 0, ?, ?,
                'https://dontstarve.wiki.gg/wiki/' || replace(?, ' ', '_'),
                'listed')
        """,
        (source_id, pageid, title, slug, title),
    )
    source_page_index_id = conn.execute(
        "select id from source_page_index where source_pageid = ?", (pageid,)
    ).fetchone()["id"]
    entity = conn.execute(
        "select slug, canonical_title, kind from entities where id = ?", (entity_id,)
    ).fetchone()
    conn.execute(
        """
        insert into source_page_entity_matches (
            source_page_index_id, source_key, source_pageid, source_title,
            source_title_slug, entity_id, entity_slug, entity_title,
            entity_kind, match_method, confidence
        )
        values (?, 'wiki.gg', ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            source_page_index_id,
            pageid,
            title,
            slug,
            entity_id,
            entity["slug"],
            entity["canonical_title"],
            entity["kind"],
            method,
            confidence,
        ),
    )
