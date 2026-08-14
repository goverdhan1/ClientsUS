"""Daily discovery run: search multiple public sources for US development demand."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .lead_sync import sync_leads_from_public_sources
from .openweb import DEFAULT_SERVICE_QUERIES, fetch_datagov, fetch_sam_gov, fetch_usajobs

SOURCE_FETCHERS = {
    "sam": fetch_sam_gov,
    "datagov": fetch_datagov,
    "usajobs": fetch_usajobs,
}


def run_daily_search(
    *,
    queries: list[tuple[str, str]] | None = None,
    limit_per_query: int = 5,
    report_dir: Path,
    leads_csv: Path | None = None,
    sync_leads: bool = True,
) -> tuple[Path, dict | None]:
    """Run all configured searches, write a dated report, optionally sync leads.csv."""
    queries = queries or DEFAULT_SERVICE_QUERIES
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"daily_{date.today().isoformat()}.txt"

    lines: list[str] = [
        f"ClientsUS daily search — {date.today().isoformat()}",
        "=" * 60,
        "",
        "These are PUBLIC solicitations and job postings (organizations actively",
        "seeking development help). Respond through each posting's official channel,",
        "or add consented contacts to data/leads.csv before emailing/WhatsApp.",
        "",
    ]
    total = 0
    errors: list[str] = []

    for keyword, source in queries:
        fetcher = SOURCE_FETCHERS.get(source)
        if fetcher is None:
            errors.append(f"unknown source {source!r} for query {keyword!r}")
            continue
        lines.append(f"## {keyword} ({source})")
        lines.append("")
        try:
            results = fetcher(keyword, limit_per_query)
        except Exception as exc:
            msg = f"FAILED {source}/{keyword}: {exc}"
            errors.append(msg)
            lines.append(f"  (lookup failed: {exc})")
            lines.append("")
            continue
        if not results:
            lines.append("  No results.")
        for item in results:
            total += 1
            title = item.get("title", "")
            org = item.get("organization", "")
            url = item.get("url", "")
            posted = item.get("posted", "")
            lines.append(f"- {title}")
            if org:
                lines.append(f"  Organization: {org}")
            if posted:
                lines.append(f"  Posted: {posted}")
            if url:
                lines.append(f"  URL: {url}")
            email = item.get("email", "")
            if email:
                lines.append(f"  Contact email: {email}")
            lines.append("")
        lines.append("")

    sync_summary: dict | None = None
    if sync_leads and leads_csv is not None:
        sync_summary = sync_leads_from_public_sources(
            leads_csv, limit_per_query=limit_per_query
        )
        lines.extend([
            "## Leads sync (SAM.gov public contacts)",
            "",
            f"  New contacts added to {leads_csv}: {sync_summary['added']}",
            f"  Skipped (duplicate/invalid): {sync_summary['skipped']}",
            f"  Candidates with email found: {sync_summary['candidates_found']}",
            "",
        ])
        if sync_summary["errors"]:
            lines.append("  Sync notes:")
            for err in sync_summary["errors"]:
                lines.append(f"    - {err}")
            lines.append("")

    lines.extend([
        "=" * 60,
        f"Total listings: {total}",
    ])
    if errors:
        lines.append("")
        lines.append("Errors:")
        lines.extend(f"  - {e}" for e in errors)

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path, sync_summary
