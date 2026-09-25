# Frontend work: public landing page + private login gate

**Temporary working note.** Delete once Phase 4 ships. The durable record is the commit
history and `docs/`.

**Four phases total. 1 and 2 are done and pushed; 3 and 4 remain.**

---

## Why this exists

`web/` was a dashboard and nothing else. The root layout wrapped every route in
`<AppShell>`, so `/` was the dashboard behind a sidebar — no marketing surface, no sign-in.

And the API had **no authentication at all** while being publicly deployed. `main.py` said
so in its own first line. All 122 leads and their contact emails were readable with a bare
`curl`, `POST /campaigns/{id}/run` would spend crawl credit for a stranger, and
`POST /outreach/send` could dispatch real email. CORS was never a defence — it is a browser
policy and `curl` ignores it.

Ryvl (`ryvl.app`) is the structural reference: hero with an animated product shot, source
marquee, features bento, three-step walkthrough, device mockups, FAQ, closing CTA. We take
the **structure and density, not the content or identity** — Qualifyr is a buyer-only B2B
lead engine for Pakistan, not seller price intelligence.

## Decisions already made

- **Private login gate, one operator.** Not multi-tenant. No table carries a `user_id` or
  `org_id`, and campaigns are YAML files on disk rather than rows, so real signups would be
  a separate and much larger project. A valid token means "the operator", not "user X".
- **Public signup stays disabled in Supabase.** The single user is created by hand. The
  landing CTA requests access by email; it does not create accounts.
- **No mobile app.** The device-mockup section shows the *responsive dashboard* and must be
  captioned as such. No app-store language.
- **One brand accent** on an otherwise neutral palette. Jade, not the reference's indigo.

---

## Phase 1 — Foundation ✅ `67dcb93`

Route groups, so a public page does not wear the signed-in furniture:

```
app/layout.tsx              html/body, Inter, ThemeProvider   (no AppShell)
app/(marketing)/layout.tsx  sticky nav + footer          → /
app/(auth)/layout.tsx       split-screen panel           → /sign-in
app/(app)/layout.tsx        AppShell + auth guard        → /dashboard, /campaigns,
                                                           /leads, /outreach, /settings
```

Route-group folders do not appear in URLs, so only the dashboard moved: `/` → `/dashboard`.

- **Theme hoisted out of `AppShell`.** It was a `useState(false)` in there — reset on every
  reload, and unreachable from any page outside the shell. Now reads the `dark` class on
  `<html>` through `useSyncExternalStore`, with an inline `<head>` script applying it before
  first paint so dark-mode users stop seeing a white flash. Reading the class rather than
  mirroring it also avoids the cascading re-render eslint correctly refuses.
- **Brand token** in `globals.css`: `--brand: oklch(0.58 0.13 168)`, lifted to `0.72` in
  dark where the light value cannot clear contrast against near-black. Accent only — CTAs,
  links, the hero accent word — never a surface.
- Added `accordion` and `label`. **Skipped `sonner`**: an inline error beside the password
  field beats a toast for a login form.
- Buttons rendering as links need `nativeButton={false}`; Base UI warns loudly otherwise
  and is right to.

## Phase 2 — Auth and API lock-down ✅ `7d2e7db`, `77ecf1d`

**Your Supabase signs tokens with ES256 against a published JWKS, not the legacy HS256
shared secret.** So there is no `GTM_SUPABASE_JWT_SECRET`; the API fetches the public key
from `GTM_SUPABASE_URL` and verifies locally (a round-trip per request would land on every
serverless cold start).

- `gtm_engine/api/auth.py` — dependency registered **app-wide**, so a route added later is
  protected by default rather than open by default. `PUBLIC_PATHS` holds the one exception,
  `/health`.
- **Fails closed.** Unset `GTM_SUPABASE_URL` → 500 with a reason. Treating "unconfigured"
  as "allow" is exactly the bug being fixed. `GTM_AUTH_DISABLED` is an explicit opt-*out*
  for local dev, so a missing or misspelled variable can never reopen the door.
- **`/docs` and `/openapi.json` are removed, not guarded.** Writing the test first showed
  `/openapi.json` still returning 200 with all 35 routes — FastAPI registers it inside its
  own `setup()`, outside app dependencies. They now exist only when auth is disabled.
- Rejections do not explain themselves ("invalid token", not which claim failed).
- `tests/test_api_auth.py` — 16 tests including a token re-signed by another key and one
  minted for a *different* Supabase project. Existing API tests bypass the dependency via
  `conftest.bypass_auth` rather than minting real tokens.
