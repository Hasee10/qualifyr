"""Search-engine fallback: find a company's own website when the discovery source did
not carry one. Conservative by design: a result is accepted only when the company name
clearly appears in the result domain or title. Wrong websites are worse than none."""

from __future__ import annotations

import logging
import re
from urllib.parse import parse_qs, quote_plus, urlparse

from bs4 import BeautifulSoup

from gtm_engine.config.schema import EngineSettings
from gtm_engine.scraping.fetcher import HttpFetcher
from gtm_engine.validation.dedupe import normalize_name
from gtm_engine.validation.domains import canonical_domain, is_social_url

log = logging.getLogger(__name__)

SEARCH_URL = "https://html.duckduckgo.com/html/?q={q}"

# Aggregators/directories that rank for any business name but are never its own site.
_DIRECTORY_DOMAINS = {
    "facebook.com", "instagram.com", "linkedin.com", "yelp.com", "foursquare.com",
    "tripadvisor.com", "yellowpages.com", "yellowpages.pk", "wikipedia.org", "wikidata.org",
    "daraz.pk", "olx.com.pk", "zameen.com", "rozee.pk", "indeed.com", "glassdoor.com",
    "pakbiz.com", "businesslist.pk", "pk.locanto.asia", "findpk.com", "cybo.com", "hipages.com",
    "mapquest.com", "trustpilot.com", "crunchbase.com", "zoominfo.com", "dnb.com", "apollo.io",
    "youtube.com", "tiktok.com", "twitter.com", "x.com", "pinterest.com", "amazon.com",
    "alibaba.com", "aliexpress.com", "justdial.com", "sulekha.com",
}

_STOPWORDS = {"the", "and", "of", "pvt", "ltd", "limited", "private", "company", "co", "store",
              "shop", "outlet", "pakistan", "karachi", "lahore", "islamabad", "rawalpindi"}


def _tokens(text: str) -> set[str]:
    return {t for t in normalize_name(text).split() if len(t) > 2 and t not in _STOPWORDS}


_GENERIC_TOKENS = {"electronics", "fashion", "furniture", "mobile", "mobiles", "garments", "traders",
                   "trading", "enterprises", "international", "brothers", "sons", "mart", "super",
                   "collection", "collections", "boutique", "clinic", "hospital", "school", "pharmacy"}


def name_matches(company_name: str, domain: str, title: str | None) -> bool:
    """True only when the company name is clearly reflected in the domain or page title."""
    toks = _tokens(company_name)
    if not toks:
        return False
    label = domain.split(".")[0]
    if "".join(sorted(toks)) in label or "".join(toks) in label:
        return True
    distinctive = [t for t in toks if t not in _GENERIC_TOKENS]
    longest = max(distinctive, key=len) if distinctive else None
    if longest and len(longest) >= 5 and longest in label:
        return True
    if title:
        overlap = toks & _tokens(title)
        needed = len(toks) - (1 if len(toks) > 2 else 0)
        if len(overlap) >= max(1, needed) and (not distinctive or overlap & set(distinctive)):
            return True
    return False


def parse_results(html: str) -> list[tuple[str, str]]:
    """Return (url, title) pairs from a DuckDuckGo HTML result page."""
    soup = BeautifulSoup(html, "lxml")
    results: list[tuple[str, str]] = []
    for a in soup.select("a.result__a"):
        href = a.get("href") or ""
        if href.startswith("//"):
            href = "https:" + href
        parsed = urlparse(href)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            if target:
                href = target
        title = a.get_text(" ", strip=True)
        if href:
            results.append((href, title))
    return results


class WebsiteFinder:
    def __init__(self, fetcher: HttpFetcher, settings: EngineSettings):
        self.fetcher = fetcher
        self.settings = settings

    async def find(self, company_name: str, city: str | None, country: str | None) -> str | None:
        if not self.settings.enable_search_fallback:
            return None
        query = " ".join(p for p in (company_name, city, country, "official website") if p)
        url = SEARCH_URL.format(q=quote_plus(query))
        result = await self.fetcher.get(url, delay=self.settings.search_delay_s, api=True)
        if not result.ok:
            log.debug("search: failed for %r (%s)", company_name, result.error or result.status_code)
            return None
        for href, title in parse_results(result.text)[:8]:
            domain = canonical_domain(href)
            if not domain or is_social_url(href) or domain in _DIRECTORY_DOMAINS:
                continue
            if name_matches(company_name, domain, title):
                return f"https://{domain}"
        return None
