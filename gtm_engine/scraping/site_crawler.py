"""Crawl one company website: homepage first, then the handful of pages that carry
buyer evidence (about, contact, team, services, careers). Never a full-site crawl."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from gtm_engine.scraping.fetcher import Fetcher
from gtm_engine.scraping.parsers import ParsedPage, parse_page
from gtm_engine.validation.domains import normalize_url

log = logging.getLogger(__name__)

_PRIORITY = ("about", "contact", "team", "services", "careers")
# Fallback paths tried when the homepage exposes no link of that kind.
_GUESS_PATHS = {
    "about": ("/about", "/about-us", "/about_us", "/pages/about-us", "/company"),
    "contact": ("/contact", "/contact-us", "/contact_us", "/pages/contact-us", "/pages/contact"),
    "team": ("/team", "/our-team", "/leadership", "/management"),
}


@dataclass
class SiteSnapshot:
    website: str
    final_url: str | None
    reachable: bool
    https: bool
    pages: dict[str, ParsedPage] = field(default_factory=dict)  # kind -> page
    error: str | None = None
    raw_html: dict[str, str] = field(default_factory=dict)      # kind -> html (for tech markers)

    @property
    def all_text(self) -> str:
        return " ".join(p.text for p in self.pages.values())

    @property
    def emails(self) -> list[str]:
        out: list[str] = []
        for kind in ("contact", "home", "about", "team", "services", "careers"):
            for e in (self.pages[kind].emails if kind in self.pages else []):
                if e not in out:
                    out.append(e)
        return out

    @property
    def phones(self) -> list[str]:
        out: list[str] = []
        for p in self.pages.values():
            for ph in p.phones:
                if ph not in out:
                    out.append(ph)
        return out

    @property
    def social(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        for p in self.pages.values():
            for k, v in p.social.items():
                merged.setdefault(k, v)
        return merged

    @property
    def team(self) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for kind in ("team", "about", "home"):
            if kind in self.pages:
                for pair in self.pages[kind].team:
                    if pair not in out:
                        out.append(pair)
        return out


class SiteCrawler:
    def __init__(self, fetcher: Fetcher, max_pages: int = 6):
        self.fetcher = fetcher
        self.max_pages = max(1, max_pages)

    async def crawl(self, website: str) -> SiteSnapshot:
        url = normalize_url(website)
        if not url:
            return SiteSnapshot(website=website, final_url=None, reachable=False, https=False, error="bad_url")

        home = await self.fetcher.get(url)
        if not home.ok and url.startswith("https://"):
            # Small businesses often have http-only sites with broken TLS.
            fallback = await self.fetcher.get("http://" + url[len("https://"):])
            if fallback.ok:
                home = fallback
        if not home.ok or not home.is_html:
            return SiteSnapshot(website=website, final_url=home.final_url, reachable=False,
                                https=False, error=home.error or f"status_{home.status_code}")

        snap = SiteSnapshot(website=website, final_url=home.final_url, reachable=True,
                            https=home.final_url.startswith("https://"))
        home_page = parse_page(home.final_url, home.text)
        snap.pages["home"] = home_page
        snap.raw_html["home"] = home.text

        budget = self.max_pages - 1
        visited = {home.final_url.rstrip("/")}
        for kind in _PRIORITY:
            if budget <= 0:
                break
            candidates = []
            if kind in home_page.internal_links:
                candidates.append(home_page.internal_links[kind])
            # At most two guesses per kind so 404s cannot eat the whole page budget.
            candidates += [home.final_url.rstrip("/") + p for p in _GUESS_PATHS.get(kind, ())[:2]]
            for candidate in candidates:
                if candidate.rstrip("/") in visited:
                    continue
                visited.add(candidate.rstrip("/"))
                res = await self.fetcher.get(candidate)
                budget -= 1
                if res.ok and res.is_html:
                    snap.pages[kind] = parse_page(res.final_url, res.text)
                    snap.raw_html[kind] = res.text
                    break
                if budget <= 0 or kind in home_page.internal_links:
                    # A linked page that failed is not worth guessing around.
                    break
        log.debug("crawled %s -> %s", website, list(snap.pages))
        return snap