- Browser side: `@supabase/ssr`, sign-in form with inline errors, `middleware.ts` guarding
  the five dashboard routes, bearer token attached per request in `lib/api.ts` (read each
  time — the SDK rotates it), sign-out control.
- Middleware uses `getUser()`, not `getSession()`: the latter trusts the cookie, the former
  verifies it, so a forged cookie cannot walk past the redirect.

**Verified:** `/dashboard` and `/leads` → 307 to `/sign-in?next=…`; `/` and `/sign-in` open.

### ⚠️ Blocked on the user — the deployed app is broken until these are done

1. Supabase → Authentication → Providers → **disable new signups**; Users → **add the one
   account**. `https://supabase.com/dashboard/project/tiqcqqwblmmxyttxqljm/auth/providers`
2. Vercel env: `GTM_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_URL` (both
   `https://tiqcqqwblmmxyttxqljm.supabase.co`), `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
3. **Redeploy** — `NEXT_PUBLIC_*` is inlined at build time, so setting the vars alone
   changes nothing about an existing build.

`web/.env.local` exists locally with a **placeholder** anon key (gitignored). Replace it to
sign in locally.

## Phase 3 — Landing page ⬜

`app/(marketing)/page.tsx` as a Server Component composing `components/marketing/`. Only
the slideshow, marquee and FAQ are client components.

| Section | Notes |
|---|---|
| Hero | Eyebrow pill, headline with one jade accent word, subhead, dual CTA, trust line |
| **Product slideshow** | Browser-chrome frame cycling Overview → Campaigns → Leads → Outreach. **Real HTML/CSS, not screenshots** — stays sharp, themes with dark mode, never drifts from the real UI. Auto-advance ~5s, dot controls, pause on hover/focus, frozen under `prefers-reduced-motion` |
| **Source marquee** | "Built on free public sources" — OpenStreetMap, Overture Maps, PPRA, KCCI, GDELT, Greenhouse, Lever, GitHub. CSS-only duplicated track, pause on hover, static grid under reduced-motion. These are the real sources in `gtm_engine/discovery/` |
| Features bento | Buyer-only classification, explainable 0–100 scoring, contact discovery + email validation, GTM intelligence signals, human-approved outreach, CSV/Sheets export |
| How it works | Define your campaign → We discover and qualify → Approve and send |
| Device mockups | Desktop + phone frame of the responsive dashboard. Captioned as responsive |
| FAQ | `accordion`, **not** the reference's radial ring — that ring is unusable on mobile and hostile to screen readers |
| Final CTA + footer | Jade band; footer already built in Phase 1 |

Verify: Lighthouse ≥ 95 performance and accessibility; keyboard-only pass; 375 / 768 /
1440px; both themes; reduced-motion on.

## Phase 4 — Polish ⬜

Per-route `metadata` + OpenGraph, `opengraph-image.tsx`, `sitemap.ts`, `robots.ts`, favicon.
Replace the root `metadata.description` ("Buyer-only GTM lead engine") with marketing copy.

**Then** write the ChatGPT image prompts — the user asked for these *after* the structure
exists, not before. Slots: wordmark + icon, auth-panel illustration, FAQ illustration, OG
image, optional hero backdrop. The slideshow, marquee and device frames are deliberately
**code, not images**, so they theme correctly and never go stale.

---

## Not phases — open bugs from the code review

1. **Double-counted signal scoring.** `scoring.py:122` counts `len(sig.buying)` *and* adds
   an explicit bonus for the same signal, so each is worth ~2× its intended weight and one
   signal saturates the 10-point bucket. Measured: a press mention scores 6 as written vs 3
   scored once. Changes who clears `min_score: 70`, i.e. who gets emailed.
2. **`press_signals.py:73` bypasses robots.txt** on prospect sites by passing `api=True`, a
   flag meant for API endpoints, in a project that sets `respect_robots: true`. Also trim
   `FEED_PATHS` from 10 — a site with no feed costs ~20s for nothing.
3. **`GTM_GITHUB_TOKEN` has two jobs.** `github_signals.py:24` reuses the workflow-dispatch
   PAT for third-party org reads, and that variable is deliberately absent from
   `gather-leads.yml` — so in Actions the signal runs keyless at 60 req/hr and silently
   403s. Needs a separate read token, and the guessed org should be verified against the
   domain before scoring +1.5 on it.
