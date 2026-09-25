# MEMORY — working tracker

Living state of the project: what is done, what is next, what was decided and why,
and the facts we verified so nobody researches them twice.

`docs/ROADMAP.txt` is the historical record of phases A–G. `docs/DIRECTION.md` is the CEO
direction and overrides anything here. **`PLAN.md` (2026-09-25 product reframe) is the current
direction and supersedes the Phase H framing below** — the website-selling pivot is now just
one possible "offer" in an offer-agnostic search engine.

Last updated: 2026-09-22 (see PLAN.md for the 2026-09-25 reframe)

---

## Where we are

Phases **A–G complete**, scraping hardened, **213 tests passing**, credentials tested live.
Engine runs end to end: discover → crawl → buyer/vendor gate → contacts → verify → score →
human approval → send → reply sync.

**But the offer changed, and the engine is now pointed the wrong way.**

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
