# ClientsUS — consent-first development-services outreach

Find US organizations actively looking for **website**, **software**, or **mobile (Android/iOS)**
development, then reach out by **email** (`smtp.gmail.com`) and/or **WhatsApp** (Twilio) — only
to contacts who have given proper consent.

## What this does (and does not do)

| Capability | Supported? | How |
|------------|------------|-----|
| Daily US prospect search at 9:00 AM Eastern | Yes | Windows Task Scheduler + `daily-search` |
| Public RFP / procurement listings | Yes | SAM.gov, Data.gov APIs |
| Federal dev job postings | Yes | USAJobs API |
| Email outreach via Gmail SMTP | Yes | `send` after `dry-run` |
| WhatsApp outreach | Yes | Twilio + `whatsapp-send` |
| **LinkedIn scraping / mass cold DM** | **No** | Violates LinkedIn ToS; use manual opt-in instead |

LinkedIn does not allow automated scraping or unsolicited bulk messaging. Legitimate alternatives:

- Respond to **public RFPs** found by `daily-search`
- Add leads who **opted in** on your website, at events, or via referral
- Use [LinkedIn Sales Navigator](https://business.linkedin.com/sales-solutions) manually and
  record only contacts who agreed to be reached

## Daily workflow

```
9:00 AM Eastern (Task Scheduler)
  └─> python -m prospect_pipeline daily-search
        └─> writes reports/daily_YYYY-MM-DD.txt

You review the report
  └─> add consented contacts to data/leads.csv

Preview outreach
  └─> python -m prospect_pipeline dry-run
  └─> python -m prospect_pipeline whatsapp-dry-run

Send (after review)
  └─> python -m prospect_pipeline send
  └─> python -m prospect_pipeline whatsapp-send
```

## Setup

### 1. Python + config

```bash
cp .env.example .env          # fill in Gmail, optional API keys, optional Twilio
cp data/leads.template.csv data/leads.csv
python -m unittest discover -s tests -v
python -m prospect_pipeline daily-search
python -m prospect_pipeline dry-run
```

No third-party Python packages; Python 3.10+ standard library only.

### 2. Windows Task Scheduler (9:00 AM Eastern)

On your Windows PC, from the repo folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\register_scheduled_task.ps1
```

This registers **ClientsUS-DailyProspectSearch** to run `scripts\run_daily_search.bat` every
day at 9:00 AM Eastern. Logs go to `logs\daily_search.log`.

Manual test:

```cmd
schtasks /Run /TN ClientsUS-DailyProspectSearch
```

### 3. API keys (free, for discovery)

| Key | Get it at | Used for |
|-----|-----------|----------|
| `SAM_GOV_API_KEY` | https://open.gsa.gov/api/get-opportunities-public-api/ | Government RFPs |
| `DATAGOV_API_KEY` | https://api.gsa.gov | Data.gov catalog |
| `USAJOBS_API_KEY` + `USAJOBS_USER_AGENT` | https://developer.usajobs.gov/ | Federal dev jobs |

If a key is missing, that source is skipped (others still run).

### 4. Gmail (email sending)

- Enable 2-Step Verification on your Google account
- Create an [App Password](https://support.google.com/accounts/answer/185833)
- Set `SMTP_USER` and `SMTP_APP_PASSWORD` in `.env`

### 5. Twilio (WhatsApp sending)

- Create a [Twilio account](https://www.twilio.com/)
- Enable WhatsApp (sandbox for testing, or register a business sender for production)
- Set `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` in `.env`
- Leads must have `phone` (E.164, e.g. `+14155551234`) and `whatsapp_consent_date`

## Leads file (`data/leads.csv`)

Only leads with a valid `consent_basis` are loaded:

- `explicit_opt_in` — person asked to be contacted (requires `consent_date`)
- `existing_customer` — existing business relationship (requires `consent_date`)
- `rfp_public_request` — public solicitation (respond per official instructions)

For WhatsApp, also set `whatsapp_consent_date` (when they opted in to text/WhatsApp contact).

**Read `docs/compliance.md` before sending anything.**

## Commands

| Command | Purpose |
|---------|---------|
| `daily-search` | Run all configured US searches; write dated report |
| `open-web` | One-off search (SAM.gov or Data.gov) |
| `dry-run` | Preview emails in `outbox/` |
| `send` | Send emails via Gmail SMTP |
| `whatsapp-dry-run` | Preview WhatsApp messages in `outbox/` |
| `whatsapp-send` | Send WhatsApp via Twilio |
| `suppress email@…` | Add address to do-not-email list |

## What I need from you

To go live, please provide:

1. **Gmail**: address + app password + your real postal address (CAN-SPAM)
2. **Your company pitch**: name, services, any portfolio link to include in templates
3. **API keys** (optional but recommended): SAM.gov, Data.gov, USAJobs
4. **Twilio** (optional): account SID, auth token, WhatsApp sender number
5. **Initial leads**: consented contacts in `data/leads.csv` (we never scrape emails/phones)
6. **Windows PC** where Task Scheduler will run (must have Python on PATH)

Once you share those, we can customize the email/WhatsApp templates and run a test batch.
