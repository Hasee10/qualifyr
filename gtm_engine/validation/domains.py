"""Domain / URL canonicalization. Every dedupe decision runs through here."""

from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import tldextract

# Offline extractor: uses the bundled public-suffix snapshot, never fetches at runtime.
_extract = tldextract.TLDExtract(suffix_list_urls=(), fallback_to_snapshot=True)

# Hosted profile sites are not a company's own domain; a "website" pointing here is a
# social link, not a canonical domain.
SOCIAL_HOSTS = {
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "wa.me", "whatsapp.com", "pinterest.com",
    "daraz.pk", "olx.com.pk", "google.com", "goo.gl", "maps.app.goo.gl",
}

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")


def normalize_url(raw: str | None) -> str | None:
    """Return an absolute http(s) URL with a scheme, or None if it cannot be one."""
    if not raw:
        return None
    url = raw.strip()
    if not url or url.startswith(("mailto:", "tel:", "javascript:")):
        return None
    if "://" not in url:
        url = "https://" + url.lstrip("/")
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    host = parsed.netloc.lower()
    if "@" in host:
        return None
    path = parsed.path or "/"
    return urlunparse((parsed.scheme, host, path, "", parsed.query, ""))


def canonical_domain(raw: str | None) -> str | None:
    """'https://www.Shop.com.pk/about?x=1' -> 'shop.com.pk'. None for social hosts / junk."""
    url = normalize_url(raw)
    if not url:
        return None
    host = urlparse(url).netloc.split(":")[0]
    ext = _extract(host)
    if not ext.domain or not ext.suffix:
        return None
    domain = f"{ext.domain}.{ext.suffix}".lower()
    if domain in SOCIAL_HOSTS or not _DOMAIN_RE.match(domain):
        return None
    return domain


def is_social_url(raw: str | None) -> bool:
    url = normalize_url(raw)
    if not url:
        return False
    host = urlparse(url).netloc.split(":")[0]
    ext = _extract(host)
    return f"{ext.domain}.{ext.suffix}".lower() in SOCIAL_HOSTS


def company_key(domain: str | None, name: str, city: str | None) -> str:
    """Primary dedupe key: domain. Fallback: normalized name + city."""
    if domain:
        return domain
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"{slug}|{(city or '').lower().strip()}"
