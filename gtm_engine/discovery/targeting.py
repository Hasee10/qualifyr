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

log = logging.getLogger(__name__)

TAXONOMY_PATH = DEFAULTS_DIR / "discovery_taxonomy.yaml"


@dataclass
class DiscoveryTargets:
    osm_categories: list[str] = field(default_factory=list)
    overture_categories: list[str] = field(default_factory=list)
    sectors: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not self.osm_categories and not self.overture_categories


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
                                   llm: LLM | None = None, taxonomy: dict | None = None) -> DiscoveryTargets:
    """The categories to search for this offer. Deterministic sector-match, optionally widened
    by the LLM; both draw only from the taxonomy, so every category is valid. Returns empty
    when there is no offer to work from - the caller then falls back to its own behaviour."""
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
    log.info("derived discovery targets from offer: sectors=%s osm=%d overture=%d",
             targets.sectors, len(targets.osm_categories), len(targets.overture_categories))
    return targets
