from dst_wiki_db.facts import extract_link_facts, rebuild_entity_facts
from dst_wiki_db.schema import connect, init_db, upsert_entity, upsert_source


def test_extract_link_facts_reads_targets_probability_and_quantity():
    facts = extract_link_facts("24px|link=Meat 75%, 24px|link=Pig Skin 25%, link=Gears×2")

    assert facts == [
        {"target_title": "Meat", "probability_text": "75%", "quantity_text": None},
        {"target_title": "Pig Skin", "probability_text": "25%", "quantity_text": None},
        {"target_title": "Gears", "probability_text": None, "quantity_text": "×2"},
    ]


def test_extract_link_facts_removes_icon_and_parenthetical_suffixes():
    facts = extract_link_facts(
        "buy from 24px|link=Mumsy for 24px|link=Coin×3, 24px|link=Wilson (shaving 22px)"
    )

    assert facts == [
        {"target_title": "Mumsy", "probability_text": None, "quantity_text": None},
        {"target_title": "Coin", "probability_text": None, "quantity_text": "×3"},
        {"target_title": "Wilson", "probability_text": None, "quantity_text": None},
    ]


def test_rebuild_entity_facts_derives_relation_like_attributes(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    source_id = upsert_source(
        conn,
        key="fandom",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com/",
        api_url="https://dontstarve.fandom.com/api.php",
        role="comparison",
    )
    entity_id = upsert_entity(
        conn,
        canonical_title="Pig",
        kind="mob",
        primary_source_id=source_id,
        primary_page_id=1,
        canonical_url="https://dontstarve.fandom.com/wiki/Pig",
        summary="Pig.",
    )
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, revid, canonical_url, wikitext, fetched_at
        )
        values (?, 1, 0, 'Pig', 100, 'https://dontstarve.fandom.com/wiki/Pig', 'body', 'now')
        """,
        (source_id,),
    )
    raw_page_id = conn.execute("select id from raw_pages").fetchone()["id"]
    conn.execute(
        """
        insert into entity_attributes (
            entity_id, source_id, raw_page_id, template_index, template_name, raw_name,
            canonical_name, value_text, variant_key
        )
        values (?, ?, ?, 0, 'Mob Infobox', 'drops', 'drops', '24px|link=Meat 75%, 24px|link=Pig Skin 25%', '')
        """,
        (entity_id, source_id, raw_page_id),
    )

    count = rebuild_entity_facts(conn)

    rows = conn.execute(
        """
        select fact_type, target_title, probability_text
        from entity_facts
        where entity_id=?
        order by target_title
        """,
        (entity_id,),
    ).fetchall()
    assert count == 2
    assert [tuple(row) for row in rows] == [
        ("drops", "Meat", "75%"),
        ("drops", "Pig Skin", "25%"),
    ]
