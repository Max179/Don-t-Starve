from __future__ import annotations

from pathlib import Path
import json
import sqlite3
from typing import Any


def import_community_guides(
    conn: sqlite3.Connection, path: Path | str
) -> dict[str, int]:
    payload = json.loads(Path(path).read_text())
    conn.execute("delete from community_guide_topic_index")
    conn.execute("delete from community_guide_topics")
    conn.execute("delete from community_guide_sources")
    scope = str(payload.get("scope") or "")
    generated_at = str(payload.get("generated_at") or "")
    source_count = 0
    topic_count = 0
    for record in payload.get("source_records", []):
        guide_id = str(record["id"])
        cursor = conn.execute(
            """
            insert into community_guide_sources (
                guide_id, platform, title, author, url, published, updated,
                observed, reliability, status, notes, scope, generated_at,
                imported_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, current_timestamp)
            """,
            (
                guide_id,
                str(record.get("platform") or ""),
                str(record.get("title") or ""),
                str(record.get("author") or ""),
                str(record.get("url") or ""),
                _optional_text(record.get("published")),
                _optional_text(record.get("updated")),
                str(record.get("observed") or ""),
                str(record.get("reliability") or ""),
                str(record.get("status") or ""),
                str(record.get("notes") or ""),
                scope,
                generated_at,
            ),
        )
        guide_source_id = int(cursor.lastrowid)
        source_count += 1
        for topic in record.get("topics", []):
            conn.execute(
                """
                insert or ignore into community_guide_topics (
                    guide_source_id, guide_id, topic
                )
                values (?, ?, ?)
                """,
                (guide_source_id, guide_id, str(topic)),
            )
            topic_count += 1
    topic_index_count = 0
    for entry in payload.get("topic_index", []):
        recommended = [str(value) for value in entry.get("recommended_sources", [])]
        verify = [str(value) for value in entry.get("verify", [])]
        conn.execute(
            """
            insert into community_guide_topic_index (
                topic, recommended_source_ids, verify_text, source_count
            )
            values (?, ?, ?, ?)
            """,
            (
                str(entry.get("topic") or ""),
                json.dumps(recommended, ensure_ascii=False),
                " | ".join(verify),
                len(recommended),
            ),
        )
        topic_index_count += 1
    conn.commit()
    return {
        "community_guide_sources": source_count,
        "community_guide_topics": topic_count,
        "community_guide_topic_index": topic_index_count,
    }


def _optional_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
