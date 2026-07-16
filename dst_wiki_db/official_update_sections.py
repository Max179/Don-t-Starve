from __future__ import annotations

import re
import sqlite3


HEADING_TYPES = {
    "Highlights Include": "highlights",
    "Highlights": "highlights",
    "Other Additions": "other_additions",
    "Bug Fixes": "bug_fixes",
    "Bug Fix": "bug_fixes",
    "Changes": "changes",
    "New Skins": "new_skins",
    "Login Rewards": "login_rewards",
    "Adjustments": "adjustments",
}
HEADING_PATTERN = re.compile(
    r"(?<![A-Za-z])(?P<heading>"
    + "|".join(re.escape(heading) for heading in sorted(HEADING_TYPES, key=len, reverse=True))
    + r")(?=\s|:|$|[A-Z])",
)
ITEM_STARTERS = (
    "Added",
    "Adjusted",
    "Changed",
    "Fixed",
    "Improved",
    "New",
    "Reduced",
    "Removed",
    "The",
    "A",
    "An",
)
ITEM_BOUNDARY_RE = re.compile(
    r"(?<=[.!?])(?:\s+(?=[A-Z0-9\"'(\[])|(?=(?:"
    + "|".join(re.escape(starter) for starter in ITEM_STARTERS)
    + r")\b))"
)


def rebuild_official_update_sections(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("delete from official_update_section_items")
    conn.execute("delete from official_update_sections")
    events = conn.execute(
        """
        select
            id, official_record_id, provider, external_id, content_text
        from official_update_events
        order by id
        """
    ).fetchall()

    section_count = 0
    item_count = 0
    for event in events:
        sections = _sections(str(event["content_text"] or ""))
        for section_index, (heading_text, section_type, body_text) in enumerate(sections):
            items = _items(body_text)
            cursor = conn.execute(
                """
                insert into official_update_sections (
                    official_update_event_id, official_record_id, provider, external_id,
                    section_index, heading_text, section_type, body_text, item_count
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(event["id"]),
                    int(event["official_record_id"]),
                    str(event["provider"]),
                    str(event["external_id"]),
                    section_index,
                    heading_text,
                    section_type,
                    body_text,
                    len(items),
                ),
            )
            official_update_section_id = int(cursor.lastrowid)
            section_count += 1
            for item_index, item_text in enumerate(items):
                conn.execute(
                    """
                    insert into official_update_section_items (
                        official_update_section_id, official_update_event_id,
                        official_record_id, provider, external_id, section_index,
                        section_type, item_index, item_text, character_length
                    )
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        official_update_section_id,
                        int(event["id"]),
                        int(event["official_record_id"]),
                        str(event["provider"]),
                        str(event["external_id"]),
                        section_index,
                        section_type,
                        item_index,
                        item_text,
                        len(item_text),
                    ),
                )
                item_count += 1
    conn.commit()
    return {
        "official_update_sections": section_count,
        "official_update_section_items": item_count,
    }


def _sections(content_text: str) -> list[tuple[str, str, str]]:
    text = " ".join(content_text.split())
    if not text:
        return []
    matches = list(HEADING_PATTERN.finditer(text))
    if not matches:
        return [("Body", "body", text)]

    sections: list[tuple[str, str, str]] = []
    if matches[0].start() > 0:
        intro = _clean_body(text[: matches[0].start()])
        if intro:
            sections.append(("Introduction", "introduction", intro))

    for index, match in enumerate(matches):
        start = match.end()
        if start < len(text) and text[start] == ":":
            start += 1
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = _clean_body(text[start:end])
        if not body:
            continue
        heading_text = _canonical_heading(match.group("heading"))
        sections.append((heading_text, HEADING_TYPES[heading_text], body))
    return sections or [("Body", "body", text)]


def _items(body_text: str) -> list[str]:
    chunks = [chunk.strip() for chunk in ITEM_BOUNDARY_RE.split(body_text) if chunk.strip()]
    return [_ensure_terminal_punctuation(chunk) for chunk in chunks]


def _canonical_heading(value: str) -> str:
    key = value.casefold()
    for heading in HEADING_TYPES:
        if heading.casefold() == key:
            return heading
    return value


def _clean_body(value: str) -> str:
    text = value.strip(" :")
    return " ".join(text.split())


def _ensure_terminal_punctuation(value: str) -> str:
    if value[-1] in ".!?":
        return value
    return f"{value}."
