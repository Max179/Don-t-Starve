from __future__ import annotations

from dataclasses import dataclass
import sqlite3


VERIFIED_DATE = "2026-07-17"


@dataclass(frozen=True)
class SourceCatalogEntry:
    source_key: str
    rank: int
    tier: str
    source_type: str
    role: str
    name: str
    base_url: str
    api_url: str | None
    access_method: str
    ingestion_status: str
    license_summary: str
    coverage_summary: str
    verification_use: str
    notes: str
    evidence: tuple[tuple[str, str, str, str, str], ...]


CATALOG_ENTRIES = (
    SourceCatalogEntry(
        source_key="wiki.gg",
        rank=1,
        tier="primary",
        source_type="community_wiki",
        role="canonical_wiki",
        name="Don't Starve Wiki",
        base_url="https://dontstarve.wiki.gg",
        api_url="https://dontstarve.wiki.gg/api.php",
        access_method="MediaWiki pages, approved dump, or API with permission",
        ingestion_status="permission_required",
        license_summary="CC BY-SA 4.0 siteinfo; respect wiki.gg robots and permissions.",
        coverage_summary="Current canonical community wiki for Don't Starve and DST mechanics, entities, images, and variants.",
        verification_use="Primary community facts once approved bulk access or dump is available.",
        notes="Do not call restricted API paths without permission; use approved dumps when provided.",
        evidence=(
            (
                "search_result",
                "search",
                "https://dontstarve.wiki.gg/wiki/Don%27t_Starve_Wiki",
                "Don't Starve Wiki on wiki.gg",
                "Top community wiki result and canonical current wiki host.",
            ),
            (
                "siteinfo",
                "source_audit",
                "https://dontstarve.wiki.gg/api.php",
                "MediaWiki siteinfo",
                "Prior audit observed the largest community-wiki article and image counts.",
            ),
            (
                "robots_policy",
                "source_audit",
                "https://dontstarve.wiki.gg/robots.txt",
                "wiki.gg robots policy",
                "Robots/source policy marks API access restricted for this project by default.",
            ),
        ),
    ),
    SourceCatalogEntry(
        source_key="klei",
        rank=2,
        tier="official",
        source_type="official_site",
        role="official_verification",
        name="Klei Entertainment",
        base_url="https://www.klei.com",
        api_url=None,
        access_method="Official pages, forums, and update posts",
        ingestion_status="active",
        license_summary="Official source; store facts, URLs, and short summaries rather than bulk-copying text.",
        coverage_summary="Official product pages, announcements, update notes, release and mechanics verification.",
        verification_use="Highest authority for whether an item, character, update, or mechanic is official.",
        notes="Forum endpoints may be intermittently blocked; preserve failed probes.",
        evidence=(
            (
                "official_page",
                "klei",
                "https://www.klei.com/games/dont-starve-together",
                "Klei Don't Starve Together page",
                "Official game page for DST.",
            ),
            (
                "official_updates",
                "klei",
                "https://forums.kleientertainment.com/game-updates/dst/",
                "Klei DST game updates",
                "Official update forum path for DST patch notes and announcements.",
            ),
            (
                "official_page",
                "klei",
                "https://www.klei.com/games/dont-starve",
                "Klei Don't Starve page",
                "Official game page for Don't Starve.",
            ),
        ),
    ),
    SourceCatalogEntry(
        source_key="steam",
        rank=3,
        tier="official",
        source_type="official_api",
        role="official_product_metadata",
        name="Steam Store / Steam Web API",
        base_url="https://store.steampowered.com",
        api_url="https://store.steampowered.com/api/appdetails",
        access_method="Steam appdetails, DLC ids, news, and store pages",
        ingestion_status="active",
        license_summary="Official product metadata and media rights belong to Valve/Klei/rightsholders.",
        coverage_summary="Official app ids, DLC catalog, product metadata, screenshots, store descriptions, and Steam news.",
        verification_use="Cross-check product ids, release metadata, DLC media, and Steam news events.",
        notes="Already used for official_records, products, product media, update events, and update sections.",
        evidence=(
            (
                "official_api",
                "steam",
                "https://store.steampowered.com/api/appdetails?appids=322330&filters=basic",
                "Steam appdetails 322330",
                "Official Steam API metadata for Don't Starve Together.",
            ),
            (
                "official_api",
                "steam",
                "https://store.steampowered.com/api/appdetails?appids=219740&filters=basic",
                "Steam appdetails 219740",
                "Official Steam API metadata for Don't Starve.",
            ),
            (
                "official_news",
                "steam",
                "https://steamcommunity.com/app/322330/allnews/",
                "Steam DST news",
                "Official Steam news stream for DST update and event posts.",
            ),
        ),
    ),
    SourceCatalogEntry(
        source_key="fandom",
        rank=4,
        tier="comparison",
        source_type="community_wiki",
        role="historical_comparison",
        name="Don't Starve Wiki on Fandom",
        base_url="https://dontstarve.fandom.com",
        api_url="https://dontstarve.fandom.com/api.php",
        access_method="MediaWiki API with low request rate and cached raw pages",
        ingestion_status="active_with_caution",
        license_summary="CC BY-SA / Fandom licensing; preserve attribution and revision evidence.",
        coverage_summary="Historical community wiki with page history, older content, and cross-source comparison value.",
        verification_use="Compare against wiki.gg titles, variants, images, categories, and older mechanics.",
        notes="Current committed database is a full Fandom historical comparison build.",
        evidence=(
            (
                "search_result",
                "search",
                "https://dontstarve.fandom.com/wiki/Don%27t_Starve_Wiki",
                "Don't Starve Wiki on Fandom",
                "High-ranking historical wiki result and existing comparison corpus.",
            ),
            (
                "siteinfo",
                "source_audit",
                "https://dontstarve.fandom.com/api.php",
                "Fandom MediaWiki siteinfo",
                "Prior audit returned usable siteinfo and current committed corpus statistics.",
            ),
            (
                "robots_policy",
                "source_audit",
                "https://dontstarve.fandom.com/robots.txt",
                "Fandom robots probe",
                "Prior audit captured Cloudflare/robots access behavior for traceability.",
            ),
        ),
    ),
    SourceCatalogEntry(
        source_key="fextralife",
        rank=5,
        tier="competitor",
        source_type="guide_wiki",
        role="competitor_reference",
        name="Don't Starve Wiki on Fextralife",
        base_url="https://dontstarve.wiki.fextralife.com",
        api_url=None,
        access_method="Lightweight manual/reference checks only",
        ingestion_status="reference_only",
        license_summary="Competitor guide/wiki site; verify terms before any reuse.",
        coverage_summary="Guide-style pages for characters, items, and gameplay topics; less canonical than wiki.gg/Fandom.",
        verification_use="Spot-check competitor coverage gaps and alternate terminology.",
        notes="Not currently used for bulk ingestion.",
        evidence=(
            (
                "search_result",
                "search",
                "https://dontstarve.wiki.fextralife.com/Don't+Starve+Wiki",
                "Don't Starve Wiki on Fextralife",
                "Visible third-party guide/wiki source in general web search.",
            ),
            (
                "competitor_reference",
                "manual_review",
                "https://dontstarve.wiki.fextralife.com/Items",
                "Fextralife Items",
                "Useful as a competitor coverage check for item pages.",
            ),
        ),
    ),
    SourceCatalogEntry(
        source_key="wikipedia",
        rank=6,
        tier="context",
        source_type="encyclopedia",
        role="general_context",
        name="Wikipedia",
        base_url="https://en.wikipedia.org",
        api_url="https://en.wikipedia.org/w/api.php",
        access_method="Manual context checks; not a mechanics database",
        ingestion_status="reference_only",
        license_summary="CC BY-SA; preserve attribution if facts are incorporated.",
        coverage_summary="General encyclopedia context for game identity, release history, and reception.",
        verification_use="High-level product context only, not entity stats or mechanics.",
        notes="Not suitable as a detailed wiki data source.",
        evidence=(
            (
                "search_result",
                "search",
                "https://en.wikipedia.org/wiki/Don%27t_Starve",
                "Don't Starve on Wikipedia",
                "General encyclopedia reference for release and product context.",
            ),
        ),
    ),
    SourceCatalogEntry(
        source_key="reddit",
        rank=7,
        tier="community_signal",
        source_type="community_discussion",
        role="source_discovery_signal",
        name="Reddit / r/dontstarve",
        base_url="https://www.reddit.com/r/dontstarve",
        api_url=None,
        access_method="Manual source discovery and migration-signal checks",
        ingestion_status="reference_only",
        license_summary="Community discussion; do not bulk-copy posts into the database.",
        coverage_summary="Community discussions can reveal source migrations, coverage complaints, and active-data gaps.",
        verification_use="Signal only; facts must be verified against wiki or official sources.",
        notes="Useful for finding current source consensus, not for canonical mechanics.",
        evidence=(
            (
                "community_signal",
                "reddit",
                "https://www.reddit.com/r/dontstarve/",
                "r/dontstarve",
                "Community signal for active wiki/source discussions and gaps.",
            ),
        ),
    ),
    SourceCatalogEntry(
        source_key="patchbot",
        rank=8,
        tier="community_signal",
        source_type="patch_tracker",
        role="update_discovery_signal",
        name="PatchBot",
        base_url="https://patchbot.io",
        api_url=None,
        access_method="Manual update discovery checks",
        ingestion_status="reference_only",
        license_summary="Third-party patch tracker; verify terms before reuse.",
        coverage_summary="Patch/update tracking signal that can help discover official posts to verify elsewhere.",
        verification_use="Discovery only; verify patch facts against Klei or Steam official records.",
        notes="Not currently used for canonical storage.",
        evidence=(
            (
                "patch_tracker",
                "patchbot",
                "https://patchbot.io/games/dont-starve-together",
                "PatchBot Don't Starve Together",
                "Community patch tracker useful for update discovery.",
            ),
        ),
    ),
)


