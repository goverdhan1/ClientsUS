from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from prospect_pipeline.models import load_leads_csv


class LeadSyncTests(unittest.TestCase):
    def test_merge_adds_sam_contact(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "leads.csv"
            csv_path.write_text(
                "business_name,contact_name,email,phone,state,services_interest,source,"
                "consent_basis,consent_date,whatsapp_consent_date,notes,external_id\n",
                encoding="utf-8",
            )
            from prospect_pipeline.lead_sync import LeadCandidate, merge_leads_csv

            added, skipped, errors = merge_leads_csv(
                csv_path,
                [
                    LeadCandidate(
                        business_name="US Dept of Example",
                        email="procurement@example.gov",
                        state="VA",
                        contact_name="Jane Doe",
                        services_interest="website development",
                        source="SAM.gov solicitation EX-1: https://sam.gov/notice/1",
                        external_id="sam:EX-1",
                        notes="sam:EX-1 auto-added",
                    )
                ],
            )
            self.assertEqual(added, 1)
            self.assertEqual(skipped, 0)
            self.assertEqual(errors, [])
            leads, _ = load_leads_csv(csv_path)
            self.assertEqual(leads[0].email, "procurement@example.gov")
            self.assertEqual(leads[0].consent_basis, "rfp_public_request")

    def test_merge_skips_duplicate_solnum(self):
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "leads.csv"
            csv_path.write_text(
                "business_name,contact_name,email,phone,state,services_interest,source,"
                "consent_basis,consent_date,whatsapp_consent_date,notes,external_id\n"
                "Agency,,first@example.gov,,VA,website,SAM.gov,rfp_public_request,,,sam:EX-1,sam:EX-1\n",
                encoding="utf-8",
            )
            from prospect_pipeline.lead_sync import LeadCandidate, merge_leads_csv

            added, skipped, _ = merge_leads_csv(
                csv_path,
                [
                    LeadCandidate(
                        business_name="Agency",
                        email="other@example.gov",
                        state="VA",
                        external_id="sam:EX-1",
                        source="SAM.gov",
                        notes="sam:EX-1 auto-added",
                    )
                ],
            )
            self.assertEqual(added, 0)
            self.assertEqual(skipped, 1)


if __name__ == "__main__":
    unittest.main()
