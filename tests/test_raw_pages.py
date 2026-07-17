import pytest

from dst_wiki_db.raw_pages import (
    compress_raw_page_wikitexts,
    decode_wikitext,
    encode_wikitext,
)
from dst_wiki_db.schema import connect, init_db, upsert_source


def test_encode_and_decode_wikitext_round_trips_unicode():
    text = "Wilson says hello.\n饥荒 wiki evidence"

    encoded, encoding = encode_wikitext(text)

    assert encoding == "gzip"
    assert isinstance(encoded, bytes)
    assert decode_wikitext(encoded, encoding) == text
    assert decode_wikitext(text, "text") == text


def test_decode_wikitext_rejects_unknown_encoding():
    with pytest.raises(ValueError):
        decode_wikitext("x", "brotli")


def test_compress_raw_page_wikitexts_updates_plain_rows(tmp_path):
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
    conn.execute(
        """
        insert into raw_pages (
            source_id, pageid, ns, title, canonical_url, wikitext,
            categories_json, templates_json, images_json, externallinks_json,
            fetched_at
        )
        values (?, 1, 0, 'Wilson', 'https://example.test/Wilson',
                'plain wikitext', '[]', '[]', '[]', '[]', 'now')
        """,
        (source_id,),
    )

    result = compress_raw_page_wikitexts(conn)

    assert result == 1
    row = conn.execute(
        "select wikitext, wikitext_encoding from raw_pages"
    ).fetchone()
    assert row["wikitext_encoding"] == "gzip"
    assert decode_wikitext(row["wikitext"], row["wikitext_encoding"]) == "plain wikitext"
    assert compress_raw_page_wikitexts(conn) == 0