def rebuild_source_catalog(conn: sqlite3.Connection) -> dict[str, int]:
    conn.execute("delete from source_catalog_evidence")
    conn.execute("delete from source_catalog")

    source_ids = {
        row["key"]: int(row["id"])
        for row in conn.execute("select id, key from sources").fetchall()
    }
    catalog_count = 0
    evidence_count = 0
    for entry in CATALOG_ENTRIES:
        source_id = source_ids.get(entry.source_key)
        cursor = conn.execute(
            """
            insert into source_catalog (
                source_id, source_key, rank, tier, source_type, role, name,
                base_url, api_url, access_method, ingestion_status,
                license_summary, coverage_summary, verification_use, notes,
                last_verified
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                source_id,
                entry.source_key,
                entry.rank,
                entry.tier,
                entry.source_type,
                entry.role,
                entry.name,
                entry.base_url,
                entry.api_url,
                entry.access_method,
                entry.ingestion_status,
                entry.license_summary,
                entry.coverage_summary,
                entry.verification_use,
                entry.notes,
                VERIFIED_DATE,
            ),
        )
        catalog_id = int(cursor.lastrowid)
        catalog_count += 1
        for evidence in entry.evidence:
            evidence_count += _insert_evidence(
                conn,
                catalog_id=catalog_id,
                source_id=source_id,
                source_key=entry.source_key,
                evidence_type=evidence[0],
                provider=evidence[1],
                url=evidence[2],
                title=evidence[3],
                summary=evidence[4],
                checked_date=VERIFIED_DATE,
            )
        for audit in _audit_evidence(conn, entry.source_key):
            evidence_count += _insert_evidence(
                conn,
                catalog_id=catalog_id,
                source_id=source_id,
                source_key=entry.source_key,
                evidence_type="source_audit",
                provider="source_audit",
                url=str(audit["url"]),
                title=str(audit["title"]),
                summary=str(audit["summary"] or audit["status"]),
                checked_date=str(audit["checked_at"])[:10],
            )
    conn.commit()
    return {
        "source_catalog": catalog_count,
        "source_catalog_evidence": evidence_count,
    }


def _insert_evidence(
    conn: sqlite3.Connection,
    *,
    catalog_id: int,
    source_id: int | None,
    source_key: str,
    evidence_type: str,
    provider: str,
    url: str,
    title: str,
    summary: str,
    checked_date: str,
) -> int:
    conn.execute(
        """
        insert into source_catalog_evidence (
            source_catalog_id, source_id, source_key, evidence_type, provider,
            url, title, summary, checked_date
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            catalog_id,
            source_id,
            source_key,
            evidence_type,
            provider,
            url,
            title,
            summary,
            checked_date,
        ),
    )
    return 1


def _audit_evidence(conn: sqlite3.Connection, source_key: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select url, title, summary, status, checked_at
        from source_audits
        where source_key=?
        order by check_type, url
        """,
        (source_key,),
    ).fetchall()
