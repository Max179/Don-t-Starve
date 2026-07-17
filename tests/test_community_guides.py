import json

from dst_wiki_db.community_guides import import_community_guides
from dst_wiki_db.schema import connect, init_db


def test_import_community_guides_loads_sources_topics_and_topic_index(tmp_path):
    seed = tmp_path / "guides.json"
    seed.write_text(
        json.dumps(
            {
                "generated_at": "2026-07-18T00:00:00+08:00",
                "scope": "Community guide curation",
                "source_records": [
                    {
                        "id": "bilibili-guide",
                        "platform": "Bilibili",
                        "title": "Beginner Guide",
                        "author": "A",
                        "url": "https://example.test/b",
                        "published": "2026-01-01",
                        "observed": "2026-07-18",
                        "reliability": "A",
                        "topics": ["beginner", "dst"],
                        "status": "accepted",
                        "notes": "Good route source.",
                    },
                    {
                        "id": "xiaohongshu-search",
                        "platform": "Xiaohongshu",
                        "title": "Search result",
                        "url": "https://example.test/x",
                        "observed": "2026-07-18",
                        "reliability": "blocked",
                        "topics": ["community_discovery"],
                        "status": "needs_login",
                        "notes": "Frontend shell only.",
                    },
                ],
                "topic_index": [
                    {
                        "topic": "beginner_route",
                        "recommended_sources": ["bilibili-guide"],
                        "verify": ["season timing", "boss timing"],
                    }
                ],
            }
        )
    )
    conn = connect(tmp_path / "wiki.sqlite")
    init_db(conn)

    result = import_community_guides(conn, seed)

    assert result == {
        "community_guide_sources": 2,
        "community_guide_topics": 3,
        "community_guide_topic_index": 1,
    }
    source = conn.execute(
        """
        select guide_id, platform, reliability, status, scope
        from community_guide_sources
        where guide_id = 'bilibili-guide'
        """
    ).fetchone()
    assert tuple(source) == (
        "bilibili-guide",
        "Bilibili",
        "A",
        "accepted",
        "Community guide curation",
    )
    topics = conn.execute(
        """
        select topic from community_guide_topics
        where guide_id = 'bilibili-guide'
        order by topic
        """
    ).fetchall()
    assert [row["topic"] for row in topics] == ["beginner", "dst"]
    topic_index = conn.execute(
        """
        select topic, recommended_source_ids, verify_text, source_count
        from community_guide_topic_index
        """
    ).fetchone()
    assert tuple(topic_index) == (
        "beginner_route",
        '["bilibili-guide"]',
        "season timing | boss timing",
        1,
    )
