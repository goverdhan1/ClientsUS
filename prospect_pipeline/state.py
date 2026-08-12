from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from .models import Lead

LOG_HEADER = ["email", "business_name", "state", "sent_on", "status", "detail"]


def _load_log(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def recently_contacted(path: Path, email: str, cooldown_days: int, today: date | None = None) -> bool:
    today = today or date.today()
    cutoff = today - timedelta(days=cooldown_days)
    email = email.strip().lower()
    for row in _load_log(path):
        if row.get("email", "").strip().lower() != email:
            continue
        try:
            sent_on = date.fromisoformat(row.get("sent_on", ""))
        except ValueError:
            continue
        if sent_on >= cutoff:
            return True
    return False


def record_send(path: Path, lead: Lead, status: str, detail: str = "", on: date | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if write_header:
            writer.writerow(LOG_HEADER)
        writer.writerow([
            lead.normalized_email,
            lead.business_name,
            lead.state,
            (on or date.today()).isoformat(),
            status,
            detail,
        ])
