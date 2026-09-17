# Decisions

Record of technical and product decisions, newest first.

| Date | Decision | Why |
|------|----------|-----|
| 2026-09-17 | robots.txt is enforced for website crawling only, not for API endpoints (Overpass, search) | overpass-api.de disallows `/api/` for crawlers, but it is an API meant for programmatic queries; robots.txt governs crawlers |
| 2026-09-17 | A vendor term in the company *name* is decisive (VENDOR) regardless of buyer terms elsewhere | "Retail Growth Consultancy" mentions retail constantly; vendors serving our target industry are the main false-positive class |
| 2026-09-17 | Buyer/vendor matches weighted by location: name/title/meta/first 800 chars ×3, body ×1 | Retailer footers routinely say "designed by X digital marketing agency" |
| 2026-09-17 | SQLite for the core engine; Supabase considered for the UI/hosting phase | Spec is local-first and tests must run offline; storage is a thin repository with portable SQL so the swap is one module |
| 2026-09-17 | `httpx` + own polite fetcher instead of Crawlee | Phase 1 fetches ~5 pages per site; a `Fetcher` protocol lets Crawlee/Playwright slot in for JS-heavy sites later |
| 2026-09-17 | Stdlib `csv`/`sqlite3`/`argparse` over pandas/SQLAlchemy/typer | Spec rule: check stdlib before adding a dependency |
| 2026-09-17 | Primary spec = `GTM_Lead_Engine_Claude_Code_Spec.docx`; older spec's LinkedIn/theHarvester/Apollo suggestions dropped | ToS risk, paid tiers, and the primary spec forbids LinkedIn as a dependency |
| 2026-09-17 | Search fallback (DuckDuckGo HTML) accepts a website only if the company name is clearly in the domain or title | A wrong website is worse than none: it would qualify the wrong company |
