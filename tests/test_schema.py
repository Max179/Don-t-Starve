import sqlite3

from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_schema_can_upsert_sources_and_entities(tmp_path):
    db_path = tmp_path / "wiki.sqlite"
    conn = connect(db_path)
    init_db(conn)

    source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg/",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=18907,
        canonical_url="https://dontstarve.wiki.gg/wiki/Wilson",
        summary="Wilson is playable.",
    )

    row = conn.execute(
        "select canonical_title, kind from entities where id=?", (entity_id,)
    ).fetchone()
    assert tuple(row) == ("Wilson", "character")


def test_schema_has_auditable_raw_tables(tmp_path):
    conn = sqlite3.connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    tables = {
        row[0] for row in conn.execute("select name from sqlite_master where type='table'")
    }

    assert {
        "sources",
        "raw_pages",
        "entities",
        "entity_sources",
        "entity_attributes",
        "entity_images",
        "entity_relations",
        "verification_checks",
        "run_metadata",
    }.issubset(tables)
