# MEMORY — working tracker

Living state of the project: what is done, what is next, what was decided and why,
and the facts we verified so nobody researches them twice.

`docs/ROADMAP.txt` is the historical record of phases A–G. `docs/DIRECTION.md` is the CEO
direction and overrides anything here. **`PLAN.md` (2026-09-25 product reframe) is the current
direction and supersedes the Phase H framing below** — the website-selling pivot is now just
one possible "offer" in an offer-agnostic search engine.

Last updated: 2026-09-26

---

## CURRENT STATUS (2026-09-26) — read this first

The 2026-09-25 reframe (PLAN.md) is **built**. Qualifyr is now an offer-agnostic
market-research search engine: describe what you sell → the LLM derives relevance keywords →
discovery targets a chosen region under a spend cap → irrelevant signals are filtered → each
qualified company returns with a research brief and a matched decision-maker.

**Reframe priorities — all done:**
- **P1 Dynamic campaigns** ✅ — user-created, DB-backed (create/list/delete/run-by-id), a New-campaign form, runs accumulate. `resolve_campaign()` loads by id-or-path; CLI `campaign-id`.
- **P2 Hard filters + LLM keywords** ✅ — `llm/tasks.generate_keywords(offer)`, `qualification/relevance.relevant_terms`; pipeline gates hiring/RFQ signals by relevance to the offer's *need*-terms (not sector) — the Imtiaz fix; generated keywords also feed PPRA discovery + the classifier; keywords shown as chips; offer-relevant intent scores +3; `stats.intent_dropped_irrelevant` surfaced.
- **P3 Region filter** ✅ — `GeographyConfig.provinces` + `search_areas()`; OSM/Overture iterate areas and try each country as a geocode hint (one campaign can span countries). ⚠️ tension with "Pakistan only" CEO directive — needs sign-off.
- **P4 Result caps** ✅ — `max_companies` is the per-run cap ("API cap" in the form); added `website_finder_max_per_run` to bound Brave.
- **P5 Research depth** ✅ — `enrichment/research.build_research_brief` (grounded per-company summary → `Lead.research_brief`, shown at top of lead detail); decision-maker's own LinkedIn `/in/` profile extracted and matched by name (`parsers.personal_profiles`, `_match_personal_profile`, requires both names — never a stranger's).
- **Golden-set harness** ✅ — `gtm_engine/eval/golden.py` + `tests/golden/golden_leads.jsonl` (18 rows) + `scripts/golden_eval.py` + `tests/test_golden_set.py` (accuracy floor 0.8, baseline 100%; hard invariants: agency never buyer, retailer never rejected).
- **CI wired** ✅ — `ci.yml` runs DB-backed tests against a `postgres:16` service (`GTM_TEST_DATABASE_URL`) AND builds the frontend (`npm ci` + `next build`). Both jobs green.

**Test counts:** ~203 pass locally (86 DB-gated skip without a DB), ~286 in CI with the Postgres service.

