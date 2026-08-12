from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

# Leads without one of these bases are refused. Scraped, purchased, or
# guessed-address lists are not acceptable inputs.
ALLOWED_CONSENT_BASIS = {"explicit_opt_in", "existing_customer", "rfp_public_request"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Lead:
    business_name: str
    email: str
    state: str
    contact_name: str = ""
    services_interest: str = ""
    source: str = ""
    consent_basis: str = ""
    consent_date: str = ""
    notes: str = ""

    @property
    def normalized_email(self) -> str:
        return self.email.strip().lower()

    def validate(self) -> list[str]:
        problems = []
        if not self.business_name.strip():
            problems.append("missing business_name")
        if not EMAIL_RE.match(self.email.strip()):
            problems.append(f"invalid email: {self.email!r}")
        if len(self.state.strip()) != 2:
            problems.append(f"state must be a 2-letter code, got {self.state!r}")
        if self.consent_basis not in ALLOWED_CONSENT_BASIS:
            problems.append(
                f"consent_basis must be one of {sorted(ALLOWED_CONSENT_BASIS)}, "
                f"got {self.consent_basis!r}"
            )
        if self.consent_basis != "rfp_public_request" and not self.consent_date.strip():
            problems.append("consent_date (YYYY-MM-DD) is required for opt-in/customer leads")
        return problems


def load_leads_csv(path: Path) -> tuple[list[Lead], list[str]]:
    """Return (valid leads, per-line validation errors). Invalid rows are never returned."""
    leads: list[Lead] = []
    errors: list[str] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for line_no, row in enumerate(csv.DictReader(fh), start=2):
            lead = Lead(
                business_name=(row.get("business_name") or "").strip(),
                contact_name=(row.get("contact_name") or "").strip(),
                email=(row.get("email") or "").strip(),
                state=(row.get("state") or "").strip().upper(),
                services_interest=(row.get("services_interest") or "").strip(),
                source=(row.get("source") or "").strip(),
                consent_basis=(row.get("consent_basis") or "").strip(),
                consent_date=(row.get("consent_date") or "").strip(),
                notes=(row.get("notes") or "").strip(),
            )
            problems = lead.validate()
            if problems:
                errors.append(f"line {line_no}: " + "; ".join(problems))
            else:
                leads.append(lead)
    return leads, errors
