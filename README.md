# GTM Lead Engine

Buyer-only B2B lead engine for Pakistan and the GCC. Discovers companies from free public
sources, scrapes their websites, decides **BUYER / VENDOR / UNKNOWN** with evidence, finds a
decision-maker, validates the email, scores 0–100 with a readable reason, and exports a clean
CSV. Vendors, agencies and software houses never reach the output. A human approves every
outreach email before it sends — nothing goes out unattended.

Python 3.12+, Supabase Postgres, free-tier APIs only. Runs locally, in GitHub Actions
(discovery + outreach), and as a FastAPI backend deployed on Vercel with a Next.js UI.

## Quick start

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[api,dev,overture]"
```

Set `GTM_DATABASE_URL` to a Supabase Postgres connection string (see [Database](#database)),
then run a campaign:

```bash
.venv/Scripts/python -m gtm_engine.cli run config/campaigns/example_retail_islamabad.yaml --max-companies 20
```

Outputs land in `data/exports/<campaign>_<timestamp>_<run>_qualified.csv` (buyers ≥ min_score)
and `..._all.csv` (everything, for audit).

Other commands:

```bash
.venv/Scripts/python -m gtm_engine.cli export retail-isb-001 --min-score 70
.venv/Scripts/python -m gtm_engine.cli suppress someone@company.pk --reason "asked to stop"
.venv/Scripts/python -m gtm_engine.cli runs
.venv/Scripts/python -m uvicorn gtm_engine.api.main:app --reload   # API on :8000
.venv/Scripts/python -m pytest
```

## Database

Storage is Supabase Postgres (`psycopg`, plain SQL, no ORM) — this replaced the original local
SQLite datastore so the same engine could run from GitHub Actions, Vercel and a laptop against
one shared source of truth. `GTM_DATABASE_URL` (a pooler connection string from your Supabase
project) is required everywhere the engine runs: CLI, API and both GitHub Actions workflows.
Schema is created idempotently on first connection per process (`CREATE TABLE IF NOT EXISTS …`
in `gtm_engine/storage/database.py`); tests get a disposable schema per run via
`?options=-csearch_path=...` so they never touch real data. Supabase's REST/service-role/anon
keys are **not** used — only the plain Postgres connection string.

## Web UI

```bash
.venv/Scripts/python -m uvicorn gtm_engine.api.main:app --reload   # API :8000
cd web && npm install && npm run dev                              # UI  :3000
```

Five pages: **Settings** (campaign YAML editor, mailboxes, suppressions, Sheets export), **Dashboard** (counts, score distribution, top buyers), **Campaigns** (run discovery
with live progress, download CSV), **Leads** (filter by type/score, open a lead to see every
reason and its activity, suppress), **Outreach** (the approval queue: each due email is rendered,
you edit subject/body, approve or reject, then send; plus sequence and activity views).

### Deployment

The API is deployed to Vercel as a Python function (`web/api/index.py`); `web/vercel.json`
copies `gtm_engine/` and `config/` into the function bundle and rewrites `/api/*` to it. That
deployed instance is treated as **read-only for outreach**: it can serve leads, drafts and
status, but real crawling and sending happen in GitHub Actions, which runs against a writable
checkout and commits results (CSVs, the send ledger) back to the repo. If the deployed API needs
to trigger a run, it dispatches the GitHub Actions workflow (`GTM_GITHUB_TOKEN` /
`GTM_GITHUB_REPO`) rather than running the crawl in-request. `GTM_CORS_ORIGINS` allowlists the
deployed frontend origin; `localhost:3000` is always allowed.

## Outreach

```bash
.venv/Scripts/python -m gtm_engine.cli outreach preview retail-isb-001          # see the 3 emails for top leads
.venv/Scripts/python -m gtm_engine.cli outreach send retail-isb-001 --dry-run   # writes .eml files to data/outbox/
.venv/Scripts/python -m gtm_engine.cli outreach send retail-isb-001             # real send (needs credentials)
.venv/Scripts/python -m gtm_engine.cli outreach status retail-isb-001
.venv/Scripts/python -m gtm_engine.cli suppress someone@company.pk
```

Credentials come only from the environment. Preferred: Gmail OAuth2 — run
`gtm outreach gmail-auth` once and store `GTM_GMAIL_CLIENT_ID` / `GTM_GMAIL_CLIENT_SECRET` /
`GTM_GMAIL_REFRESH_TOKEN` plus `GTM_SMTP_USER`. Fallback: `GTM_SMTP_PASSWORD` (App Password).
Several mailboxes: `GTM_MAILBOX_1_USER`/`_PASSWORD`, `GTM_MAILBOX_2_…` — Email 1 rotates to the
least-loaded mailbox, follow-ups stay on the mailbox that started the thread, each mailbox has
its own cap, warm-up and bounce guard. Without any credentials, every send is a dry run. Sender protection is on by default: warm-up ramp
(5/day growing by 2/day to the cap), 30–120 s random spacing, and a bounce-rate guard that
pauses the mailbox for the day. **Every email requires human approval** (`require_approval: true`): it is drafted, shown in the UI, edited if you like, and sent only after you approve it — follow-ups come back for their own approval. Sequence: Email 1 → +3 days Follow-up 1 →
+4 days Follow-up 2, threaded; stops on reply, bounce, "STOP", or suppression. Daily cap, 45 s
spacing and a 09:00–18:00 Asia/Karachi weekday window live in `config/outreach/settings.yaml`;
copy in `config/outreach/templates.yaml`. Every send is recorded in
`leads/<campaign>/outreach_ledger.json`, which CI commits, so an address never receives the same
step twice even if the runner's database is lost.

Replies are pulled over IMAP and classified (interested / not interested / wrong person /
out-of-office / auto-reply) by rules, with an optional LLM pass for ambiguous cases.

**Sends are manual-trigger only, deliberately not on a cron** — `outreach.yml` runs only via
`workflow_dispatch`, so nothing in the database gets emailed unattended; a human decides when a
batch goes out. `gather-leads.yml` (discovery/crawling) does run on a weekly schedule as well as
on demand, since it only writes leads, never contacts anyone.

## How a lead is produced

```
discover (Overture / OSM / KCCI / PPRA / seed CSV) → dedupe (domain, name+city)
→ find website (search fallback) → check the domain is still live
→ crawl ≤ N pages → classify BUYER/VENDOR/UNKNOWN → contacts + signals + quality
→ email syntax + MX → decision-maker email discovery + verification
→ score with reasons → store → CSV
```

Every stage is configuration-driven:

| File | Controls |
|------|----------|
| `config/campaigns/*.yaml` | offer, industries, cities, roles, buyer keywords, OSM/Overture categories, weights, thresholds |
| `config/defaults/vendor_rules.yaml` | global negative keywords and vendor self-description phrases |
| `config/defaults/roles.yaml` | buyer role whitelist, sell-side role blacklist, generic mailboxes |
| `config/defaults/signals.yaml` | buying/pain signal phrases and technology markers |
| `config/defaults/intent.yaml` | tender/RFQ/hiring intent phrases |
| `config/engine.yaml` | rate limits, timeouts, concurrency, robots, browser fallback, LLM provider (env `GTM_*` overrides) |
| `docs/API_KEYS.md` | every external credential the engine can use, what it unlocks, and whether it's currently set |

## Layout

```
gtm_engine/
  config/         schema + YAML loader
  discovery/      overture.py (Overture Maps via DuckDB), osm.py (Overpass + mirrors),
                  chambers.py (KCCI member directory),
                  geocode.py (Nominatim), csv_seed.py, search.py (website finder, Brave/DDG)
  scraping/       fetcher.py (polite HTTP, charset sniffing, size cap, host circuit breaker),
                  integrity.py (parked / soft-404 / placeholder / marketplace-redirect detection),
                  browser.py (optional Playwright
                  fallback for JS-only sites), site_crawler.py, parsers.py
  qualification/  buyer_classifier.py  ← the gate
  enrichment/     contacts.py, signals.py, email_patterns.py, external_signals.py (GDELT, RDAP), phones.py
  validation/     domains.py, emails.py, dedupe.py, verifier.py (Reacher/Hunter/MX-only), liveness.py
  scoring/        scoring.py
  export/         csv_export.py, sheets.py (Google Sheets mirror)
  storage/        database.py (Supabase Postgres via psycopg, plain SQL)
  outreach/       templates, sequencer (queue + state machine), sender (Gmail OAuth2/SMTP/dry-run),
                  reply_state (IMAP), reply_classifier.py, ledger (durable send log committed to leads/),
                  mailboxes.py (multi-mailbox rotation, warm-up, bounce guard)
  intent/         ppra.py (live Pakistan tenders), company_pages.py (RFQ / hiring intent)
  llm/            optional grounded LLM layer (Ollama / Groq / Gemini), off by default
  api/            FastAPI backend for the web UI, also deployed to Vercel
web/              Next.js 16 + shadcn UI, api/index.py + vercel.json for deployment (see web/README.md)
  pipeline.py     orchestration
  cli.py
config/           campaigns, defaults, engine, outreach settings
tests/            pytest suite with HTML/Overpass fixtures, disposable Postgres schema per run
docs/             REQUIREMENTS.md, DECISIONS.md, DIRECTION.md, API_KEYS.md
data/             exports + local cache (gitignored)
leads/            per-campaign CSVs and outreach ledger committed by CI
.github/workflows/
  gather-leads.yml   scheduled + manual discovery/crawl run, commits leads, per-campaign concurrency
  outreach.yml       manual-only send trigger (no cron, by design — see Outreach)
  verify-sent.yml    post-send verification
  ci.yml             tests
  pages.yml          GitHub Pages landing page
```

## Milestones

| | Status |
|---|---|
| M1 Foundation (config, storage, models, API skeleton) | done |
| M2 Discovery (Overture, OSM, KCCI, PPRA, seed CSV, website finder) | done |
| M3 Scraping (crawler, about/contact/team parsing, integrity checks) | done |
| M4 Buyer gate | done |
| M5 Enrichment (contacts, signals, quality) | done |
| M6 Validation (domains, MX, dedupe, suppression) | done |
| M7 Scoring with reasons | done |
| M8 Web UI (dashboard, campaigns, leads, outreach approval queue) | done — `web/` |
| M9 Outreach (Gmail SMTP/OAuth2, 3-step sequence, reply/bounce/STOP sync, ledger) | done |
| Phase A sender protection · Phase B contacts (verifier, phone type, provenance, decision-maker email discovery) · Phase C multi-mailbox rotation · Phase D signals & sources (KCCI directory, domain age, news, site quality, Brave) · Phase E reply intelligence · Phase F sharing & polish (Sheets, landing page, Settings UI) · Phase G intent scraping, optional LLM layer, reviewer accuracy | done |
| Migration: SQLite → Supabase Postgres; API deployed to Vercel | done |
| M10 Hardening (per-campaign concurrency, dead-run detection, domain liveness check, race-safe CSV commits) | in progress |

## Known gaps

- **Google Sheets mirror** is wired up but `GTM_SHEETS_CREDENTIALS_JSON` isn't supplied yet; the
  workflow step is non-fatal so a missing key doesn't fail a run.
- **Gemini** LLM fallback returns 404/503 on the free tier; Groq is the reliable path and is used
  by default when `enable_llm: true`.
- **Multi-mailbox rotation** is implemented and tested in isolation, but only one mailbox has
  live credentials in production so far.
- **Decision-maker email verification** depends on Hunter.io's free tier (100 verifications/mo)
  unless you self-host Reacher (`GTM_REACHER_URL`).

See `docs/API_KEYS.md` for the full credential registry and status, `docs/DECISIONS.md` for why
things are built the way they are, and `docs/DIRECTION.md` / `docs/REQUIREMENTS.md` for scope
and roadmap.
