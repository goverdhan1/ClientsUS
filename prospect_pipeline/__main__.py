from __future__ import annotations

import argparse
import sys

from . import state as state_mod
from .config import Settings
from .consent import SuppressionList
from .emailer import build_message, send_all, write_dry_run
from .leads import select_batch
from .models import load_leads_csv
from .openweb import fetch_datagov, fetch_sam_gov


def _selected_messages(settings: Settings, limit: int | None):
    if not settings.leads_csv.exists():
        raise SystemExit(
            f"Leads file not found: {settings.leads_csv}\n"
            "Copy data/leads.template.csv to data/leads.csv and add consented leads."
        )
    leads, errors = load_leads_csv(settings.leads_csv)
    for err in errors:
        print(f"REFUSED row: {err}", file=sys.stderr)
    if errors:
        print(
            f"{len(errors)} row(s) refused (missing/invalid consent basis or data). "
            "Only valid rows are used.",
            file=sys.stderr,
        )
    suppression = SuppressionList(settings.suppression_path)
    batch, skipped = select_batch(
        leads,
        suppression,
        settings.sent_log_path,
        max_count=limit or settings.max_per_run,
        per_state_cap=settings.per_state_cap,
        cooldown_days=settings.cooldown_days,
    )
    template = settings.template_path.read_text(encoding="utf-8")
    messages = []
    for lead in batch:
        try:
            messages.append((lead, build_message(lead, settings, template)))
        except ValueError as exc:
            print(f"Skipping {lead.normalized_email}: {exc}", file=sys.stderr)
    return messages, skipped


def cmd_dry_run(args) -> int:
    settings = Settings.from_env()
    messages, skipped = _selected_messages(settings, args.limit)
    for _, msg in messages:
        path = write_dry_run(msg, settings.outbox_dir)
        print(f"drafted {msg['To']} -> {path}")
    print(f"\n{len(messages)} draft(s) written to {settings.outbox_dir}. Skipped: {skipped}")
    print("Nothing was sent. Review the drafts, then use 'send' when ready.")
    return 0


def cmd_send(args) -> int:
    settings = Settings.from_env()
    missing = settings.missing_for_send()
    if missing:
        for item in missing:
            print(f"Missing config: {item}", file=sys.stderr)
        print("Set these in .env (see .env.example) and retry.", file=sys.stderr)
        return 2
    messages, skipped = _selected_messages(settings, args.limit)
    if not messages:
        print("No eligible leads to email right now.")
        return 0
    print(f"About to send {len(messages)} email(s) from {settings.smtp_user}. Skipped: {skipped}")
    if not args.yes:
        reply = input("Type 'send' to confirm: ").strip().lower()
        if reply != "send":
            print("Aborted.")
            return 1
    sent = send_all(settings, [msg for _, msg in messages])
    sent_set = set(sent)
    for lead, msg in messages:
        if msg["To"] in sent_set:
            state_mod.record_send(settings.sent_log_path, lead, "sent")
    print(f"Sent {len(sent)} email(s). Logged to {settings.sent_log_path}.")
    return 0


def cmd_suppress(args) -> int:
    settings = Settings.from_env()
    suppression = SuppressionList(settings.suppression_path)
    for email in args.emails:
        suppression.add(email)
        print(f"suppressed {email.strip().lower()}")
    print("These addresses will never be emailed again by this tool.")
    return 0


def cmd_open_web(args) -> int:
    fetcher = fetch_sam_gov if args.source == "sam" else fetch_datagov
    try:
        results = fetcher(args.query, args.limit) if args.source == "sam" else fetcher(args.query, args.limit)
    except Exception as exc:  # network/key errors should not crash a cron run
        print(f"open-web lookup failed: {exc}", file=sys.stderr)
        return 1
    if not results:
        print("No public solicitations found for that query.")
        return 0
    print(f"{len(results)} public solicitation(s) for {args.query!r}:\n")
    for item in results:
        print(f"- {item['title']}\n  {item['organization']}\n  {item['url']}")
    print(
        "\nRespond through each posting's official instructions, or add the bid contact "
        "to data/leads.csv with consent_basis=rfp_public_request."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="prospect_pipeline",
        description="Consent-gated outreach for US web/software/mobile development prospects.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_dry = sub.add_parser("dry-run", help="Render emails to outbox/ without sending")
    p_dry.add_argument("--limit", type=int, default=None)
    p_dry.set_defaults(func=cmd_dry_run)

    p_send = sub.add_parser("send", help="Send emails via smtp.gmail.com (asks to confirm)")
    p_send.add_argument("--limit", type=int, default=None)
    p_send.add_argument("--yes", action="store_true", help="Skip the interactive confirmation")
    p_send.set_defaults(func=cmd_send)

    p_sup = sub.add_parser("suppress", help="Add addresses to the do-not-email list")
    p_sup.add_argument("emails", nargs="+")
    p_sup.set_defaults(func=cmd_suppress)

    p_web = sub.add_parser("open-web", help="List public RFPs for development services (read-only)")
    p_web.add_argument("--query", default="website development RFP")
    p_web.add_argument("--source", choices=["sam", "datagov"], default="sam")
    p_web.add_argument("--limit", type=int, default=10)
    p_web.set_defaults(func=cmd_open_web)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
