# Qualifyr web UI

Next.js 16 + Tailwind v4 + shadcn/ui front end for the GTM Lead Engine. Talks to the FastAPI
backend (`python -m uvicorn gtm_engine.api.main:app --reload`, port 8000). No auth.

```bash
npm install
npm run dev          # http://localhost:3000
```

Set `NEXT_PUBLIC_API_URL` if the API is not on `http://localhost:8000` (see `.env.local.example`).

Pages: Dashboard · Campaigns (run discovery, download CSV) · Leads (filter, inspect reasons,
suppress) · Outreach (review queue: preview, edit, approve/reject, send; sequence; activity).

Layout and components come from https://github.com/ceyhanmolla/shadcn-crm-dashboard (MIT).
