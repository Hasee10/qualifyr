# MEMORY — working tracker

Live state of the project: what is built, what is next, the architecture to implement
against, and facts we verified so nobody re-researches them. Read this top-to-bottom before
starting engine work.

- **`PLAN.md`** (repo root) — the product direction of record (2026-09-25 reframe). Overrides
  anything here on *direction*.
- **`docs/DIRECTION.md`** — CEO direction; **`docs/ROADMAP.txt`** — historical phases A–G.
- This file — the live "what's done / what's next / how it works / what we verified".

Last updated: 2026-10-03 (NL frontend, campaigns UI cleanup, mailbox management, CSV fix)

---

## 1. WHAT QUALIFYR IS (the reframe, now built)

An **offer-agnostic market-research search engine**, not a lead-gen / cold-email tool. You
describe what you sell → the engine derives what to search for → finds real companies from
free public sources → judges each by *need* → returns a small set of strictly-relevant
results, each with a research brief and a matched decision-maker. Campaigns and outreach are
secondary. Quality over quantity is absolute (3–5 great results = success).

Two intended jobs: (1) **market search** — "where can we sell this?"; (2) **competitor
analysis** — "what are my competitors doing?" (job 2 is **not built yet** — see E3).

The old "we sell websites" Phase-H pivot is now just **one possible offer** a user can type,
not the product.

---

## 2. WHAT IS BUILT (all ✅, pushed, CI green)

**Reframe priorities P1–P5:**
- **P1 Dynamic campaigns** — user-created, **DB-backed** (not files): create/list/delete/
  run-by-id, a New-campaign form, runs accumulate. `config.loader.resolve_campaign()` loads a
  campaign by id (DB) OR path (file); CLI `campaign-id` prints the resolved id for workflows.
- **P2 Hard filters + LLM keywords** — `llm/tasks.generate_keywords(offer)` +
  `qualification/relevance.relevant_terms`. Pipeline drops hiring/RFQ signals not relevant to
  the offer's **need-terms (not sector)** — the "Imtiaz was hiring, but not for us" fix.
  Generated keywords also feed PPRA discovery + the classifier; shown as chips; offer-relevant
  intent scores +3; `stats.intent_dropped_irrelevant` surfaced.
- **P3 Region filter** — `GeographyConfig.provinces` + `search_areas()`; OSM/Overture iterate
  areas and try each country as a geocode hint (one campaign can span countries). ⚠️ tension
  with the "Pakistan only" CEO directive — **needs sign-off** before real multi-country use.
- **P4 Result caps** — `max_companies` is the per-run cap ("API cap" in the form); plus
  `website_finder_max_per_run` bounds Brave.
