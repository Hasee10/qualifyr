# GTM Lead Engine

Buyer-only B2B lead engine for Pakistan and the GCC. Discovers companies from free public
sources, scrapes their websites, decides **BUYER / VENDOR / UNKNOWN** with evidence, finds a
decision-maker, validates the email, scores 0–100 with a readable reason, and exports a clean
CSV. Vendors, agencies and software houses never reach the output.

Phase 1 is local-first: Python 3.12+, SQLite, no paid APIs.

## Quick start

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[api,dev,overture]"
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

## Outreach

```bash
.venv/Scripts/python -m gtm_engine.cli outreach preview retail-isb-001          # see the 3 emails for top leads
.venv/Scripts/python -m gtm_engine.cli outreach send retail-isb-001 --dry-run   # writes .eml files to data/outbox/
.venv/Scripts/python -m gtm_engine.cli outreach send retail-isb-001             # real send (needs credentials)
.venv/Scripts/python -m gtm_engine.cli outreach status retail-isb-001
.venv/Scripts/python -m gtm_engine.cli suppress someone@company.pk
```

Credentials come only from the environment (`GTM_SMTP_USER`, `GTM_SMTP_PASSWORD` = Gmail address +
App Password). Without them every send is a dry run. Sequence: Email 1 → +3 days Follow-up 1 →
+4 days Follow-up 2, threaded; stops on reply, bounce, "STOP", or suppression. Daily cap, 45 s
spacing and a 09:00–18:00 Asia/Karachi weekday window live in `config/outreach/settings.yaml`;
copy in `config/outreach/templates.yaml`. Every send is recorded in
`leads/<campaign>/outreach_ledger.json`, which CI commits, so an address never receives the same
step twice even if the runner's database is lost.

GitHub Actions: `Outreach` runs weekdays at 10:00 PKT (secrets `GTM_SMTP_USER` / `GTM_SMTP_PASSWORD`).

## How a lead is produced

```
discover (OSM / seed CSV) → dedupe (domain, name+city) → find website (search fallback)
→ crawl ≤ N pages → classify BUYER/VENDOR/UNKNOWN → contacts + signals + quality
→ email syntax + MX → score with reasons → store → CSV
```

Every stage is configuration-driven:

| File | Controls |
|------|----------|
| `config/campaigns/*.yaml` | offer, industries, cities, roles, buyer keywords, OSM categories, weights, thresholds |
| `config/defaults/vendor_rules.yaml` | global negative keywords and vendor self-description phrases |
| `config/defaults/roles.yaml` | buyer role whitelist, sell-side role blacklist, generic mailboxes |
| `config/defaults/signals.yaml` | buying/pain signal phrases and technology markers |
| `config/engine.yaml` | rate limits, timeouts, concurrency, robots, DB path (env `GTM_*` overrides) |

## Layout

```
gtm_engine/
  config/         schema + YAML loader
  discovery/      overture.py (Overture Maps via DuckDB), osm.py (Overpass + mirrors),
                  geocode.py (Nominatim), csv_seed.py, search.py (website finder)
  scraping/       fetcher.py (polite HTTP), site_crawler.py, parsers.py
  qualification/  buyer_classifier.py  ← the gate
  enrichment/     contacts.py, signals.py
  validation/     domains.py, emails.py, dedupe.py
  scoring/        scoring.py
  export/         csv_export.py
  storage/        database.py (SQLite)
  outreach/       templates, sequencer (queue + state machine), sender (Gmail/dry-run),
                  reply_state (IMAP), ledger (durable send log committed to leads/)
  api/            FastAPI skeleton
  pipeline.py     orchestration
  cli.py
config/           campaigns, defaults, engine settings
tests/            pytest suite with HTML/Overpass fixtures
docs/             REQUIREMENTS.md, DECISIONS.md
data/             sqlite db + exports (gitignored)
```

## Milestones

| | Status |
|---|---|
| M1 Foundation (config, SQLite, models, API skeleton) | done |
| M2 Discovery (OSM + seed CSV + website finder) | done |
| M3 Scraping (crawler, about/contact/team parsing) | done |
| M4 Buyer gate | done |
| M5 Enrichment (contacts, signals, quality) | done |
| M6 Validation (domains, MX, dedupe, suppression) | done |
| M7 Scoring with reasons | done |
| M8 Export UI | CLI + API done; web UI pending template |
| M9 Outreach (Gmail SMTP, 3-step sequence, reply/bounce/STOP sync, ledger) | done |
| M10 Hardening | in progress |
