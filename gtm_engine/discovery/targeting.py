"""Offer -> discovery targets (E1).

The reframe's promise is that you describe what you sell and the engine figures out where to
look. Until now that translation was done by the *user*, in OSM/Overture tag syntax: a
campaign with a great offer but no hand-picked categories discovered nothing. This turns the
offer into the categories to search, so discovery is driven by the offer, not by the user's
knowledge of map tags.

How it stays honest: categories are never free-generated (an invented `shop=apparel` silently
matches nothing). The offer selects *sectors* from a curated taxonomy, and each sector expands
to categories known to be valid. The deterministic path matches sector keywords against the
offer; the optional LLM refines which sectors apply, choosing only from the same list."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from gtm_engine.config.loader import DEFAULTS_DIR
from gtm_engine.llm.client import LLM, parse_json_object
from gtm_engine.llm.tasks import generate_search_queries

log = logging.getLogger(__name__)

TAXONOMY_PATH = DEFAULTS_DIR / "discovery_taxonomy.yaml"


@dataclass
class DiscoveryTargets:
    osm_categories: list[str] = field(default_factory=list)
    overture_categories: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)
    search_queries: list[str] = field(default_factory=list)  # E2: queries for web-search discovery

    @property
    def empty(self) -> bool:
        return not self.osm_categories and not self.overture_categories


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        norm = (it or "").strip()
        low = norm.lower()
        if norm and low not in seen:
            seen.add(low)
            out.append(norm)
    return out


def _seed_queries(industries: list[str] | None, cities: list[str] | None,
                  sectors: list[str], taxonomy: dict, limit: int) -> list[str]:
    """Deterministic web-search queries from the campaign's industries (or, lacking those, the
    human term of each matched sector) crossed with up to two cities. Always something to search
    even without an LLM."""
    terms = list(industries or [])
    if not terms:
        for s in sectors:
            match = (taxonomy.get(s) or {}).get("match", [])
            if match:
                terms.append(match[0])
    places = (cities or [])[:2] or [None]
    queries: list[str] = []
    for term in terms[:4]:
        for city in places:
            queries.append(" ".join(p for p in [term, "companies", f"in {city}" if city else None] if p))
    return _dedupe(queries)[:limit]


def load_taxonomy(path: Path | None = None) -> dict:
    data = yaml.safe_load((path or TAXONOMY_PATH).read_text(encoding="utf-8")) or {}
    return data.get("sectors", {})


def _expand(sectors: list[str], taxonomy: dict) -> DiscoveryTargets:
    osm: list[str] = []
    overture: list[str] = []
    for key in sectors:
        spec = taxonomy.get(key) or {}
        for c in spec.get("osm", []):
            if c not in osm:
                osm.append(c)
        for c in spec.get("overture", []):
            if c not in overture:
                overture.append(c)
    return DiscoveryTargets(osm_categories=osm, overture_categories=overture, sectors=list(sectors))


def match_sectors(offer: str, industries: list[str] | None, taxonomy: dict) -> list[str]:
    """Sectors whose `match` terms appear in the offer or the campaign's industries. The broad
    `general_retail` fallback is only kept when nothing more specific matched, so a clothing
    campaign is not diluted with every storefront."""
    text = " ".join([offer or "", *(industries or [])]).lower()
    hits: list[str] = []
    for key, spec in taxonomy.items():
        if key == "general_retail":
            continue
        if any(term.lower() in text for term in spec.get("match", [])):
            hits.append(key)
    if not hits and "general_retail" in taxonomy:
        general = taxonomy["general_retail"]
        if any(term.lower() in text for term in general.get("match", [])):
            hits.append("general_retail")
    return hits


async def _llm_sectors(llm: LLM, offer: str, taxonomy: dict) -> list[str]:
    keys = list(taxonomy.keys())
    system = ("You select which business sectors would BUY the seller's offer, choosing ONLY "
              "from the provided sector list. Pick the sectors a plausible buyer belongs to, "
              "not the seller's own sector. Output a JSON array of sector keys, nothing else.")
    user = f"Seller offer: {offer!r}\n\nSectors to choose from:\n{keys}\n\nJSON array of keys."
    try:
        raw = await llm.complete(system, user, max_tokens=200)
    except Exception as exc:  # noqa: BLE001 - the LLM is optional
        log.debug("llm sector selection failed: %s", exc)
        return []
    obj = parse_json_object("{\"k\":" + raw + "}") if raw.strip().startswith("[") else None
    picked = obj.get("k") if obj else None
    if not isinstance(picked, list):
        # tolerate a bare array or comma/space separated keys
        picked = [k for k in keys if k in (raw or "")]
    return [k for k in picked if k in taxonomy]


async def derive_discovery_targets(offer: str, industries: list[str] | None = None,
                                   llm: LLM | None = None, taxonomy: dict | None = None,
                                   cities: list[str] | None = None, countries: list[str] | None = None,
                                   max_search_queries: int = 8) -> DiscoveryTargets:
    """The categories AND web-search queries to search for this offer. Categories come from the
    taxonomy (deterministic sector-match, optionally widened by the LLM), so every one is valid.
    Search queries (E2) are free text: deterministic seeds plus optional LLM queries, both aimed
    at buyers in the region. Returns empty when there is no offer - the caller then falls back."""
    if not (offer or "").strip():
        return DiscoveryTargets()
    taxonomy = taxonomy if taxonomy is not None else load_taxonomy()
    sectors = match_sectors(offer, industries, taxonomy)
    if llm is not None:
        for k in await _llm_sectors(llm, offer, taxonomy):
            if k not in sectors:
                sectors.append(k)
    if not sectors and "general_retail" in taxonomy:
        sectors = ["general_retail"]  # never leave an offer with nothing to search
    targets = _expand(sectors, taxonomy)

    region = ", ".join((cities or [])[:2] + (countries or [])[:1]) or None
    queries = _seed_queries(industries, cities, sectors, taxonomy, limit=max_search_queries)
    queries += await generate_search_queries(llm, offer, region)
    targets.search_queries = _dedupe(queries)[:max_search_queries]

    log.info("derived discovery targets from offer: sectors=%s osm=%d overture=%d queries=%d",
             targets.sectors, len(targets.osm_categories), len(targets.overture_categories),
             len(targets.search_queries))
    return targets
