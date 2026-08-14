"""Read-only discovery of PUBLIC solicitations (RFPs) for development services.

These are organizations actively asking for proposals — the cleanest possible
"looking for development services" signal. This module never scrapes personal
contact data; it lists public postings and links to follow per each posting's
own response instructions.
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import date, timedelta

USER_AGENT = "prospect-pipeline/0.1 (+consent-first outreach tooling)"

# Service types to search each daily run (keyword, source).
DEFAULT_SERVICE_QUERIES: list[tuple[str, str]] = [
    ("website development", "sam"),
    ("software development", "sam"),
    ("mobile app development", "sam"),
    ("Android iOS application development", "sam"),
    ("website development RFP", "datagov"),
    ("software development contractor", "usajobs"),
    ("mobile application developer", "usajobs"),
]


def _get_json(url: str, headers: dict[str, str] | None = None) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_sam_gov(keyword: str = "website development", limit: int = 10) -> list[dict]:
    """Search SAM.gov contract opportunities. Needs a free key from https://sam.gov."""
    api_key = os.environ.get("SAM_GOV_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "SAM_GOV_API_KEY is not set. Request a free key at "
            "https://open.gsa.gov/api/get-opportunities-public-api/ and add it to .env."
        )
    today = date.today()
    params = urllib.parse.urlencode({
        "api_key": api_key,
        "keywords": keyword,
        "limit": limit,
        "postedFrom": (today - timedelta(days=30)).strftime("%m/%d/%Y"),
        "postedTo": today.strftime("%m/%d/%Y"),
    })
    data = _get_json(f"https://api.sam.gov/opportunities/v2/search?{params}")
    results = []
    for item in data.get("opportunitiesData", []):
        poc_email = ""
        poc_name = ""
        for poc in item.get("pointOfContact") or []:
            if isinstance(poc, dict) and poc.get("email"):
                poc_email = poc["email"].strip()
                poc_name = (poc.get("fullName") or poc.get("fullname") or "").strip()
                break
        state = "DC"
        pop = item.get("placeOfPerformance") or {}
        if isinstance(pop, dict):
            st = pop.get("state") or {}
            if isinstance(st, dict) and st.get("code"):
                state = str(st["code"]).upper()[:2]
        office = item.get("officeAddress") or {}
        if state == "DC" and isinstance(office, dict) and office.get("state"):
            state = str(office["state"]).upper()[:2]
        results.append({
            "title": item.get("title", ""),
            "organization": item.get("fullParentPathName", "")
            or item.get("department", "")
            or item.get("office", ""),
            "url": item.get("uiLink", ""),
            "posted": item.get("postedDate", ""),
            "email": poc_email,
            "contact_name": poc_name,
            "state": state,
            "solicitation_number": item.get("solicitationNumber", ""),
        })
    return results


def fetch_datagov(query: str = "website development RFP", limit: int = 10) -> list[dict]:
    """Search the Data.gov catalog. Needs a free key from https://api.gsa.gov
    (DATAGOV_API_KEY in .env). The old key-free CKAN API was retired in 2025."""
    api_key = os.environ.get("DATAGOV_API_KEY", "")
    if not api_key:
        raise RuntimeError(
            "DATAGOV_API_KEY is not set. Get a free key at https://api.gsa.gov "
            "and add it to .env (or use --source sam with SAM_GOV_API_KEY)."
        )
    params = urllib.parse.urlencode({"q": query, "per_page": limit})
    data = _get_json(
        f"https://api.gsa.gov/technology/datagov/v4/search?{params}",
        headers={"X-Api-Key": api_key},
    )
    return [
        {
            "title": item.get("title", ""),
            "organization": item.get("organization", "")
            if isinstance(item.get("organization"), str)
            else (item.get("organization") or {}).get("name", ""),
            "url": item.get("landing_page", "") or item.get("url", ""),
            "posted": item.get("modified", ""),
        }
        for item in data.get("results", [])
    ]


def fetch_usajobs(keyword: str = "software developer", limit: int = 10) -> list[dict]:
    """Search USAJobs for federal IT / development openings.

    Free API key: https://developer.usajobs.gov/
    Set USAJOBS_API_KEY and USAJOBS_USER_AGENT (your registration email) in .env.
    """
    api_key = os.environ.get("USAJOBS_API_KEY", "")
    user_agent = os.environ.get("USAJOBS_USER_AGENT", "")
    if not api_key or not user_agent:
        raise RuntimeError(
            "USAJOBS_API_KEY and USAJOBS_USER_AGENT are not set. Register at "
            "https://developer.usajobs.gov/ and add both to .env."
        )
    params = urllib.parse.urlencode({
        "Keyword": keyword,
        "ResultsPerPage": min(limit, 25),
        "Page": 1,
    })
    data = _get_json(
        f"https://data.usajobs.gov/api/search?{params}",
        headers={
            "Host": "data.usajobs.gov",
            "User-Agent": user_agent,
            "Authorization-Key": api_key,
        },
    )
    items = data.get("SearchResult", {}).get("SearchResultItems", [])
    results = []
    for wrapped in items[:limit]:
        item = wrapped.get("MatchedObjectDescriptor", {})
        locs = item.get("PositionLocation", []) or []
        location = ", ".join(
            loc.get("LocationName", "") for loc in locs if loc.get("LocationName")
        )
        org = item.get("OrganizationName", "")
        results.append({
            "title": item.get("PositionTitle", ""),
            "organization": org,
            "url": item.get("PositionURI", "") or item.get("ApplyURI", ""),
            "posted": item.get("PublicationStartDate", ""),
            "location": location,
        })
    return results
