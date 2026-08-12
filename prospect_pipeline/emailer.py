from __future__ import annotations

import smtplib
import string
from email.message import EmailMessage
from pathlib import Path

from .config import Settings
from .models import Lead


def required_tokens(template: str) -> set[str]:
    return {
        field.split(".")[0].split("[")[0]
        for _, field, _, _ in string.Formatter().parse(template)
        if field
    }


def render(template: str, tokens: dict[str, str]) -> str:
    needed = required_tokens(template)
    missing = needed - tokens.keys()
    if missing:
        raise ValueError(f"template tokens not provided: {sorted(missing)}")
    empty = [key for key in needed if not str(tokens[key]).strip()]
    if empty:
        # An empty sender_postal_address would produce a CAN-SPAM-violating email.
        raise ValueError(f"template tokens must not be empty: {sorted(empty)}")
    return template.format(**tokens)


def tokens_for(lead: Lead, settings: Settings) -> dict[str, str]:
    return {
        "contact_name": lead.contact_name or "there",
        "business_name": lead.business_name,
        "services_interest": lead.services_interest or "web, software, or mobile development",
        "source_phrase": lead.source or "your inquiry",
        "sender_name": settings.sender_name,
        "sender_company": settings.sender_company or settings.sender_name,
        "sender_postal_address": settings.sender_postal_address,
    }


def build_message(lead: Lead, settings: Settings, template: str) -> EmailMessage:
    body = render(template, tokens_for(lead, settings))
    subject_line, _, rest = body.partition("\n")
    subject = subject_line.removeprefix("Subject:").strip()
    msg = EmailMessage()
    msg["From"] = (
        f"{settings.sender_name} <{settings.smtp_user}>"
        if settings.sender_name
        else settings.smtp_user
    )
    msg["To"] = lead.normalized_email
    msg["Subject"] = subject
    msg.set_content(rest.strip() + "\n")
    return msg


def write_dry_run(msg: EmailMessage, outbox_dir: Path) -> Path:
    outbox_dir.mkdir(parents=True, exist_ok=True)
    target = outbox_dir / f"{msg['To'].replace('@', '_at_')}.txt"
    target.write_text(msg.as_string(), encoding="utf-8")
    return target


def send_all(settings: Settings, messages: list[EmailMessage]) -> list[str]:
    """Send via Gmail SMTP (STARTTLS). Returns the addresses that were sent."""
    sent = []
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as smtp:
        smtp.ehlo()
        smtp.starttls()
        smtp.login(settings.smtp_user, settings.smtp_app_password)
        for msg in messages:
            smtp.send_message(msg)
            sent.append(msg["To"])
    return sent
