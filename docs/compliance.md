# Outreach compliance guardrails

This project sends commercial email. The rules below are built into the code where
possible; the rest are on the operator.

## Lead sourcing (enforced in code)

Every lead in `data/leads.csv` must have a `consent_basis`:

- `explicit_opt_in` — the person asked to be contacted (contact form, trade-show
  signup, referral with permission). Requires `consent_date`.
- `existing_customer` — an existing business relationship. Requires `consent_date`
  (when the relationship started).
- `rfp_public_request` — a public solicitation (e.g. SAM.gov, state procurement
  portal). Respond through the posting's official instructions.

Rows without a valid basis are **refused** by the loader. Scraped directories,
purchased lists, and guessed addresses are never acceptable inputs.

## CAN-SPAM checklist (US commercial email)

- Accurate `From` and subject line — the template is honest about why you're writing.
- A valid physical postal address in every email — sending is **blocked** unless
  `SENDER_POSTAL_ADDRESS` is set, and rendering fails if the token is empty.
- A working opt-out — the template asks people to reply "unsubscribe". When someone
  does, run `python -m prospect_pipeline suppress their@email.com`. The suppression
  list is checked before every send. Honor requests promptly (legal max: 10 business
  days) and never sell or transfer opted-out addresses.
- Don't use misleading headers or routing information.

## Gmail-specific

- Use an **app password**, not your login password (2-Step Verification required):
  https://support.google.com/accounts/answer/185833
- Free Gmail accounts cap around 500 messages/day and will throttle bulk sending.
  Defaults here (`MAX_PER_RUN=50`) stay well under that. For real volume, use an
  email service provider (SendGrid, SES, etc.) with proper unsubscribe handling.
- Persistent `.env` values and secrets belong in environment variables / the Cursor
  Dashboard secrets store, never in git. `.env` and `data/leads.csv` are gitignored.

## Process

1. `python -m prospect_pipeline daily-search` — find public US opportunities (scheduled daily).
2. Review `reports/daily_*.txt` and add consented contacts to `data/leads.csv`.
3. `python -m prospect_pipeline dry-run` — review rendered email drafts in `outbox/`.
4. `python -m prospect_pipeline send` — sends after an interactive confirmation.
5. `python -m prospect_pipeline whatsapp-dry-run` / `whatsapp-send` — same flow for WhatsApp.
6. Record every send (automatic in `state/sent_log.csv` and `state/whatsapp_sent_log.csv`); a
   30-day cooldown per address/phone is enforced automatically.

## WhatsApp / SMS (TCPA)

- US law requires **prior express written consent** before marketing texts or WhatsApp messages.
- Every WhatsApp lead must have `whatsapp_consent_date` set (when they opted in).
- Include an opt-out path (template says "Reply STOP").
- Use Twilio's official WhatsApp API — not personal WhatsApp automation (against Meta ToS).
- For production volume, register a WhatsApp Business sender with Meta via Twilio.

## LinkedIn and social scraping

- Do **not** scrape LinkedIn profiles, export connection lists without consent, or send bulk
  unsolicited InMails through automation.
- LinkedIn's User Agreement prohibits scraping and unauthorized bots.
- Acceptable: manual networking, Sales Navigator with personal messages, inbound leads from your
  website, and public procurement postings (SAM.gov).
