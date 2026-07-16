from dst_wiki_db.official_update_sections import rebuild_official_update_sections
from dst_wiki_db.schema import connect, init_db


def _insert_event(conn, *, external_id: str, title: str, content_text: str) -> int:
    cursor = conn.execute(
        """
        insert into official_records (
            provider, record_type, external_id, title, url, status, summary, payload_json
        )
        values ('steam', 'news', ?, ?, 'https://example.test/news', 'ok', '', '{}')
        """,
        (external_id, title),
    )
    official_record_id = int(cursor.lastrowid)
    cursor = conn.execute(
        """
        insert into official_update_events (
            official_record_id, provider, record_type, external_id, appid,
            title, url, author, published_at_unix, published_at_iso,
            event_type, summary, content_text, content_length, mentioned_entity_count
        )
        values (?, 'steam', 'news', ?, 322330, ?,
                'https://example.test/news', 'KleiFish', 1700000000,
                '2023-11-14T22:13:20Z', 'hotfix', '', ?, ?, 2)
        """,
        (official_record_id, external_id, title, content_text, len(content_text)),
    )
    return int(cursor.lastrowid)


def test_rebuild_official_update_sections_extracts_headings_and_items(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _insert_event(
        conn,
        external_id="hotfix-1",
        title="Hotfix 740477",
        content_text=(
            "Changes Added Coals. Added Thermal Balm. "
            "Bug Fixes Fixed Beefalo duplication. Fixed crashes."
        ),
    )

    result = rebuild_official_update_sections(conn)

    assert result == {
        "official_update_sections": 2,
        "official_update_section_items": 4,
    }
    sections = conn.execute(
        """
        select section_index, heading_text, section_type, body_text, item_count
        from official_update_sections
        order by section_index
        """
    ).fetchall()
    assert [dict(row) for row in sections] == [
        {
            "section_index": 0,
            "heading_text": "Changes",
            "section_type": "changes",
            "body_text": "Added Coals. Added Thermal Balm.",
            "item_count": 2,
        },
        {
            "section_index": 1,
            "heading_text": "Bug Fixes",
            "section_type": "bug_fixes",
            "body_text": "Fixed Beefalo duplication. Fixed crashes.",
            "item_count": 2,
        },
    ]
    items = conn.execute(
        """
        select section_index, item_index, item_text, character_length
        from official_update_section_items
        order by section_index, item_index
        """
    ).fetchall()
    assert [dict(row) for row in items] == [
        {
            "section_index": 0,
            "item_index": 0,
            "item_text": "Added Coals.",
            "character_length": 12,
        },
        {
            "section_index": 0,
            "item_index": 1,
            "item_text": "Added Thermal Balm.",
            "character_length": 19,
        },
        {
            "section_index": 1,
            "item_index": 0,
            "item_text": "Fixed Beefalo duplication.",
            "character_length": 26,
        },
        {
            "section_index": 1,
            "item_index": 1,
            "item_text": "Fixed crashes.",
            "character_length": 14,
        },
    ]


def test_rebuild_official_update_sections_preserves_intro_before_first_heading(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _insert_event(
        conn,
        external_id="update-1",
        title="From Beyond",
        content_text=(
            "A forbidden path awaits. "
            "Highlights Added Waymark Compass. Added a new boss. "
            "Other Additions Added Heat Gland."
        ),
    )

    result = rebuild_official_update_sections(conn)

    assert result == {
        "official_update_sections": 3,
        "official_update_section_items": 4,
    }
    rows = conn.execute(
        """
        select section_index, heading_text, section_type, body_text
        from official_update_sections
        order by section_index
        """
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {
            "section_index": 0,
            "heading_text": "Introduction",
            "section_type": "introduction",
            "body_text": "A forbidden path awaits.",
        },
        {
            "section_index": 1,
            "heading_text": "Highlights",
            "section_type": "highlights",
            "body_text": "Added Waymark Compass. Added a new boss.",
        },
        {
            "section_index": 2,
            "heading_text": "Other Additions",
            "section_type": "other_additions",
            "body_text": "Added Heat Gland.",
        },
    ]


def test_rebuild_official_update_sections_falls_back_to_body_section(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _insert_event(
        conn,
        external_id="announcement-1",
        title="Announcement",
        content_text="A short announcement without named sections.",
    )

    result = rebuild_official_update_sections(conn)

    assert result == {
        "official_update_sections": 1,
        "official_update_section_items": 1,
    }
    row = conn.execute(
        """
        select heading_text, section_type, body_text, item_count
        from official_update_sections
        """
    ).fetchone()
    assert dict(row) == {
        "heading_text": "Body",
        "section_type": "body",
        "body_text": "A short announcement without named sections.",
        "item_count": 1,
    }


def test_rebuild_official_update_sections_does_not_split_prose_words(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _insert_event(
        conn,
        external_id="announcement-prose",
        title="Announcement",
        content_text=(
            "MegaChanges were not a heading. "
            "The update changes how survivors travel."
        ),
    )

    result = rebuild_official_update_sections(conn)

    assert result == {
        "official_update_sections": 1,
        "official_update_section_items": 2,
    }
    row = conn.execute(
        """
        select heading_text, section_type, body_text, item_count
        from official_update_sections
        """
    ).fetchone()
    assert dict(row) == {
        "heading_text": "Body",
        "section_type": "body",
        "body_text": (
            "MegaChanges were not a heading. "
            "The update changes how survivors travel."
        ),
        "item_count": 2,
    }


def test_rebuild_official_update_sections_handles_glued_headings_and_items(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _insert_event(
        conn,
        external_id="hotfix-glued",
        title="Hotfix 712852",
        content_text=(
            "ChangesClockworks can now only be befriended when stunned."
            "Bug FixesFixed Batilisks not engaging in combat."
            "Fixed Spider Warriors returning inside."
        ),
    )

    result = rebuild_official_update_sections(conn)

    assert result == {
        "official_update_sections": 2,
        "official_update_section_items": 3,
    }
    sections = conn.execute(
        """
        select section_index, heading_text, section_type, body_text, item_count
        from official_update_sections
        order by section_index
        """
    ).fetchall()
    assert [dict(row) for row in sections] == [
        {
            "section_index": 0,
            "heading_text": "Changes",
            "section_type": "changes",
            "body_text": "Clockworks can now only be befriended when stunned.",
            "item_count": 1,
        },
        {
            "section_index": 1,
            "heading_text": "Bug Fixes",
            "section_type": "bug_fixes",
            "body_text": (
                "Fixed Batilisks not engaging in combat."
                "Fixed Spider Warriors returning inside."
            ),
            "item_count": 2,
        },
    ]
    items = conn.execute(
        """
        select section_index, item_index, item_text
        from official_update_section_items
        order by section_index, item_index
        """
    ).fetchall()
    assert [tuple(row) for row in items] == [
        (0, 0, "Clockworks can now only be befriended when stunned."),
        (1, 0, "Fixed Batilisks not engaging in combat."),
        (1, 1, "Fixed Spider Warriors returning inside."),
    ]


def test_rebuild_official_update_sections_keeps_normal_sentence_boundaries(tmp_path):
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)
    _insert_event(
        conn,
        external_id="intro-sentences",
        title="Announcement",
        content_text=(
            "Welcome to the Constant. Survivors have returned! "
            "Players can explore together."
        ),
    )

    result = rebuild_official_update_sections(conn)

    assert result == {
        "official_update_sections": 1,
        "official_update_section_items": 3,
    }
    rows = conn.execute(
        """
        select item_index, item_text
        from official_update_section_items
        order by item_index
        """
    ).fetchall()
    assert [tuple(row) for row in rows] == [
        (0, "Welcome to the Constant."),
        (1, "Survivors have returned!"),
        (2, "Players can explore together."),
    ]
