"""OpenStreetMap discovery via the Overpass API. Free, no key, business-level data
with names, addresses and (sometimes) websites/phones."""

from __future__ import annotations

import json
import logging
from urllib.parse import urlencode
from typing import AsyncIterator

from gtm_engine.config.schema import CampaignConfig, EngineSettings
from gtm_engine.models import DiscoveredCompany
from gtm_engine.scraping.fetcher import HttpFetcher

log = logging.getLogger(__name__)

# OSM tag keys that may carry a website / email / phone, in preference order.
_WEBSITE_KEYS = ("website", "contact:website", "url", "contact:url", "brand:website")
_EMAIL_KEYS = ("email", "contact:email")
_PHONE_KEYS = ("phone", "contact:phone", "contact:mobile", "mobile")


def tag_filter(category: str) -> str:
    """'shop=clothes' -> '["shop"="clothes"]'; 'shop=*' or 'shop' -> '["shop"]'."""
    if "=" not in category:
        return f'["{category}"]'
    key, value = category.split("=", 1)
    if value in ("*", ""):
        return f'["{key}"]'
    return f'["{key}"="{value}"]'


def build_query(city: str, categories: list[str], timeout_s: int, area_name: str | None = None) -> str:
    area = area_name or city
    filters = "".join(f'  nwr{tag_filter(c)}["name"](area.searchArea);\n' for c in categories)
    return (
        f"[out:json][timeout:{timeout_s}];\n"
        f'area["name"="{area}"]["boundary"="administrative"]->.searchArea;\n'
        f"(\n{filters});\n"
        "out center tags;"
    )


def _first(tags: dict, keys: tuple[str, ...]) -> str | None:
    for k in keys:
        v = tags.get(k)
        if v:
            return v.split(";")[0].strip()
    return None


def _address(tags: dict) -> str | None:
    parts = [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb"),
             tags.get("addr:city"), tags.get("addr:postcode")]
    joined = ", ".join(p for p in parts if p)
    return joined or tags.get("addr:full")


def element_to_company(el: dict, city: str, country: str, category_label: str | None) -> DiscoveredCompany | None:
    tags = el.get("tags") or {}
    name = tags.get("name") or tags.get("brand")
    if not name:
        return None
    osm_type, osm_id = el.get("type"), el.get("id")
    category = None
    for key in ("shop", "amenity", "office", "craft", "industrial", "healthcare"):
        if key in tags:
            category = f"{key}={tags[key]}"
            break
    return DiscoveredCompany(
        name=name.strip(),
        website=_first(tags, _WEBSITE_KEYS),
        country=country,
        city=tags.get("addr:city") or city,
        address=_address(tags),
        phone=_first(tags, _PHONE_KEYS),
        email=_first(tags, _EMAIL_KEYS),
        category=category or category_label,
        source="osm",
        source_url=f"https://www.openstreetmap.org/{osm_type}/{osm_id}" if osm_type and osm_id else None,
        extra={"osm_tags": tags, "brand": tags.get("brand"), "lat": el.get("lat") or (el.get("center") or {}).get("lat"),
               "lon": el.get("lon") or (el.get("center") or {}).get("lon")},
    )


class OSMDiscovery:
    name = "osm"

    def __init__(self, fetcher: HttpFetcher, settings: EngineSettings):
        self.fetcher = fetcher
        self.settings = settings

    async def discover(self, campaign: CampaignConfig) -> AsyncIterator[DiscoveredCompany]:
        if not campaign.osm_categories:
            log.info("osm: campaign has no osm_categories; skipping")
            return
        country = campaign.geography.countries[0] if campaign.geography.countries else None
        for city in campaign.geography.cities:
            area = campaign.geography.osm_area_overrides.get(city)
            query = build_query(city, campaign.osm_categories, self.settings.overpass_timeout_s, area)
            elements = await self._run_query(query)
            log.info("osm: %s -> %d elements", city, len(elements))
            for el in elements:
                company = element_to_company(el, city, country or "", None)
                if company:
                    yield company

    async def _run_query(self, query: str) -> list[dict]:
        url = f"{self.settings.overpass_url}?{urlencode({'data': query})}"
        # Overpass is a shared public instance: one query at a time, generous spacing.
        result = await self.fetcher.get(url, delay=self.settings.per_host_delay_s * 2, api=True)
        if not result.ok:
            log.warning("osm: overpass request failed (%s %s)", result.status_code, result.error)
            return []
        try:
            payload = json.loads(result.text)
        except json.JSONDecodeError:
            log.warning("osm: non-JSON response from overpass")
            return []
        return payload.get("elements", [])
