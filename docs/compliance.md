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

1. `python -m prospect_pipeline dry-run` — review rendered drafts in `outbox/`.
2. `python -m prospect_pipeline send` — sends after an interactive confirmation.
3. Record every send (automatic in `state/sent_log.csv`); a 30-day cooldown per
   address is enforced automatically.
