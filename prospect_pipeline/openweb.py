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
    return [
        {
            "title": item.get("title", ""),
            "organization": item.get("department", "") or item.get("office", ""),
            "url": item.get("uiLink", ""),
            "posted": item.get("postedDate", ""),
        }
        for item in data.get("opportunitiesData", [])
    ]


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
