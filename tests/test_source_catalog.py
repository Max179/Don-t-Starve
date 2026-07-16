from dst_wiki_db.schema import connect, init_db, upsert_source
from dst_wiki_db.source_catalog import rebuild_source_catalog


def test_rebuild_source_catalog_records_ranked_sources_and_evidence(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    wiki_source_id = upsert_source(
        conn,
        key="wiki.gg",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        role="canonical",
    )
    upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    conn.execute(
        """
        insert into source_audits (
            source_id, source_key, check_type, url, status, status_code,
            allowed, title, summary, payload_json
        )
        values (?, 'wiki.gg', 'mediawiki_siteinfo',
                'https://dontstarve.wiki.gg/api.php', 'restricted_by_robots',
                null, 0, 'MediaWiki siteinfo',
                'API access is marked restricted by robots/source policy.',
                '{}')
        """,
        (wiki_source_id,),
    )

    result = rebuild_source_catalog(conn)

    assert result == {"source_catalog": 8, "source_catalog_evidence": 18}
    catalog_rows = conn.execute(
        """
        select source_key, rank, tier, source_type, role, ingestion_status, source_id
        from source_catalog
        order by rank
        """
    ).fetchall()
    assert [tuple(row) for row in catalog_rows[:4]] == [
        (
            "wiki.gg",
            1,
            "primary",
            "community_wiki",
            "canonical_wiki",
            "permission_required",
            wiki_source_id,
        ),
        ("klei", 2, "official", "official_site", "official_verification", "active", None),
        ("steam", 3, "official", "official_api", "official_product_metadata", "active", None),
        (
            "fandom",
            4,
            "comparison",
            "community_wiki",
            "historical_comparison",
            "active_with_caution",
            catalog_rows[3]["source_id"],
        ),
    ]

    evidence_counts = {
        row["source_key"]: row["count"]
        for row in conn.execute(
            """
            select source_key, count(*) as count
            from source_catalog_evidence
            group by source_key
            """
        )
    }
    assert evidence_counts["wiki.gg"] == 4
    assert evidence_counts["klei"] == 3
    assert evidence_counts["steam"] == 3
    assert evidence_counts["fandom"] == 3
    assert evidence_counts["fextralife"] == 2


def test_rebuild_source_catalog_is_idempotent(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    first = rebuild_source_catalog(conn)
    second = rebuild_source_catalog(conn)

    assert first == second == {"source_catalog": 8, "source_catalog_evidence": 17}
    assert conn.execute("select count(*) from source_catalog").fetchone()[0] == 8
    assert conn.execute("select count(*) from source_catalog_evidence").fetchone()[0] == 17