**Multi-tenancy** ✅ (built 2026-09-26) — campaigns carry an `owner_id` (migrated in via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`); set on create from the Supabase token's `sub` (`current_user_id`), preserved on re-upsert via `COALESCE` so a pipeline run never blanks it. Every `/campaigns/{id}/...` route is guarded by `require_campaign_access` and every `/leads/{id}/...` route by `require_lead_access` (lead → campaign → owner), both attached as `dependencies=[...]` on the decorator so new routes are guarded by adding it there. A campaign the caller may not see is **404, not 403** (existence not leaked). `GET /campaigns` and `list_campaigns(owner_id)` return only the caller's own DB campaigns plus shared ones. **Shared by design:** file-based example campaigns and legacy NULL-owner DB campaigns. **No scoping** when auth is off/bypassed (local operator, tests) — `current_user_id` is None. Suppressions + mailboxes remain global (operator-level infra, not per-user data) — revisit if that changes. Tests: `tests/test_multitenancy.py` (5 DB-backed). Full suite green locally (203 pass / 91 DB-skip); the 5 new tests run in CI against the postgres service.

**Full-platform test pass (2026-09-26)** — ran regression + adversarial + in-process load
testing against a real Postgres (throwaway PG16 on :5433 via the installed D:\PostgreSQL\16
binaries with trust auth — the machine's own `postgresql-16-D` cluster's password is unknown;
CI uses its own postgres service). **342 tests pass, 0 skipped.** Three lapses found and fixed:
1. A campaign/lead id with a NUL byte → 500 (psycopg rejects NUL); guards now 404 it first.
2. `GET /campaigns/{id}/outreach/activity` used SQLite `?` placeholders → 500 on every call; now `%s`.
3. Cold-start DDL race: concurrent `CREATE TABLE IF NOT EXISTS` on a fresh DB → `pg_type`
   unique violation; `Database.__init__` now serialises schema creation with a
   transaction-scoped advisory lock (`pg_advisory_xact_lock`), pooler-safe.
New test files: `tests/test_multitenancy.py`, `tests/test_multitenancy_adversarial.py`
(every scoped route 404s for a non-owner; hostile ids → clean 404, never 500),
`tests/test_load_concurrency.py` (isolation under load, unique ids under concurrent create,
run-dispatch stampede never 500s, bulk listing, connection-pool safety). Known best-effort
(not a bug, documented in the test): the active-run 409 guard is a read-then-dispatch, so a
dispatch stampede can let more than one through — never crashes.

**Intent-based matching (CEO 2026-09-26): "leads strictly by our intent, not keywords".** Confirmed the "7 points" against the proposal (`GTM_Lead_Engine_Claude_Code_Spec.docx`): Section 6 = the per-company research checklist (incl. web activity/quality — the Rizvi Dental case), Section 8 = the 5 scoring dims. Competitor analysis parked per CEO. Built in 4 slices, all pushed + CI green:
- **S1** `llm/tasks.judge_intent(offer, evidence)` → grounded `{buyer, confidence, reason}`; None without an LLM. Live-verified on Groq (Khaadi 0.92, Imtiaz 0.7, agency rejected 0.9).
- **S2** wired into `pipeline._process_company` via `apply_intent_verdict(cls, verdict)` (threshold 0.6): confident non-buyer demotes a keyword-only BUYER→UNKNOWN, confident buyer promotes UNKNOWN→BUYER, VENDOR never promoted; `scoring.score_lead` rewards evident need (×confidence). Stored on Lead: `intent_fit/intent_confidence/intent_reason`.
- **S3** `enrichment/research.build_research_brief` deepened to the Section-6 checklist — web-presence verdict (flags the thin single-page/no-public-detail case + missing site), intent line, tech, source. Takes `quality`.
- **S4** UI: intent badge + reason in the lead detail (`web/.../leads/page.tsx`, `Lead` type in `api.ts`).
- **Enabled the LLM layer:** `config/engine.yaml` now `enable_llm: true`, `llm_provider: groq`. ⚠️ **GTM_GROQ_API_KEY must be a GitHub Actions secret** for intent to run in the gather-leads job; without it the engine degrades to the keyword path (never breaks). Intent adds one Groq call per non-vendor company (bounded by the run cap).

**Also fixed 2026-09-26 (deployed-app bugs):** CSV download now uses an authenticated fetch (`api.downloadExport`, was a bare <a> → "missing bearer token") and honours the type + min-score filters; `/campaigns` sped up by replacing per-campaign full-lead loads with a SQL aggregate (`Database.campaign_counts`).

**ENGINE FOCUS (2026-09-26) — the current work stream.** Analysis found the reframe was only
*half*-built: qualification got reframed (relevance gate, judge_intent by need-not-sector,
research brief) but **discovery was still conventional lead-gen** — gated ONLY on
user-hand-picked `osm_categories`/`overture_categories`; the offer/LLM keywords only FILTERED
after discovery, never drove *what* was searched. A campaign with an offer but no categories
discovered nothing, silently. That is the biggest remaining gap from "describe your offer and
it searches". Engine plan **E1–E4**:
- **E1 offer → discovery targets** ✅ **DONE (f2f936b)** — `config/defaults/discovery_taxonomy.yaml`
  maps 16 business sectors → valid OSM tags + Overture substrings.
  `discovery/targeting.derive_discovery_targets(offer, industries, llm)` picks sectors
  deterministically (offer/industry keyword match) and, with the LLM on, widens them — both
  choosing ONLY from the taxonomy, so every derived category is a real tag (never an invented
  `shop=apparel` that silently matches nothing). `pipeline.run()` derives categories when the
  user supplied none; **explicit user categories always win** (deriving only fills the gap).
  Chosen sectors → `stats.discovery_sectors`, surfaced in the campaign summary + shown as chips;
  New-campaign form now says categories are optional. Live-verified on Groq (clothing/pharma/
  restaurant offers → correct sectors → valid tags). Tests: `tests/test_discovery_targeting.py` (7).
- **E2 web-search discovery** — TODO. Find companies by *what they do* (run the offer's derived
  search queries via Brave/search, extract names/domains), so the universe includes software
  firms, services, online brands — anything without a mapped storefront. Second half of
  "describe your offer and it searches". `WebsiteFinder` today only resolves a known name→URL.
- **E3 competitor-analysis flow** — TODO. The unbuilt 2nd core job in PLAN.md: describe a
  product → find competitors → surface their hiring/press/funding. (CEO earlier said park it;
  reconfirm before building.)
- **E4 optimize** — TODO, deliberately LAST (hardening the wrong shape is waste). Items:
  LLM token pacing (measured Groq free limit ≈ **8,000 tokens/min**, ~11 judge_intent calls/min
  sustainable — currently only reactive 429-retry, no proactive token bucket); DB is a single
  SYNC psycopg conn with no `to_thread`/lock, so `concurrency=4` does not parallelize DB calls
  and every write blocks the event loop; no DB reconnection handling if the conn drops mid-run;
  Nominatim policy is **4 req/min for scheduled/regular scripts** (code targets 1/sec — mitigated
  by the disk geocode cache, but P3's provinces/multi-country add more first-time lookups); no
  failure alerting on the weekly gather-leads cron beyond GitHub's default email.

**Landing page (2026-09-26):** staleness pass with a monochrome illustration pack.
`web/src/components/marketing/illustration.tsx` (one reused theme-adaptive panel) used in
Features (`feature-qualification-funnel`), How it works (`process-three-step`, wide), Comparison
(`noise-to-qualified`), FAQ (`faq-woman-inquiring` beside the heading). Two were tried then
removed as redundant with existing coded UI: `faq-support-side` (support card kept its icon) and
`mobile-approval` (See-it-in-action kept its coded phone mockups) — those PNGs deleted. Pack's
SVGs are base64-PNG wrappers, so PNGs used directly via next/image. Hero/stats/marquee/nav/footer
untouched.

**Remaining (non-engine):**
- Verify GTM_GROQ_API_KEY is in the repo's GitHub Actions secrets, then run a real campaign to see intent-driven + offer-derived-discovery leads live.
- Open non-code items: CEO sign-off on multi-country scope (P3) and on E3 competitor analysis; other API keys (Sheets, Hunter/Reacher, mailbox 2); `docs/API_KEYS.md` still has wrong Hunter/Brave quotas and there is no Brave spend counter.

**Support email** in the landing FAQ is `outreach.grydin@gmail.com`.

**API facts re-verified 2026-09-26 (live, against the real key):** Groq `openai/gpt-oss-20b`
still works and is still on the free tier (a report claimed it left the free tier 2026-09-11 —
false for us); free rate limit ≈ 1000 req/min but the binding limit is **8000 tokens/min**;
a judge_intent-sized call ≈ 727 tokens (~90% reasoning). Hunter free = 50 credits/mo (unchanged).
Overture release auto-discovered at query time (never stale). Overpass has mirror fallback.

Everything below is the **historical Phase-A–G + Phase-H record**, kept for the verified facts.
The website-selling pivot is now just one possible "offer", not the product.

---

## Where we are (historical, pre-reframe)

Phases **A–G complete**, scraping hardened, credentials tested live.
Engine runs end to end: discover → crawl → buyer/vendor gate → contacts → verify → score →
human approval → send → reply sync.

---

## THE PIVOT (decided 2026-09-22)

We now sell **websites**:

* Business has **no website** → we offer to build one.
* Business has a **bad/dead/dated website** → we offer to rebuild it.

This inverts the engine's core assumption. Two things are currently broken by it:

1. `buyer_classifier.py` returns `UNKNOWN` when a site is unreachable, which hard-blocks
   outreach. Our best leads can never be contacted.
2. `scoring.py` awards points for a healthy site (`+5 reachable`, `+2 https`,
   `−1 not mobile-friendly`). **A good website currently scores as a good lead.**

Also decided: **Pakistan is WhatsApp-first, email second.** Gulf/elsewhere is email-first.
Channel order is per-campaign config, never hardcoded.

---

## Verified facts (measured, not assumed — do not re-research)

### Market data — central Karachi, OpenStreetMap, 2026-09-22

| Metric | Count | Share |
|---|---|---|
| Named businesses | 13,294 | 100% |
| Any phone | 3,713 | 27.9% |
| **Mobile `03xx` (WhatsApp candidates)** | **3,054** | **23.0%** |
| Landline (not WhatsApp) | 579 | 4.4% |
| Website tagged | 469 | 3.5% |
| **Email tagged** | **31** | **0.2%** |
| Explicit `contact:whatsapp` tag | 0 | 0.0% |

**WhatsApp candidates outnumber emails 98:1.** Email-only would reduce a 13,000-company
market to ~31. This is why WhatsApp-first is not optional.

Lahore central (1,025 named): 21.1% phone, 12.8% website, 7.7% email — same pattern.

Caveat: a missing OSM tag means *untagged*, not *absent*. The 3.5% website figure is a
**floor, not a true rate.** Never assert "you have no website" from a missing tag alone.

### API limits and access

| Service | Reality | Our status |
|---|---|---|
| **Hunter** | **50 credits/month, one shared pool.** 1 credit = email found; **0.5 credit = verification** | `docs/API_KEYS.md` wrongly says "50 searches + 100 verifications" as separate pools — **needs fixing** |
| **Brave Search** | **$5/1,000 requests, $5/month free credit ≈ 1,000 searches.** Credit card required even on free. 50 QPS | Docs wrongly say "2,000 queries/mo". **No budget counter in code — will fail silently mid-month** |
| **Reddit search RSS** | **403 from datacenter IPs.** Works only from residential. Returns 200 with a spoofed browser UA — *we do not do this* (see `docs/DECISIONS.md`) | **Dropped permanently** |
| **Reddit Data API** | Free tier is non-commercial only; commercial needs manual approval (2–4 weeks) then $0.24/1k | Dropped |
| **Google News RSS** | Free, keyless, works. `when:1d` and `site:` operators work. `gl`/`ceid` set *edition*, do **not** filter by country | Demoted to optional enrichment — see below |
| **WhatsApp Cloud API** | `contacts` endpoint **no longer reports real registration status** — always returns valid + a WhatsApp ID. Useless for checking | No legitimate API exists |
| **Gemini free tier** | Key valid, all free flash models 404/503 on this account | Groq (`openai/gpt-oss-20b`) used instead |

### Why Google News is near-useless for our ICP

Searched `"Khaadi"` (one of Pakistan's largest retail brands) over **90 days** → 3 results,
one a data aggregator, two about a different company. `"Lahore" "new store"` over 30 days →
one article about a Lego franchise abroad.

**News coverage is anti-correlated with our ICP.** Small businesses with no website are by
definition the ones nobody writes about. Do not build discovery on news.

### WhatsApp number detection — no API, use tiered evidence

| Tier | Signal | Strength |
|---|---|---|
| 1 — proof | `wa.me/` or `api.whatsapp.com/send?phone=` link on their site or FB page | Self-declared. Certain. |
| 2 — candidate | Mobile format `03xx` / `+923xx` (`classify_phone` already does this) | Strong in PK |
| 3 — no | Landline `021`/`042`/`051` | Call-only, never WhatsApp |

Third-party WhatsApp-check services (whapi.cloud, WAHA) drive an unofficial WhatsApp Web
client. **ToS violation + ban risk. Ruled out** — doubly so for an open-source repo where
collaborators would inherit the risk.

---

## PHASE H — offer pivot: web-presence targeting + WhatsApp-first channel

**Est. 5–6 working days.** Order matters: safety gate first, then the pivot.

### H0 · Golden set — *do first*
- [ ] 50 hand-labelled real Karachi businesses across all four quadrants + web agencies
- [ ] Score the engine against it, record the **pre-pivot baseline**
- **Gate:** if post-H1 accuracy falls below this baseline, **H1 does not ship**

Without this, "quality was not affected" is unverifiable. It is the only measure that
answers the quality question rather than reducing the odds of a bad answer.

### H5 · Vendor list rebuild — *ships before the pivot*
- [ ] Rewrite `negative_keywords` around web design, digital marketing, software houses,
      IT services, freelance developers
- [ ] Own regression tests
- **Pass:** no web agency ever enters the queue

Pitching web development to a web agency is the worst failure available, and PK map data is
dense with small IT shops (`office=it`, `office=company` are top Karachi categories).

### H1 · Web presence becomes the targeting axis
- [ ] Add `web_presence` to the Lead model: `none | social_only | parked | placeholder | dead | dated | healthy`
- [ ] Stop discarding `integrity.py` results — it already computes this, we throw it away
- [ ] Remove the `UNKNOWN` hard-block at `buyer_classifier.py:131`, behind a campaign flag
- [ ] Make company-quality weights in `scoring.py:70` campaign-driven (invert for this offer)
- [ ] Add `company_size` (`sme` | `corporate`) — Talha's axis; drives pitch and price
- **Pass:** a shop with a parked domain reaches the queue as HIGH; the old retail campaign scores unchanged

### H2 · WhatsApp channel
- [ ] `classify_phone` mobile → WhatsApp channel; landline → call-only
- [ ] Crawler extracts `wa.me` links (Tier-1 confirmation)
- [ ] Channel-aware outreach gate — a verified mobile qualifies a lead **without an email**
- [ ] `channel_priority: [whatsapp, email]` per campaign (Gulf flips it)
- **Pass:** ≥3,000 Karachi businesses reach a WhatsApp queue; no landline ever labelled WhatsApp

### H3 · Absence confirmation
- [ ] Two independent probes (Brave + DNS on `name.pk` / `name.com.pk`) before claiming "no website"
- [ ] Brave **monthly credit counter** (currently missing — silent failure risk)
- **Pass:** a business with an untagged but real website is never told it has none

### H4 · Hunter credit fix → 5x executives
- [ ] Credit-based budget (verify 0.5, search 1.0), replacing the wrong `monthly_budget = 100`
- [ ] **Never** use Domain Search — we can generate candidates free
- [ ] Infer pattern first (`infer_pattern` exists), then verify **one** candidate
- [ ] `require_decision_maker` campaign flag — generic `info@` held for review, not sent
- **Pass:** 100 decision-makers/month on the free tier instead of 20

Current cost is 5 candidates × 0.5 = 2.5 credits/person = 20 people/month.
Pattern-inferred single verify = 0.5 credits/person = 100 people/month.

---

## Quality measures (must never regress)

Already built and tested:

* Buyer/Vendor/Unknown gate — nothing reaches outreach without passing
* Per-field `provenance` — every field records its origin
* `website_mismatch` — a site that isn't theirs supplies **no** email, phone or names
* Unverified guesses land in `candidate_email`, shown but **never sent**
* Integrity checks — parked / soft-404 / placeholder / binary / marketplace-redirect
* **Human approves every email** — preview, edit, approve, reject
* Reviewer verdicts + accuracy metric (target ≥80%)
* Suppression list, homoglyph rejection, IDN folding, dedupe by company key

Phase H adds: vendor guard ships first (H5), absence confirmed by two probes (H3),
landline can never be WhatsApp (H2), every no-website lead carries its evidence.

**Known risk, accepted with mitigation:** H1 relaxes the `UNKNOWN` block, which exists
because a map record alone is thin evidence. Mitigation — the evidence standard *changes*
rather than disappears (category + name + confirmed absence + mobile = four converging
signals), and **every no-website lead goes to a human-sent queue, not an automated
sequencer.** Plus the H0 baseline gate.

Smaller exposures: `shop=yes` is 13% of Karachi records with no stated business type — keep
out until name-based inference is reliable. Mobile-prefix inference has a miss rate; zero
businesses tag `contact:whatsapp`, so we are always inferring.

---

## Blocked on the user

- [ ] **The offer and rough price bands** (SME vs corporate) — blocks templates only
- [ ] **Confirm the WhatsApp queue is manual** — H2 delivers a list, not a sender
- [ ] `GTM_MAILBOX_2_USER` / `GTM_MAILBOX_2_PASSWORD` — not in the credentials PDF
- [ ] `GTM_SHEETS_CREDENTIALS_JSON` — PDF points at a Drive file we cannot open
- [ ] `GTM_GMAIL_REFRESH_TOKEN` — needs the user to run `gtm outreach gmail-auth`
- [ ] Add tested keys as GitHub Actions repository secrets

---

## Explicitly NOT in Phase H

| Item | Why |
|---|---|
| Reddit (any form) | Blocked from CI; the only workaround spoofs our identity |
| Google News RSS | Anti-correlated with our ICP — proven on Khaadi |
| Job boards / Rozee | Best remaining source, but an addition not a prerequisite |
| Gulf campaigns | After PK works; config already designed to flip |
| Supabase / Vercel | **Deploying now would ship inverted scoring** |
| WhatsApp *send* automation | Requires a ToS-violating client. Never in this repo. |
| LLM changes | Layer is done and grounded; leave it |

---

## Backlog after H

1. Job boards (Rozee, Mustakbil) — hiring a Social Media Manager with no website is a
   textbook lead. Behavioural signal from the company itself, unlike news.
2. `shop=yes` name-based category inference (13% of the market currently unusable)
3. Relevance: weight structured map categories above free-text body matching
4. Gulf campaign (email-first, `require_decision_maker: true`)
5. Supabase + Vercel deployment
6. Open-source readiness: contributor docs, pluggable channel providers, no ToS-violating deps

---

## Environment quirks

* PATH has corrupted `E:\` entries (`E:\Windsurf\bin`, `E:\flutter\bin`) that break
  `pip install` — strip `/e/` from PATH first
* Long bash heredocs containing Python fail to parse in Git Bash — write to the scratchpad
  and run from there
* Overpass main endpoint rate-limits and times out under load; mirror
  `overpass.kumi.systems` works. Default `request_timeout_s = 15.0` is far too short for
  city-wide queries — raise it per call
* `.env` is gitignored and loaded automatically; tests are isolated from it via the autouse
  `isolate_credentials` fixture
