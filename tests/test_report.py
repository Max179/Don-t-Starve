from dst_wiki_db.report import database_counts, sample_entities
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source
from scripts.inspect_database import main as inspect_main


def test_database_counts_and_samples(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg/",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    upsert_entity(
        conn,
        canonical_title="Wilson",
        kind="character",
        primary_source_id=source_id,
        primary_page_id=18907,
        canonical_url="https://dontstarve.wiki.gg/wiki/Wilson",
        summary="Wilson is playable.",
    )

    assert database_counts(conn)["entities"] == 1
    assert sample_entities(conn, limit=1) == [
        {
            "canonical_title": "Wilson",
            "kind": "character",
            "attribute_count": 0,
            "image_count": 0,
        }
    ]


def test_inspect_database_initializes_missing_new_tables(tmp_path, capsys):
    db_path = tmp_path / "old.sqlite"
    conn = connect(db_path)
    init_db(conn)
    conn.execute("drop table entity_fact_targets")
    conn.commit()
    conn.close()

    assert inspect_main([str(db_path)]) == 0

    output = capsys.readouterr().out
    assert '"entity_fact_targets": 0' in output
