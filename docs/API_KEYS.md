# API keys & credentials registry

Single source of truth for every external credential the engine can use. All are free
tiers. Values live only in GitHub Actions secrets (or your local environment) — never in
the repo. **Status** is updated as keys are added.

| Env var | Service | Used for | Free tier | Required? | Status |
|---|---|---|---|---|---|
| `GTM_SMTP_USER` | Gmail | Mailbox #1 address (sending + IMAP reply sync) | free account | yes (or `GTM_MAILBOX_1_USER`) | ✅ set |
| `GTM_SMTP_PASSWORD` | Gmail App Password | Mailbox #1 auth (fallback to OAuth2) | free | one of password / OAuth | ✅ set |
| `GTM_GMAIL_CLIENT_ID` / `GTM_GMAIL_CLIENT_SECRET` / `GTM_GMAIL_REFRESH_TOKEN` | Google Cloud OAuth client | Mailbox #1 OAuth2 (XOAUTH2), replaces the App Password | free | optional (preferred) | ⏳ not set — run `gtm outreach gmail-auth` |
| `GTM_MAILBOX_2_USER` / `GTM_MAILBOX_2_PASSWORD` | Gmail | Mailbox #2 for rotation | free | optional | ⚠️ reported added, **not visible on the repo** as of 2026-09-21 — please re-check |
| `GTM_MAILBOX_N_USER` / `_PASSWORD` / `_CLIENT_ID` / `_CLIENT_SECRET` / `_REFRESH_TOKEN` / `_LIMIT` / `_NAME` | Gmail | Further mailboxes (slots 3–10) | free | optional | — |
| `GTM_REACHER_URL` | Self-hosted Reacher (`check-if-email-exists`) | Mailbox-level email verification → `deliverable` status; unlocks decision-maker email confirmation | free software; needs a host with outbound port 25 | optional | ⏳ not set |
| `GTM_HUNTER_API_KEY` | Hunter.io | Email verification fallback (50 verifications/month), spent only on decision-maker candidates | free 50/mo | optional | ⏳ not set |
| `GTM_BRAVE_API_KEY` | Brave Search API | Website finder (replaces DuckDuckGo HTML scraping) | 2,000 queries/mo | optional | ⏳ supported, not set |
| `GTM_GOOGLE_CSE_KEY` / `GTM_GOOGLE_CSE_ID` | Google Custom Search JSON | Website finder fallback | 100 queries/day | optional | ⏳ planned (Phase D) |
| `GTM_GROQ_API_KEY` or `GTM_GEMINI_API_KEY` | Groq / Google Gemini | Hosted LLM fallback for Phase G (Ollama locally needs no key) | free, rate-limited | optional | ⏳ planned (Phase G) |
| `GTM_SHEETS_CREDENTIALS_JSON` | Google Sheets API (service account) | One-way export of qualified leads | free | optional | ⏳ planned (Phase F) |

## Keyless services in use

Overture Maps (S3 parquet), OpenStreetMap Overpass + mirrors, Nominatim, GDELT news (rate-limited),
RDAP domain age (not for .pk), KCCI member directory (scraped, cached weekly), Google Fonts (UI).

## Where they are read

- Mailboxes: `gtm_engine/outreach/mailboxes.py` (`load_mailboxes`)
- Gmail OAuth: `gtm_engine/outreach/gmail_oauth.py`
- Verifiers: `gtm_engine/validation/verifier.py` (`build_verifier`)
- Workflows pass them through: `.github/workflows/outreach.yml`, `verify-sent.yml`

## Adding a key

1. GitHub → Settings → Secrets and variables → Actions → *New repository secret*.
2. Add the same name to the `env:` block of the relevant workflow if it is new.
3. Update the **Status** column here.
