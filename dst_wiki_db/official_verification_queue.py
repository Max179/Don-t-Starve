from __future__ import annotations

import sqlite3


def rebuild_entity_official_verification_queue(conn: sqlite3.Connection) -> int:
    conn.execute("delete from entity_official_verification_queue")
    rows = conn.execute(
        """
        select
            cgq.entity_id,
            cgq.slug,
            cgq.canonical_title,
            cgq.kind,
            cgq.priority,
            cgq.readiness_score,
            cgq.readiness_status,
            cgq.source_coverage_status,
            cgq.media_status,
            coalesce(esc.source_profile_count, 0) as source_profile_count,
            coalesce(esc.matched_page_count, 0) as matched_source_page_count,
            coalesce(esc.best_source_key, '') as best_source_key,
            coalesce(esc.best_page_title, '') as best_page_title,
            coalesce(esc.best_page_url, '') as best_page_url
        from entity_completeness_gap_queue cgq
        left join entity_source_coverage esc on esc.entity_id = cgq.entity_id
        where cgq.missing_requirement = 'official_mentions'
        order by cgq.priority, cgq.readiness_score, cgq.canonical_title
        """
    ).fetchall()
    count = 0
    for row in rows:
        title = str(row["canonical_title"])
        conn.execute(
            """
            insert into entity_official_verification_queue (
                entity_id, slug, canonical_title, kind, priority,
                readiness_score, readiness_status, source_coverage_status,
                media_status, source_profile_count, matched_source_page_count,
                best_source_key, best_page_title, best_page_url,
                suggested_sources_text, official_search_query,
                steam_news_query, klei_query, candidate_reason, detected_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'klei|steam',
                    ?, ?, ?, 'missing_official_mentions', current_timestamp)
            """,
            (
                int(row["entity_id"]),
                str(row["slug"]),
                title,
                str(row["kind"]),
                int(row["priority"]),
                int(row["readiness_score"]),
                str(row["readiness_status"]),
                str(row["source_coverage_status"] or ""),
                str(row["media_status"] or ""),
                int(row["source_profile_count"]),
                int(row["matched_source_page_count"]),
                str(row["best_source_key"] or ""),
                str(row["best_page_title"] or ""),
                str(row["best_page_url"] or ""),
                _official_query(title),
                _steam_news_query(title),
                _klei_query(title),
            ),
        )
        count += 1
    conn.commit()
    return count


def _official_query(title: str) -> str:
    return f'"{title}" "Don\'t Starve" OR "Don\'t Starve Together" official'


def _steam_news_query(title: str) -> str:
    return f'"{title}" "Don\'t Starve Together" Steam news'


def _klei_query(title: str) -> str:
    return f'"{title}" site:klei.com OR site:forums.kleientertainment.com'
