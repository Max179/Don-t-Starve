import json

from dst_wiki_db.link_profiles import rebuild_entity_link_profiles
from dst_wiki_db.schema import connect, init_db, slugify, upsert_entity, upsert_source


def test_rebuild_entity_link_profiles_summarizes_resolved_and_unresolved_links(tmp_path):
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
    spear_id = upsert_entity(
        conn,
        canonical_title="Spear",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://example.test/Spear",
        summary="",
    )
    twigs_id = upsert_entity(
        conn,
        canonical_title="Twigs",
        kind="item",
        primary_source_id=source_id,
        primary_page_id=2,
        canonical_url="https://example.test/Twigs",
        summary="",
    )
    spider_id = upsert_entity(
        conn,
        canonical_title="Spider",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=3,
        canonical_url="https://example.test/Spider",
        summary="",
    )
    for pageid, title in enumerate(("Spear", "Spear Copy"), 1):
        conn.execute(
            """
            insert into raw_pages (
                source_id, pageid, ns, title, canonical_url, wikitext,
                categories_json, templates_json, images_json,
                externallinks_json, fetched_at
            )
            values (?, ?, 0, ?, 'https://example.test', '', '[]', '[]',
                    '[]', '[]', 'now')
            """,
            (source_id, pageid, title),
        )
    _link(conn, spear_id, source_id, "Twigs", twigs_id)
    _link(conn, spear_id, source_id, "Twigs", twigs_id, raw_page_id=2)
    _link(conn, spear_id, source_id, "Spider", spider_id)
    _link(conn, spear_id, source_id, "Missing Thing", None)

    result = rebuild_entity_link_profiles(conn)

    assert result == 1
    row = conn.execute(
        """
        select wiki_link_count, resolved_link_count, unresolved_link_count,
               unique_target_count, unique_resolved_target_count,
               unique_unresolved_target_count, target_kind_count,
               target_kind_counts_json, top_resolved_targets_json,
               top_unresolved_targets_json, has_wiki_links,
               has_resolved_links, has_unresolved_links
        from entity_link_profiles
        """
    ).fetchone()
    assert row["wiki_link_count"] == 4
    assert row["resolved_link_count"] == 3
    assert row["unresolved_link_count"] == 1
    assert row["unique_target_count"] == 3
    assert row["unique_resolved_target_count"] == 2
    assert row["unique_unresolved_target_count"] == 1
    assert row["target_kind_count"] == 2
    assert row["has_wiki_links"] == 1
    assert row["has_resolved_links"] == 1
    assert row["has_unresolved_links"] == 1
    assert json.loads(row["target_kind_counts_json"]) == [
        {"count": 2, "kind": "item"},
        {"count": 1, "kind": "mob"},
    ]
    assert json.loads(row["top_resolved_targets_json"])[0] == {
        "entity_id": twigs_id,
        "kind": "item",
        "link_count": 2,
        "slug": "twigs",
        "target_slug": "twigs",
        "target_title": "Twigs",
        "title": "Twigs",
    }
    assert json.loads(row["top_unresolved_targets_json"]) == [
        {"link_count": 1, "slug": "missing-thing", "title": "Missing Thing"}
    ]


def test_rebuild_entity_link_profiles_is_idempotent_without_links(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    assert rebuild_entity_link_profiles(conn) == 0
    assert rebuild_entity_link_profiles(conn) == 0


def _link(conn, entity_id, source_id, target_title, target_entity_id, raw_page_id=1):
    conn.execute(
        """
        insert into entity_relations (
            entity_id, source_id, raw_page_id, relation_type, target_title,
            target_slug, target_entity_id, raw_value
        )
        values (?, ?, ?, 'wikilink', ?, ?, ?, ?)
        """,
        (
            entity_id,
            source_id,
            raw_page_id,
            target_title,
            slugify(target_title),
            target_entity_id,
            target_title,
        ),
    )
