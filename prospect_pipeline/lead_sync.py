"""Merge publicly listed procurement contacts into data/leads.csv."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from .models import EMAIL_RE, Lead, load_leads_csv
from .openweb import DEFAULT_SERVICE_QUERIES, fetch_sam_gov

SOLNUM_RE = re.compile(r"sam:([A-Za-z0-9\-]+)")
KEYWORD_SERVICE = {
    "website": "website development",
    "wordpress": "website development",
    "software": "custom software development",
    "mobile": "mobile app development",
    "android": "mobile app development",
    "ios": "mobile app development",
    "application": "custom software development",
}


@dataclass
class LeadCandidate:
    business_name: str
    email: str
    state: str
    contact_name: str = ""
    services_interest: str = ""
    source: str = ""
    external_id: str = ""
    notes: str = ""


def _service_from_keyword(keyword: str) -> str:
    lower = keyword.lower()
    for token, label in KEYWORD_SERVICE.items():
        if token in lower:
            return label
    return "web, software, or mobile development"


def _existing_solnums(leads: list[Lead], rows_raw: list[dict]) -> set[str]:
    found: set[str] = set()
    for lead in leads:
        for match in SOLNUM_RE.finditer(lead.notes):
            found.add(match.group(1))
    for row in rows_raw:
        for match in SOLNUM_RE.finditer(row.get("notes", "")):
            found.add(match.group(1))
        ext = (row.get("external_id") or "").strip()
        if ext.startswith("sam:"):
            found.add(ext[4:])
    return found


def _existing_emails(leads: list[Lead], rows_raw: list[dict]) -> set[str]:
    emails = {lead.normalized_email for lead in leads if lead.email.strip()}
    for row in rows_raw:
        email = (row.get("email") or "").strip().lower()
        if email:
            emails.add(email)
    return emails


def discover_lead_candidates(
    *,
    queries: list[tuple[str, str]] | None = None,
    limit_per_query: int = 5,
) -> tuple[list[LeadCandidate], list[str]]:
    """Collect email contacts from public APIs (SAM.gov POC emails only)."""
    queries = queries or DEFAULT_SERVICE_QUERIES
    candidates: list[LeadCandidate] = []
    errors: list[str] = []
    seen_ids: set[str] = set()

    for keyword, source in queries:
        if source != "sam":
            continue
        try:
            results = fetch_sam_gov(keyword, limit_per_query)
        except Exception as exc:
            errors.append(f"{source}/{keyword}: {exc}")
            continue
        for item in results:
            email = (item.get("email") or "").strip().lower()
            if not email or not EMAIL_RE.match(email):
                continue
            solnum = (item.get("solicitation_number") or "").strip()
            external_id = f"sam:{solnum}" if solnum else ""
            dedupe_key = external_id or email
            if dedupe_key in seen_ids:
                continue
            seen_ids.add(dedupe_key)
            candidates.append(
                LeadCandidate(
                    business_name=item.get("organization") or item.get("title") or "US Agency",
                    email=email,
                    state=(item.get("state") or "DC").upper()[:2],
                    contact_name=item.get("contact_name") or "",
                    services_interest=_service_from_keyword(keyword),
                    source=f"SAM.gov solicitation {solnum or item.get('title', '')}: {item.get('url', '')}".strip(),
                    external_id=external_id,
                    notes=f"{external_id} auto-added {item.get('posted', '')}".strip(),
                )
            )
    return candidates, errors


def merge_leads_csv(leads_csv: Path, candidates: list[LeadCandidate]) -> tuple[int, int, list[str]]:
    """Append new SAM.gov contacts to leads.csv. Returns (added, skipped, errors)."""
    header = [
        "business_name",
        "contact_name",
        "email",
        "phone",
        "state",
        "services_interest",
        "source",
        "consent_basis",
        "consent_date",
        "whatsapp_consent_date",
        "notes",
        "external_id",
    ]
    leads_csv.parent.mkdir(parents=True, exist_ok=True)

    rows_raw: list[dict] = []
    if leads_csv.exists():
        with leads_csv.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            file_header = reader.fieldnames or header
            for row in reader:
                rows_raw.append(row)
    else:
        file_header = header

    # Ensure external_id column exists in output schema.
    out_header = list(file_header)
    if "external_id" not in out_header:
        out_header.append("external_id")

    valid_leads, _ = load_leads_csv(leads_csv) if leads_csv.exists() else ([], [])
    known_solnums = _existing_solnums(valid_leads, rows_raw)
    known_emails = _existing_emails(valid_leads, rows_raw)

    added = 0
    skipped = 0
    errors: list[str] = []

    for cand in candidates:
        solnum = cand.external_id[4:] if cand.external_id.startswith("sam:") else ""
        if solnum and solnum in known_solnums:
            skipped += 1
            continue
        if cand.email in known_emails:
            skipped += 1
            continue
        lead = Lead(
            business_name=cand.business_name,
            contact_name=cand.contact_name,
            email=cand.email,
            state=cand.state if len(cand.state) == 2 else "DC",
            services_interest=cand.services_interest,
            source=cand.source,
            consent_basis="rfp_public_request",
            notes=cand.notes,
        )
        problems = lead.validate()
        if problems:
            errors.append(f"skipped {cand.email}: {'; '.join(problems)}")
            skipped += 1
            continue
        row = {col: "" for col in out_header}
        row.update({
            "business_name": cand.business_name,
            "contact_name": cand.contact_name,
            "email": cand.email,
            "state": lead.state,
            "services_interest": cand.services_interest,
            "source": cand.source,
            "consent_basis": "rfp_public_request",
            "notes": cand.notes,
            "external_id": cand.external_id,
        })
        rows_raw.append(row)
        known_emails.add(cand.email)
        if solnum:
            known_solnums.add(solnum)
        added += 1

    with leads_csv.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=out_header, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows_raw)

    return added, skipped, errors


def sync_leads_from_public_sources(
    leads_csv: Path,
    *,
    limit_per_query: int = 5,
) -> dict:
    candidates, discover_errors = discover_lead_candidates(limit_per_query=limit_per_query)
    added, skipped, merge_errors = merge_leads_csv(leads_csv, candidates)
    return {
        "candidates_found": len(candidates),
        "added": added,
        "skipped": skipped,
        "errors": discover_errors + merge_errors,
    }
