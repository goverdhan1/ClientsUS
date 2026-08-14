from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .config import Settings
from .models import Lead

# E.164: + followed by 10–15 digits (US numbers typically +1XXXXXXXXXX).
PHONE_RE = re.compile(r"^\+[1-9]\d{9,14}$")


def normalize_phone(raw: str) -> str:
    """Normalize to E.164. Accepts 10-digit US numbers with optional +1."""
    digits = re.sub(r"\D", "", raw.strip())
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    candidate = raw.strip()
    if candidate.startswith("+") and PHONE_RE.match(candidate):
        return candidate
    raise ValueError(f"phone must be E.164 or 10-digit US number, got {raw!r}")


def render_whatsapp(template: str, tokens: dict[str, str]) -> str:
    missing = {k for k in ("contact_name", "business_name", "services_interest", "sender_name", "sender_company")
               if not str(tokens.get(k, "")).strip()}
    if missing:
        raise ValueError(f"whatsapp template tokens must not be empty: {sorted(missing)}")
    return template.format(**tokens)


def tokens_for_whatsapp(lead: Lead, settings: Settings) -> dict[str, str]:
    return {
        "contact_name": lead.contact_name or "there",
        "business_name": lead.business_name,
        "services_interest": lead.services_interest or "web, software, or mobile development",
        "sender_name": settings.sender_name,
        "sender_company": settings.sender_company or settings.sender_name,
    }


def build_whatsapp_body(lead: Lead, settings: Settings, template: str) -> str:
    return render_whatsapp(template, tokens_for_whatsapp(lead, settings))


def write_whatsapp_dry_run(lead: Lead, body: str, outbox_dir: Path) -> Path:
    outbox_dir.mkdir(parents=True, exist_ok=True)
    phone = normalize_phone(lead.phone)
    safe = phone.replace("+", "plus_")
    target = outbox_dir / f"whatsapp_{safe}.txt"
    target.write_text(f"To: {phone}\n\n{body}\n", encoding="utf-8")
    return target


def _twilio_post(settings: Settings, payload: dict[str, str]) -> dict:
    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{settings.twilio_account_sid}/Messages.json"
    )
    body = urllib.parse.urlencode(payload).encode("utf-8")
    token = base64.b64encode(
        f"{settings.twilio_account_sid}:{settings.twilio_auth_token}".encode()
    ).decode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Twilio HTTP {exc.code}: {detail}") from exc


def send_whatsapp_message(settings: Settings, to_phone: str, body: str) -> str:
    """Send one WhatsApp message via Twilio. Returns Twilio message SID."""
    to_e164 = normalize_phone(to_phone)
    from_num = settings.twilio_whatsapp_from.strip()
    if not from_num.startswith("+"):
        from_num = f"+{from_num}"
    result = _twilio_post(settings, {
        "From": f"whatsapp:{from_num}",
        "To": f"whatsapp:{to_e164}",
        "Body": body,
    })
    return result.get("sid", "")


def send_whatsapp_all(
    settings: Settings,
    items: list[tuple[Lead, str]],
    delay_seconds: float = 0.0,
) -> tuple[list[str], list[tuple[str, str]]]:
    sent: list[str] = []
    failures: list[tuple[str, str]] = []
    for index, (lead, body) in enumerate(items):
        phone = normalize_phone(lead.phone)
        try:
            send_whatsapp_message(settings, phone, body)
            sent.append(phone)
        except (RuntimeError, ValueError, OSError) as exc:
            failures.append((phone, str(exc)))
        if delay_seconds > 0 and index < len(items) - 1:
            time.sleep(delay_seconds)
    return sent, failures
