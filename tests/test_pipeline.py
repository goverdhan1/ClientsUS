from __future__ import annotations

import smtplib
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from prospect_pipeline.config import Settings
from prospect_pipeline.consent import SuppressionList
from prospect_pipeline.emailer import build_message, render, send_all, write_dry_run
from prospect_pipeline.leads import select_batch
from prospect_pipeline.models import Lead, load_leads_csv
from prospect_pipeline.state import recently_contacted, record_send

TEMPLATE = (
    "Subject: {services_interest} for {business_name}\n\n"
    "Hi {contact_name},\nfrom {sender_name} at {sender_company},\n{sender_postal_address}\n"
    "Re: {source_phrase}\n"
)


def make_settings(root: Path) -> Settings:
    return Settings(
        smtp_host="smtp.gmail.com",
        smtp_port=587,
        smtp_user="sender@example.com",
        smtp_app_password="x" * 16,
        sender_name="Sender",
        sender_company="Sender Co",
        sender_postal_address="1 Main St, Austin, TX 78701",
        max_per_run=50,
        per_state_cap=1,
        cooldown_days=30,
        send_delay_seconds=0,
        leads_csv=root / "leads.csv",
        template_path=root / "template.txt",
        state_dir=root / "state",
        outbox_dir=root / "outbox",
    )


def make_lead(email: str, state: str = "TX", basis: str = "explicit_opt_in") -> Lead:
    return Lead(
        business_name="Biz",
        email=email,
        state=state,
        services_interest="website development",
        source="website inquiry",
        consent_basis=basis,
        consent_date="2026-08-01" if basis != "rfp_public_request" else "",
    )


class LeadValidationTests(unittest.TestCase):
    def test_scraped_basis_is_refused(self):
        lead = make_lead("a@b.com", basis="scraped_directory")
        self.assertTrue(any("consent_basis" in p for p in lead.validate()))

    def test_opt_in_without_date_is_refused(self):
        lead = make_lead("a@b.com")
        lead.consent_date = ""
        self.assertTrue(any("consent_date" in p for p in lead.validate()))

    def test_valid_rows_load_and_invalid_rows_are_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "leads.csv"
            csv_path.write_text(
                "business_name,contact_name,email,state,services_interest,source,consent_basis,consent_date,notes\n"
                "Good Co,,good@example.com,TX,website,referral,explicit_opt_in,2026-08-01,\n"
                "Bad Co,,bad@example.com,TX,website,scraped,scraped_directory,,\n"
                "Broken,,not-an-email,Texas,website,referral,explicit_opt_in,2026-08-01,\n",
                encoding="utf-8",
            )
            leads, errors = load_leads_csv(csv_path)
        self.assertEqual([l.email for l in leads], ["good@example.com"])
        self.assertEqual(len(errors), 2)


class SelectionTests(unittest.TestCase):
    def test_dedupe_suppression_cooldown_and_caps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            log = root / "sent_log.csv"
            record_send(log, make_lead("recent@example.com"), "sent",
                        on=date.today() - timedelta(days=5))
            suppression = SuppressionList(root / "suppression.txt")
            suppression.add("opted-out@example.com")

            leads = [
                make_lead("one@tx.com", "TX"),
                make_lead("one@tx.com", "TX"),              # duplicate
                make_lead("opted-out@example.com", "NY"),   # suppressed
                make_lead("recent@example.com", "CA"),      # cooldown
                make_lead("two@tx.com", "TX"),              # over per-state cap (cap=1)
                make_lead("three@ny.com", "NY"),
                make_lead("four@ca.com", "CA"),
                make_lead("five@az.com", "AZ"),             # over max (max=3)
            ]
            batch, skipped = select_batch(
                leads, suppression, log,
                max_count=3, per_state_cap=1, cooldown_days=30,
            )
        self.assertEqual(
            [l.email for l in batch],
            ["one@tx.com", "three@ny.com", "four@ca.com"],
        )
        self.assertEqual(skipped["duplicate"], 1)
        self.assertEqual(skipped["suppressed"], 1)
        self.assertEqual(skipped["cooldown"], 1)
        self.assertEqual(skipped["state_cap"], 1)
        self.assertEqual(skipped["over_max"], 1)

    def test_recently_contacted_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log.csv"
            lead = make_lead("x@example.com")
            record_send(log, lead, "sent", on=date.today() - timedelta(days=10))
            self.assertTrue(recently_contacted(log, "x@example.com", 30))
            self.assertFalse(recently_contacted(log, "x@example.com", 5))
            self.assertFalse(recently_contacted(log, "other@example.com", 30))

    def test_failed_send_does_not_trigger_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "log.csv"
            record_send(log, make_lead("y@example.com"), "failed", detail="550 rejected")
            self.assertFalse(recently_contacted(log, "y@example.com", 30))


class RenderTests(unittest.TestCase):
    def tokens(self):
        return {
            "contact_name": "Sam",
            "business_name": "Acme",
            "services_interest": "mobile app",
            "source_phrase": "your inquiry",
            "sender_name": "Dev",
            "sender_company": "Dev Co",
            "sender_postal_address": "1 Main St",
        }

    def test_render_ok(self):
        out = render(TEMPLATE, self.tokens())
        self.assertIn("Subject: mobile app for Acme", out)
        self.assertIn("1 Main St", out)

    def test_missing_token_raises(self):
        tokens = self.tokens()
        del tokens["sender_postal_address"]
        with self.assertRaises(ValueError):
            render(TEMPLATE, tokens)

    def test_empty_token_raises(self):
        tokens = self.tokens()
        tokens["sender_postal_address"] = "  "
        with self.assertRaises(ValueError):
            render(TEMPLATE, tokens)


class MessageTests(unittest.TestCase):
    def test_build_and_dry_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp))
            msg = build_message(make_lead("Lead@Example.com"), settings, TEMPLATE)
            self.assertEqual(msg["To"], "lead@example.com")
            self.assertEqual(msg["Subject"], "website development for Biz")
            self.assertIn("Sender <sender@example.com>", msg["From"])
            self.assertIsNotNone(msg["Date"])
            self.assertEqual(
                msg["List-Unsubscribe"],
                "<mailto:sender@example.com?subject=unsubscribe>",
            )
            self.assertIn("1 Main St, Austin, TX 78701", msg.get_content())
            out = write_dry_run(msg, settings.outbox_dir)
            self.assertTrue(out.exists())
            self.assertIn("Subject:", out.read_text(encoding="utf-8"))

    def test_missing_for_send_flags_address(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp))
            settings.sender_postal_address = ""
            self.assertTrue(any("SENDER_POSTAL_ADDRESS" in m for m in settings.missing_for_send()))


class SendAllTests(unittest.TestCase):
    def test_rejected_recipient_does_not_abort_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            settings = make_settings(Path(tmp))
            messages = [
                build_message(make_lead(f"u{i}@example.com"), settings, TEMPLATE)
                for i in range(3)
            ]
            with mock.patch("smtplib.SMTP") as smtp_cls:
                smtp = smtp_cls.return_value.__enter__.return_value
                smtp.send_message.side_effect = [
                    None,
                    smtplib.SMTPRecipientsRefused({"u1@example.com": (550, b"no such user")}),
                    None,
                ]
                sent, failures = send_all(settings, messages, delay_seconds=0)
        self.assertEqual(sent, ["u0@example.com", "u2@example.com"])
        self.assertEqual([recipient for recipient, _ in failures], ["u1@example.com"])


if __name__ == "__main__":
    unittest.main()
