from __future__ import annotations

import gzip
import sqlite3


TEXT_ENCODING = "text"
GZIP_ENCODING = "gzip"


def encode_wikitext(wikitext: str) -> tuple[bytes, str]:
    return gzip.compress(wikitext.encode("utf-8"), compresslevel=9), GZIP_ENCODING


def decode_wikitext(value: object, encoding: str | None = None) -> str:
    normalized = encoding or TEXT_ENCODING
    if normalized == TEXT_ENCODING:
        if isinstance(value, bytes):
            return value.decode("utf-8")
        return str(value or "")
    if normalized == GZIP_ENCODING:
        payload = bytes(value or b"")
        return gzip.decompress(payload).decode("utf-8")
    raise ValueError(f"Unsupported wikitext encoding: {normalized}")


def compress_raw_page_wikitexts(conn: sqlite3.Connection) -> int:
    rows = conn.execute(
        """
        select id, wikitext, wikitext_encoding
        from raw_pages
        where wikitext_encoding = 'text'
        order by id
        """
    ).fetchall()
    count = 0
    for row in rows:
        encoded, encoding = encode_wikitext(
            decode_wikitext(row["wikitext"], row["wikitext_encoding"])
        )
        conn.execute(
            """
            update raw_pages
            set wikitext = ?,
                wikitext_encoding = ?
            where id = ?
            """,
            (encoded, encoding, int(row["id"])),
        )
        count += 1
    conn.commit()
    return count