- **P5 Research depth** — `enrichment/research.build_research_brief` (grounded per-company
  summary → `Lead.research_brief`, top of lead detail; includes a web-presence verdict for the
  thin/single-page case); decision-maker's own LinkedIn `/in/` profile extracted + matched by
  name (`parsers.personal_profiles`, `contacts._match_personal_profile`, needs BOTH names —
  never a stranger's).

**Intent-based matching (CEO: "leads strictly by intent, not keywords"), 4 slices done:**
- `llm/tasks.judge_intent(offer, evidence)` → grounded `{buyer, confidence, reason}`; None
  without an LLM. Wired via `pipeline.apply_intent_verdict` (threshold 0.6): a confident
  non-buyer demotes a keyword-only BUYER→UNKNOWN, a confident buyer promotes UNKNOWN→BUYER,
  VENDOR is never promoted. `scoring.score_lead` rewards evident need (×confidence). Stored on
  the lead (`intent_fit/intent_confidence/intent_reason`), shown as a badge + reason in the UI.
  `judge_intent` runs **once per non-vendor company** when the LLM is on (bounded by the cap).
- **The LLM layer is ENABLED**: `config/engine.yaml` → `enable_llm: true`, `llm_provider: groq`.

**Multi-tenancy** — campaigns carry `owner_id` (migrated via `ALTER TABLE ... ADD COLUMN IF
NOT EXISTS`), set on create from the Supabase token's `sub` (`auth.current_user_id`), preserved
on re-upsert via `COALESCE`. Every `/campaigns/{id}/…` route guarded by `require_campaign_access`,
every `/leads/{id}/…` by `require_lead_access` (both as decorator `dependencies=[…]`). A campaign
the caller may not see is **404, not 403** (existence not leaked). File-based example campaigns
and legacy NULL-owner rows stay **shared**. **No scoping when auth is off/bypassed** (local
operator, tests) — `current_user_id` is None. Suppressions + mailboxes are global operator infra.

**Golden set** — `gtm_engine/eval/golden.py` + `tests/golden/golden_leads.jsonl` (18 rows) +
`scripts/golden_eval.py`. `tests/test_golden_set.py` enforces accuracy floor 0.8 (baseline
100%) + hard invariants: an agency is never a buyer, a real retailer is never rejected. **The
seed is small — grow it to 50+, esp. intent-judge cases, to trust the number.**

**Phase 5 — Business profile enrichment** ✅ **DONE (2026-10-02):**
- Track A: OSM `opening_hours` extraction + structured parser (`enrichment/hours.py`)
- Track B: Google Places API (`enrichment/places.py`) — Text Search (unlimited free) + Place
  Details Enterprise for rating, review count, hours. Budget: 20/run, auto-enables when
  `GTM_GOOGLE_PLACES_API_KEY` is set. Key stored in GitHub Secrets only, never logged.
- Online presence audit: `enrichment/online_presence.py` — detects ecommerce, WhatsApp, social,
  delivery platforms, mobile app. `OnlinePresence` model with `online_gap_score` (inverse
  digital maturity). Gap labels: `no_website`, `no_app`, `no_whatsapp`, etc.

**Phase 6 — Decomposed scoring + pain mining** ✅ **DONE (2026-10-03):**
- Scoring reworked: `review_band(0-30) + rating(0-10) + proximity_tier(0-15) + online_gap(0-25)
  + pain_evidence(0-20) = max 100`. Replaces old 6-dimension ICP scoring.
- Proximity/tier: haversine from configurable anchor (`anchor_lat`/`anchor_lon`), Tier 1/2/3.
- Review text pain mining: keyword patterns + optional LLM refinement on Google review text.
- Config: `enable_review_text`, `anchor_lat`, `anchor_lon`, `proximity_tier1_km/2_km`.

**NL campaign interface** ✅ **DONE (2026-10-03):**
- `gtm_engine/campaign/nl_parser.py` — accepts text like "find grocery stores in Islamabad that
  need inventory software", auto-builds CampaignConfig. Two-stage: deterministic regex always
  runs, optional LLM fills gaps (never overwrites). `POST /campaigns/nl` + `gtm nl` CLI.
- Frontend: old 10-field form replaced with NL text input (always editable, stays visible after
  creation). Editable `max_companies` field (default 30). "Run now" button in result panel
  triggers discovery immediately. `POST /campaigns/nl` accepts optional `max_companies` override.

**Frontend cleanup** ✅ **DONE (2026-10-03):**
- Campaigns page: compact cards (redundant offer line hidden when it matches name, sectors/keywords
  badges removed, stats in single row, smaller Run/CSV buttons, last-run shows date only).
- CSV export: authenticated fetch with bearer token (was broken — plain `<a href>` couldn't send auth).
- Self-serve mailbox management: Settings → Mailboxes tab (add SMTP credentials, test connection,
  enable/disable, delete). `user_mailboxes` table + 5 new API endpoints.
- React crash fix: NL explanation dict rendered as text node → guarded with type checks.

**Phase 7 — Open-source readiness** ✅ **DONE (2026-10-03):**
- Per-user API key management: `user_api_keys` table, Fernet-encrypted at rest (`GTM_ENCRYPTION_KEY`),
  resolution priority: user DB key → operator env var. `api/keys.py` + `api/usage.py`.
- Daily usage limits: `usage_counts` table, per-user caps (brave: 50, groq: 200, hunter: 10,
  places: 20). Configurable via `GTM_DAILY_LIMIT_{RESOURCE}`. Engine degrades to free fallbacks
  when limit hit.
- Settings UI: "API Keys" tab (save/delete/test per key, masked input, status badges) +
  "Usage" tab (progress bars per resource, daily reset at UTC midnight).
- Monetization vote: `user_preferences` table, radio + comment in Settings; captures
  own-keys/managed-paid/undecided preference for product direction.
- CSV + Google Sheets deep link: after download, "View in Google Sheets" link on leads page.
- Key resolution wired into pipeline: `Pipeline(resolved_keys=...)` threads to search.py,
  client.py, verifier.py, places.py, web_search.py. CLI path unchanged (env vars only).
- 7 new API endpoints: `/settings/api-keys` (CRUD + test), `/settings/usage`, `/settings/preferences`.
- `cryptography` added to core deps; `.env.example` updated with encryption key + limit overrides.
- Hard filters: `min_google_reviews`, `max_proximity_tier`, `require_online_gap` — applied
  post-scoring in the pipeline. City/province extraction from `config/defaults/pk_cities.yaml`.

**CI** — `ci.yml`: `test` job runs the DB-backed tests against a throwaway `postgres:16`
service (`GTM_TEST_DATABASE_URL`); `web` job runs `npm ci` + `next build` (tsc + ESLint). Both
green. **Local runs skip ~90 DB-gated tests** (no local Postgres); CI runs them all (~342).

**Landing page** — monochrome illustration pass; `web/src/components/marketing/illustration.tsx`
(one reused panel) in Features / How-it-works / Comparison / FAQ. Redundant ones removed.

---

## 3. ENGINE FOCUS — the current work stream (E1–E4)

**The finding that drives this:** the reframe was only *half*-built. Qualification got
reframed, but **discovery was still conventional lead-gen** — it ran ONLY on
`osm_categories`/`overture_categories` the user hand-picked in map-tag syntax; the offer/LLM
never drove *what* was searched, only filtered afterward. A campaign with an offer but no
categories discovered nothing, silently.

- **E1 — offer → discovery targets** ✅ **DONE.** `config/defaults/discovery_taxonomy.yaml`
  maps 16 sectors → valid OSM tags + Overture substrings.
  `discovery/targeting.derive_discovery_targets(offer, industries, llm)` picks sectors
  deterministically (offer/industry keyword match) + LLM-widened — **both only from the
  taxonomy**, so every derived category is a real tag (never an invented `shop=apparel` that
  matches nothing). `pipeline.run()` derives categories when the user gave none; **explicit
  user categories always win**. Sectors → `stats.discovery_sectors`, shown as chips; form says
  categories are optional. Tests: `tests/test_discovery_targeting.py`. Live-verified on Groq.
- **E2 — web-search discovery** ✅ **DONE.** `derive_discovery_targets` now also emits
  `search_queries` — deterministic seeds (industries/sector terms × cities) + optional LLM
  queries aimed at buyers (`llm/tasks.generate_search_queries`; queries are free text so the
  LLM writes them directly). `discovery/web_search.WebSearchDiscovery` runs them via the shared
  `search.search_web` (Brave when keyed, else keyless DuckDuckGo), takes each result's own
  domain, drops directories/aggregators/social, de-dupes, yields a company (asserts only the
  domain + a name from it; the pipeline crawls/classifies/intent-judges the rest, so
  competitors are filtered downstream). Config: `enable_web_search_discovery` (default on),
  `web_search_max_queries_per_run` (6); `CampaignConfig.search_queries`. Wired into `run()`
  (derives queries when the user set none; explicit map categories still win) + `discover()`.
  `max_companies` still caps what gets processed. Tests: `tests/test_web_search_discovery.py`
  (off in the DB fixture to stay hermetic). ⚠️ Not yet live-verified end-to-end on real Brave
  results — do a capped run to confirm quality before trusting it.
- **E3 — competitor-analysis flow** ⬜. The unbuilt 2nd core job: describe a product → find
  competitors → surface their hiring/press/funding. Different flow, larger build. **CEO earlier
  said park it — reconfirm before building.**
- **E4 — optimize** ✅ **mostly DONE** (was deliberately last):
  - **Proactive LLM token pacing** ✅ — `llm/client.TokenBucket` paces GroqLLM calls under the
    ~8k tokens/min free budget up front (was reactive 429-retry only). `GTM_GROQ_TOKENS_PER_MIN`.
  - **Async DB** ✅ — per-company DB calls run off the event loop via `pipeline._db_call`
    (`to_thread` + an asyncio lock; the single connection is not thread-safe). Progress writes
    get their OWN connection in `cli.py` so they never share the pipeline's under threads.
  - **DB reconnection** ✅ — every statement goes through `Database._execute`, which reconnects
    (backoff, search_path re-applied) once on a dropped connection; `_commit` recovers too.
  - **Nominatim** ✅ — explicit `geocode.NOMINATIM_DELAY_S` (1.1s, under the 1/sec public cap;
    disk-cached), `GTM_NOMINATIM_DELAY_S` to override for a self-hosted instance.
  - **Cron failure alert** ✅ — `gather-leads.yml` opens (or comments on) a `crawl-failure` issue
    on failure (keyless GITHUB_TOKEN).
  - ⬜ **Still open:** no in-code **Brave monthly spend counter** (documented in `docs/API_KEYS.md`);
    the async-DB win is real but DB calls are still **serialised** (one connection) — a true
    connection pool would parallelise them, if throughput ever demands it.

---

## 4. ARCHITECTURE & HOW TO WORK HERE

**Stack:** Python 3.12+ engine; FastAPI API (`gtm_engine/api/main.py`); Postgres via
`psycopg` (Supabase); Next.js 16 + Tailwind + shadcn frontend in `web/`. Deployed: frontend +
API on Vercel, crawls in GitHub Actions (`gather-leads.yml`), DB on Supabase.

**Where the core logic lives:**
- `pipeline.py` — the run: `run()` (setup: relevance kw, offer→targets, discover) →
  `discover()` (which sources fire) → `process_company()` (crawl → classify → intent judge →
  contacts → score → build lead). Per-company failures are isolated (one bad company ≠ dead run).
- `discovery/` — `targeting.py` (E1 offer→categories), `osm.py`, `overture.py` (category-gated),
  `chambers.py` (KCCI), `search.py` (WebsiteFinder), `geocode.py` (Nominatim, disk-cached).
- `intent/` — PPRA tenders + company-page RFQ/hiring signals.
- `qualification/buyer_classifier.py` (BUYER/VENDOR/UNKNOWN gate) + `relevance.py`.
- `llm/` — `client.py` (Groq/Gemini/Ollama, retry w/ backoff), `tasks.py` (generate_keywords,
  judge_intent, extract_requirement, classify_reply, draft_hook). All grounded; deterministic
  fallback; **off does not break the engine**.
- `scoring/scoring.py` — decomposed 0–100: review_band + rating + proximity + online_gap +
  pain_evidence. `scoring/proximity.py` — haversine tier scoring.
- `enrichment/` — contacts, email patterns/verify, phones, research brief, external signals,
  `online_presence.py` (gap audit), `places.py` (Google Places API), `hours.py` (OSM hours).
- `campaign/nl_parser.py` — NL text → CampaignConfig (deterministic + optional LLM).
- `outreach/` — sequencer, sender, reply classify, mailboxes (secondary; human-approved).
- `storage/database.py` — thin plain-SQL repo; schema is `CREATE TABLE IF NOT EXISTS` applied
  once per DSN, guarded by an advisory lock; campaigns/leads/runs/drafts/etc.
- `config/` — `schema.py` (Pydantic configs), `loader.py`, `defaults/*.yaml`, `campaigns/*.yaml`
  (the 3 shipped examples), `engine.yaml`, `discovery_taxonomy.yaml`.

**Commands (Windows; strip corrupted `/e/` PATH entries first — see §7):**
```
.venv/Scripts/python.exe -m pytest -q            # tests (DB-gated ones skip without a DB)
.venv/Scripts/python.exe scripts/golden_eval.py  # classifier accuracy vs the golden set
.venv/Scripts/python.exe -m gtm_engine.cli run <campaign_id|path.yaml> --max-companies N
cd web && npm run build                          # frontend gate (tsc + eslint)
```
`.env` (gitignored) is auto-loaded; tests are isolated from it (`isolate_credentials` fixture).
**Never launch a preview/dev server** (standing user order) — verify frontend via `tsc`/`next
build`, not by running it.

**Auth model:** Supabase JWT verified in `api/auth.py` (ES256 vs JWKS). App-wide dependency
stashes the user on `request.state`; `current_user_id` reads `sub`. `GTM_AUTH_DISABLED=1` for
local; tests use `conftest.bypass_auth`.

**Working style (do this):** verify on real data, not assumptions; the engine before the UI;
grounded LLM only (nothing invented); every result carries evidence + provenance; commit +
push each coherent slice with CI kept green; keep MEMORY.md current.

---

## 5. VERIFIED FACTS — do not re-research

**APIs (re-verified live 2026-09-26 against the real key):**
- Groq `openai/gpt-oss-20b` **still works, still free-tier** (a report claimed it left the free
  tier 2026-09-11 — false for us). Binding limit ≈ **8,000 tokens/min** (req limit ~1000/min is
  not the constraint). A judge_intent call ≈ 727 tokens (~90% reasoning).
- Gemini free flash models returned 404/503 → Groq is the default; client walks a model list.
- Hunter free = **50 credits/mo, one shared pool** (verify = 0.5 credit). `docs/API_KEYS.md`
  still wrongly says "50 searches + 100 verifications" and has no Brave spend counter — stale.
- Brave: ~$5/mo credit ≈ 1,000 searches; free plan rejects the `country` param.
- Reddit search RSS = 403 from datacenter IPs (only a spoofed UA gets 200 — refused per
  `docs/DECISIONS.md`). Google News RSS works but is anti-correlated with our ICP (90 days of
  "Khaadi" → nothing usable). Both effectively dropped.
- Overture release is auto-discovered at query time (never stale). Overpass has mirror fallback.
- WhatsApp: no legit registration-check API (Meta's `contacts` endpoint always says "valid").
  Detect via `wa.me` links (proof) then `03xx` mobile prefix (candidate). ToS-safe only.

**Market data (central Karachi, OSM, 2026-09-22):** 13,294 named businesses; 23.0% mobile
(WhatsApp candidates) vs 0.2% email — i.e. phone/WhatsApp is the reachable channel in PK, email
is near-empty. 3.5% have a website *tag* (a floor, not the true rate — a missing tag ≠ no site).

---

## 6. OPEN / BLOCKED (non-code, needs the user)

- CEO sign-off on **multi-country scope** (P3) and on **E3 competitor analysis**.
- Confirm **`GTM_GROQ_API_KEY` is a GitHub Actions secret** — without it the gather-leads job
  degrades to the keyword path (never breaks, but no intent/offer-derived discovery live).
- `GTM_ENCRYPTION_KEY` — added to GitHub Secrets + Vercel env vars (2026-10-03). Verify the
  Settings page no longer shows the red warning after redeployment.
- Missing keys: `GTM_SHEETS_CREDENTIALS_JSON`, `GTM_MAILBOX_2_*`, `GTM_GMAIL_REFRESH_TOKEN`
  (needs `gtm outreach gmail-auth`).
- `docs/API_KEYS.md` quota text is stale (Hunter/Brave); no Brave monthly spend counter in code.
- Support email in the landing FAQ is `outreach.grydin@gmail.com`.
- **Compare leads with vs without Google Places API key** — requested, never executed.

---

## 7. ENVIRONMENT QUIRKS

- **PATH** has corrupted `E:\` entries (`E:\Windsurf\bin`, `E:\flutter\bin`) that break `pip`/
  `npm` — strip `/e/` from PATH first: `export PATH=$(echo "$PATH" | tr ':' '\n' | grep -v '^/e/' | tr '\n' ':')`.
- Long bash heredocs with Python fail to parse in Git Bash — write scripts to the scratchpad.
- No local Postgres password → DB-gated tests skip locally; rely on CI (postgres service) for them.
- Overpass main endpoint rate-limits under load; mirrors work. `request_timeout_s=15` is too
  short for city-wide queries — raise per call.
- Git may warn LF→CRLF on commit; harmless.

---

## 8. HISTORICAL (superseded — kept only as a pointer)

Phases **A–G** (discover → crawl → classify → contacts → verify → score → human-approved
outreach → reply sync) are complete and are the engine's foundation; details in
`docs/ROADMAP.txt`. The **Phase-H "website-selling pivot"** (2026-09-22: sell websites to
businesses with no/dead sites, WhatsApp-first) was **superseded by the 2026-09-25 reframe** —
website-selling is now just one possible offer. The detailed Phase-H task lists and its
"WhatsApp channel / web-presence axis" plans are **obsolete**; the market data and WhatsApp-
detection facts from that work are preserved in §5. Do not treat any Phase-H task as a current
TODO — the live plan is §2–§3.
