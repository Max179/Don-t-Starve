from dst_wiki_db.schema import connect, init_db, upsert_source
from dst_wiki_db.source_gap_import import import_source_gap_pages


def test_import_source_gap_pages_writes_raw_and_parsed_entities(tmp_path):
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
    _gap(conn, source_id, 10, "Ancient Fuelweaver")
    _gap(conn, source_id, 11, "Ammo Pouch")
    client = FakeClient(
        [
            {
                "pageid": 11,
                "ns": 0,
                "title": "Ammo Pouch",
                "revisions": [
                    {
                        "revid": 100,
                        "timestamp": "2026-07-01T00:00:00Z",
                        "slots": {
                            "main": {
                                "content": "{{Item Infobox|image=Ammo Pouch.png|spawnCode=ammopouch}}\nThe Ammo Pouch is an item.\n[[Category:Items]]"
                            }
                        },
                    }
                ],
                "categories": [{"title": "Category:Items"}],
                "templates": [{"title": "Template:Item Infobox"}],
                "images": [{"title": "File:Ammo Pouch.png"}],
                "externallinks": [],
            }
        ]
    )

    result = import_source_gap_pages(
        conn,
        source_key="wiki.gg",
        gap_type="potential_new_entity",
        limit=1,
        batch_size=1,
        client=client,
    )

    assert result == {
        "source_key": "wiki.gg",
        "gap_type": "potential_new_entity",
        "selected_gaps": 1,
        "pages_seen": 1,
        "pages_imported": 1,
        "entities_written": 1,
        "images_registered": 1,
        "verification_checks": 1,
    }
    entity = conn.execute(
        "select canonical_title, kind, primary_source_id from entities"
    ).fetchone()
    assert tuple(entity) == ("Ammo Pouch", "item", source_id)
    raw_page = conn.execute(
        """
        select title, wikitext_encoding
        from raw_pages
        where source_id = ?
        """,
        (source_id,),
    ).fetchone()
    assert tuple(raw_page) == ("Ammo Pouch", "gzip")
    attributes = {
        row["canonical_name"]: row["value_text"]
        for row in conn.execute(
            """
            select canonical_name, value_text
            from entity_attributes
            """
        )
    }
    assert attributes["spawn_code"] == "ammopouch"
    image = conn.execute("select image_name, role from entity_images").fetchone()
    assert tuple(image) == ("Ammo Pouch.png", "image")
    verification = conn.execute(
        """
        select check_type, source_key, status
        from verification_checks
        """
    ).fetchone()
    assert tuple(verification) == ("source_presence", "wiki.gg", "present")
    assert client.requested_titles == [["Ammo Pouch"]]


def _gap(conn, source_id, pageid, title):
    slug = title.lower().replace(" ", "-")
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
    conn.execute(
        """
        insert into source_page_gaps (
            source_page_index_id, source_key, source_pageid, title, title_slug,
            page_url, gap_type, priority, notes
        )
        values (?, 'wiki.gg', ?, ?, ?,
                'https://dontstarve.wiki.gg/wiki/' || replace(?, ' ', '_'),
                'potential_new_entity', 10, 'test')
        """,
        (source_page_index_id, pageid, title, slug, title),
    )


class FakeClient:
    def __init__(self, pages):
        self.pages = list(pages)
        self.requested_titles = []

    def fetch_siteinfo(self):
        return {"query": {"statistics": {"articles": 1}}}

    def fetch_page_batch(self, titles):
        self.requested_titles.append(list(titles))
        return self.pages[: len(titles)]
