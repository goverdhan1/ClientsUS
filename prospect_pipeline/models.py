from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

# Leads without one of these bases are refused. Scraped, purchased, or
# guessed-address lists are not acceptable inputs.
ALLOWED_CONSENT_BASIS = {"explicit_opt_in", "existing_customer", "rfp_public_request"}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+[1-9]\d{9,14}$")


@dataclass
class Lead:
    business_name: str
    email: str
    state: str
    contact_name: str = ""
    phone: str = ""
    services_interest: str = ""
    source: str = ""
    consent_basis: str = ""
    consent_date: str = ""
    whatsapp_consent_date: str = ""
    notes: str = ""

    @property
    def normalized_email(self) -> str:
        return self.email.strip().lower()

    def validate(self) -> list[str]:
        problems = []
        if not self.business_name.strip():
            problems.append("missing business_name")
        has_email = bool(self.email.strip())
        has_phone = bool(self.phone.strip())
        if not has_email and not has_phone:
            problems.append("need at least one of email or phone")
        if has_email and not EMAIL_RE.match(self.email.strip()):
            problems.append(f"invalid email: {self.email!r}")
        if has_phone:
            phone = self.phone.strip()
            if not (phone.startswith("+") and PHONE_RE.match(phone)):
                problems.append(
                    f"phone must be E.164 (e.g. +14155551234), got {self.phone!r}"
                )
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

    def validate_for_whatsapp(self) -> list[str]:
        """Extra checks before WhatsApp outreach (TCPA / carrier rules)."""
        problems = self.validate()
        if not self.phone.strip():
            problems.append("phone is required for WhatsApp")
        if not self.whatsapp_consent_date.strip():
            problems.append(
                "whatsapp_consent_date (YYYY-MM-DD) is required — "
                "person must have opted in to text/WhatsApp contact"
            )
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
                phone=(row.get("phone") or "").strip(),
                state=(row.get("state") or "").strip().upper(),
                services_interest=(row.get("services_interest") or "").strip(),
                source=(row.get("source") or "").strip(),
                consent_basis=(row.get("consent_basis") or "").strip(),
                consent_date=(row.get("consent_date") or "").strip(),
                whatsapp_consent_date=(row.get("whatsapp_consent_date") or "").strip(),
                notes=(row.get("notes") or "").strip(),
            )
            problems = lead.validate()
            if problems:
                errors.append(f"line {line_no}: " + "; ".join(problems))
            else:
                leads.append(lead)
    return leads, errors
