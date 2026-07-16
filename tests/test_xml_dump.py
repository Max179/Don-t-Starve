import json

from dst_wiki_db.schema import connect, init_db
from dst_wiki_db.xml_dump import import_mediawiki_xml_dump, iter_mediawiki_xml_dump_pages


SAMPLE_DUMP = """<?xml version="1.0" encoding="utf-8"?>
<mediawiki xmlns="http://www.mediawiki.org/xml/export-0.11/">
  <siteinfo>
    <sitename>Don't Starve Wiki</sitename>
    <base>https://dontstarve.wiki.gg/wiki/Don%27t_Starve_Wiki</base>
    <generator>MediaWiki 1.43.1</generator>
    <case>first-letter</case>
  </siteinfo>
  <page>
    <title>Wilson</title>
    <ns>0</ns>
    <id>18907</id>
    <revision>
      <id>568062</id>
      <timestamp>2026-07-01T00:00:00Z</timestamp>
      <text xml:space="preserve">{{Character Infobox
|image dst=Wilson Original Portrait.png
|health dst=150
|spawnCode dst="wilson"
}}
'''Wilson''' is a playable [[character]].
[[Category:Characters]]
</text>
    </revision>
  </page>
  <page>
    <title>Redirect Page</title>
    <ns>0</ns>
    <id>2</id>
    <redirect title="Wilson" />
    <revision>
      <id>3</id>
      <timestamp>2026-07-01T00:00:00Z</timestamp>
      <text>#REDIRECT [[Wilson]]</text>
    </revision>
  </page>
  <page>
    <title>Template:Character Infobox</title>
    <ns>10</ns>
    <id>4</id>
    <revision>
      <id>5</id>
      <timestamp>2026-07-01T00:00:00Z</timestamp>
      <text>template body</text>
    </revision>
  </page>
</mediawiki>
"""


def test_iter_mediawiki_xml_dump_pages_reads_mainspace_non_redirects(tmp_path):
    dump_path = tmp_path / "sample.xml"
    dump_path.write_text(SAMPLE_DUMP)

    pages = list(iter_mediawiki_xml_dump_pages(dump_path))

    assert len(pages) == 1
    page = pages[0]
    assert page.title == "Wilson"
    assert page.pageid == 18907
    assert page.revid == 568062
    assert page.timestamp == "2026-07-01T00:00:00Z"
    assert "Character Infobox" in page.text


def test_import_mediawiki_xml_dump_writes_existing_database_shape(tmp_path):
    dump_path = tmp_path / "sample.xml"
    dump_path.write_text(SAMPLE_DUMP)
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    result = import_mediawiki_xml_dump(
        conn,
        dump_path=dump_path,
        source_key="wiki.gg",
    )

    assert result == {
        "source": "wiki.gg",
        "pages_seen": 1,
        "pages_written": 1,
        "entities_written": 1,
        "images_registered": 1,
    }
    source = conn.execute(
        "select key, fetched_at is not null, siteinfo_json from sources where key='wiki.gg'"
    ).fetchone()
    assert source["key"] == "wiki.gg"
    assert source[1] == 1
    assert json.loads(source["siteinfo_json"]) == {
        "base": "https://dontstarve.wiki.gg/wiki/Don%27t_Starve_Wiki",
        "case": "first-letter",
        "generator": "MediaWiki 1.43.1",
        "sitename": "Don't Starve Wiki",
    }
    entity = conn.execute(
        "select canonical_title, kind, canonical_url from entities"
    ).fetchone()
    assert tuple(entity) == (
        "Wilson",
        "character",
        "https://dontstarve.wiki.gg/wiki/Wilson",
    )
    raw = conn.execute("select title, categories_json, templates_json, images_json from raw_pages").fetchone()
    assert raw["title"] == "Wilson"
    assert json.loads(raw["categories_json"]) == [{"title": "Category:Characters"}]
    assert json.loads(raw["templates_json"]) == [{"title": "Template:Character Infobox"}]
    assert json.loads(raw["images_json"]) == [{"title": "File:Wilson Original Portrait.png"}]
    attribute = conn.execute(
        "select canonical_name, value_number, variant_key from entity_attributes where raw_name='health dst'"
    ).fetchone()
    assert tuple(attribute) == ("health", 150, "dst")
    image = conn.execute("select image_name, role, variant_key from entity_images").fetchone()
    assert tuple(image) == ("Wilson Original Portrait.png", "image dst", "dst")
