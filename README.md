# ClientsUS — consent-first development-services outreach

Find US organizations that are actively looking for website, software, or mobile
development, and email them from Gmail (`smtp.gmail.com`) — without scraping
personal data or sending spam.

## How it works

1. **Source demand (open web, read-only)**
   `python -m prospect_pipeline open-web --query "website development"` lists public
   solicitations (SAM.gov via free `SAM_GOV_API_KEY`, or Data.gov via free
   `DATAGOV_API_KEY`).
   These are organizations publicly asking for proposals — respond through each
   posting's official channel, or add the bid contact to your leads file with
   `consent_basis=rfp_public_request`.

2. **Maintain a consented leads file**
   Copy `data/leads.template.csv` to `data/leads.csv` (gitignored). Only leads with
   `explicit_opt_in`, `existing_customer`, or `rfp_public_request` are ever loaded;
   anything else is refused. Real prospect data stays out of git.

3. **Preview, then send**
   `python -m prospect_pipeline dry-run` renders drafts into `outbox/` without
   sending. `python -m prospect_pipeline send` sends via `smtp.gmail.com` after a
   confirmation, enforces per-state caps, a 30-day per-address cooldown, and the
   suppression list (`python -m prospect_pipeline suppress a@b.com`).

## Setup

```bash
cp .env.example .env   # fill in Gmail app password + sender identity
python -m unittest discover -s tests -v
python -m prospect_pipeline dry-run
```

No third-party dependencies; Python 3.10+ standard library only.

**Read `docs/compliance.md` before sending anything.** The pipeline will refuse to
send without a real sender postal address (CAN-SPAM) and will never email scraped,
purchased, or unsubscribed addresses.
