"""Offer -> discovery targets (E1).

The reframe's promise is that you describe what you sell and the engine figures out where to
look. Until now that translation was done by the *user*, in OSM/Overture tag syntax: a
campaign with a great offer but no hand-picked categories discovered nothing. This turns the
offer into the categories to search, so discovery is driven by the offer, not by the user's
knowledge of map tags.

How it stays honest: categories come from a curated taxonomy when possible, or from a
validated niche fallback that checks against known-valid OSM tags. The deterministic path
matches sector keywords against the offer; the optional LLM refines which sectors apply.
When no sector matches, industries are mapped to valid OSM/Overture tags directly."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import get_close_matches
from pathlib import Path

import yaml

from gtm_engine.config.loader import DEFAULTS_DIR
from gtm_engine.llm.client import LLM, parse_json_object
from gtm_engine.llm.tasks import generate_search_queries

log = logging.getLogger(__name__)

TAXONOMY_PATH = DEFAULTS_DIR / "discovery_taxonomy.yaml"
VALID_OSM_TAGS_PATH = DEFAULTS_DIR / "valid_osm_tags.yaml"


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
                  sectors: list[str], taxonomy: dict, limit: int,
                  areas: list[str] | None = None) -> list[str]:
    """Deterministic web-search queries from the campaign's industries (or, lacking those, the
    human term of each matched sector) crossed with areas+cities. Always something to search
    even without an LLM."""
    terms = list(industries or [])
    if not terms:
        for s in sectors:
            if s == "_niche":
                continue
            match = (taxonomy.get(s) or {}).get("match", [])
            if match:
                terms.append(match[0])
    city_list = (cities or [])[:2]
    area_list = (areas or [])[:3]
    queries: list[str] = []
    for term in terms[:4]:
        if area_list and city_list:
            for area in area_list:
                for city in city_list[:1]:
                    queries.append(f"{term} {area} {city}")
        elif city_list:
            for city in city_list:
                queries.append(f"{term} in {city}")
        else:
            queries.append(f"{term} companies")
    return _dedupe(queries)[:limit]


def load_taxonomy(path: Path | None = None) -> dict:
    data = yaml.safe_load((path or TAXONOMY_PATH).read_text(encoding="utf-8")) or {}
    return data.get("sectors", {})


_VALID_OSM_CACHE: dict[str, set[str]] | None = None


def load_valid_osm_tags(path: Path | None = None) -> dict[str, set[str]]:
    global _VALID_OSM_CACHE  # noqa: PLW0603
    if _VALID_OSM_CACHE is not None:
        return _VALID_OSM_CACHE
    try:
        data = yaml.safe_load((path or VALID_OSM_TAGS_PATH).read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        log.warning("valid_osm_tags.yaml not found at %s", path or VALID_OSM_TAGS_PATH)
        return {}
    result = {k: set(v) for k, v in data.items() if isinstance(v, list)}
    _VALID_OSM_CACHE = result
    return result


_INDUSTRY_SYNONYMS: dict[str, list[str]] = {
    "newspaper": ["newspaper", "newsagent"],
    "media": ["newspaper", "newsagent"],
    "law": ["lawyer"],
    "legal": ["lawyer"],
    "attorney": ["lawyer"],
    "travel": ["travel_agency", "travel_agent"],
    "watch": ["watches", "watchmaker", "clockmaker"],
    "tailor": ["tailor", "dressmaker"],
    "printing": ["printer", "copyshop"],
    "print": ["printer", "copyshop"],
    "flower": ["florist"],
    "pet": ["pet", "pet_grooming", "veterinary"],
    "photo": ["photo", "photographer"],
    "barber": ["hairdresser"],
    "hair": ["hairdresser"],
    "laundry": ["laundry", "dry_cleaning"],
    "plumber": ["plumber"],
    "electrician": ["electrician"],
    "carpenter": ["carpenter", "cabinet_maker"],
    "mechanic": ["car_repair"],
    "dentist": ["dentist"],
    "doctor": ["doctors", "doctor", "clinic"],
    "hospital": ["hospital"],
    "school": ["school"],
    "gym": ["fitness_centre"],
    "fitness": ["fitness_centre"],
    "hotel": ["hotel"],
    "motel": ["motel"],
    "bank": ["bank"],
    "insurance": ["insurance"],
    "real estate": ["estate_agent"],
    "property": ["estate_agent", "property_management"],
    "accountant": ["accountant"],
    "architect": ["architect"],
    "courier": ["courier"],
    "locksmith": ["locksmith"],
}


def _niche_fallback(industries: list[str], valid_tags: dict[str, set[str]]) -> DiscoveryTargets:
    """Construct valid OSM/Overture categories from raw industry terms when no taxonomy sector
    matches. Uses synonym lookup, fuzzy matching against valid tags, and heuristic key probing."""
    osm: list[str] = []
    overture: list[str] = []
    all_values = []
    for key, vals in valid_tags.items():
        for v in vals:
            all_values.append((key, v))

    for industry in industries[:5]:
        term = industry.lower().strip()
        found_osm: list[str] = []

        words_to_try = [term] + term.split()
        for w in words_to_try:
            synonyms = _INDUSTRY_SYNONYMS.get(w, [])
            for syn in synonyms:
                for key, vals in valid_tags.items():
                    if syn in vals and f"{key}={syn}" not in found_osm:
                        found_osm.append(f"{key}={syn}")

        if not found_osm:
            for w in words_to_try:
                for key, vals in valid_tags.items():
                    if w in vals and f"{key}={w}" not in found_osm:
                        found_osm.append(f"{key}={w}")

        if not found_osm:
            for w in words_to_try:
                singular = w.rstrip("s") if w.endswith("s") and len(w) > 3 else w
                for key, vals in valid_tags.items():
                    if singular in vals and f"{key}={singular}" not in found_osm:
                        found_osm.append(f"{key}={singular}")

        if not found_osm:
            val_list = [v for _, v in all_values]
            close = get_close_matches(term, val_list, n=3, cutoff=0.75)
            for match in close:
                for key, vals in valid_tags.items():
                    if match in vals and f"{key}={match}" not in found_osm:
                        found_osm.append(f"{key}={match}")

        for tag in found_osm[:5]:
            if tag not in osm:
                osm.append(tag)

        overture.append(term)
        if term != term.rstrip("s"):
            overture.append(term.rstrip("s"))

    if not osm and not overture:
        return DiscoveryTargets()
    return DiscoveryTargets(
        osm_categories=osm,
        overture_categories=_dedupe(overture),
        sectors=["_niche"],
    )


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


async def _llm_discovery_categories(llm: LLM, industries: list[str],
                                     valid_tags: dict[str, set[str]]) -> DiscoveryTargets:
    """Ask the LLM to suggest OSM/Overture categories for niche industries, validated against
    the known-valid tag list. Returns empty on failure (deterministic niche fallback already ran)."""
    tag_ref = {k: sorted(v)[:30] for k, v in valid_tags.items()}
    system = (
        "You suggest OSM map tags and Overture category substrings for discovering businesses. "
        "Output a JSON object: {\"osm\": [\"key=value\", ...], \"overture\": [\"substring\", ...]}. "
        "OSM tags MUST be from the valid list provided. Overture categories are free substrings."
    )
    user = (
        f"Find businesses of type: {industries}\n\n"
        f"Valid OSM tags (key: [values]):\n{tag_ref}\n\n"
        "Suggest OSM tags and Overture substrings for these business types. JSON only."
    )
    try:
        raw = await llm.complete(system, user, max_tokens=400)
    except Exception as exc:  # noqa: BLE001
        log.debug("llm discovery categories failed: %s", exc)
        return DiscoveryTargets()
    obj = parse_json_object(raw)
    if not obj:
        return DiscoveryTargets()
    osm = []
    for tag in (obj.get("osm") or []):
        if "=" not in str(tag):
            continue
        key, val = str(tag).split("=", 1)
        if key in valid_tags and val in valid_tags[key] and tag not in osm:
            osm.append(tag)
    overture = [str(c).strip().lower() for c in (obj.get("overture") or []) if c]
    return DiscoveryTargets(osm_categories=osm, overture_categories=overture, sectors=["_niche"])


async def derive_discovery_targets(offer: str, industries: list[str] | None = None,
                                   llm: LLM | None = None, taxonomy: dict | None = None,
                                   cities: list[str] | None = None, countries: list[str] | None = None,
                                   areas: list[str] | None = None,
                                   max_search_queries: int = 8) -> DiscoveryTargets:
    """The categories AND web-search queries to search for this offer. Categories come from the
    taxonomy when possible, or from a validated niche fallback / LLM suggestions for industries
    outside the 16 taxonomy sectors. Returns empty when there is no offer."""
    if not (offer or "").strip():
        return DiscoveryTargets()
    taxonomy = taxonomy if taxonomy is not None else load_taxonomy()
    sectors = match_sectors(offer, industries, taxonomy)
    if llm is not None:
        for k in await _llm_sectors(llm, offer, taxonomy):
            if k not in sectors:
                sectors.append(k)

    if not sectors and industries:
        valid_tags = load_valid_osm_tags()
        targets = _niche_fallback(industries, valid_tags)
        if llm is not None and valid_tags:
            llm_cats = await _llm_discovery_categories(llm, industries, valid_tags)
            for tag in llm_cats.osm_categories:
                if tag not in targets.osm_categories:
                    targets.osm_categories.append(tag)
            for cat in llm_cats.overture_categories:
                if cat not in targets.overture_categories:
                    targets.overture_categories.append(cat)
        if not targets.empty:
            log.info("niche fallback for industries %s: osm=%s overture=%s",
                     industries, targets.osm_categories, targets.overture_categories)
        else:
            targets = _expand(["general_retail"], taxonomy) if "general_retail" in taxonomy else DiscoveryTargets()
            targets.sectors = ["general_retail"]
    elif not sectors and "general_retail" in taxonomy:
        targets = _expand(["general_retail"], taxonomy)
        targets.sectors = ["general_retail"]
    else:
        targets = _expand(sectors, taxonomy)

    region = ", ".join((cities or [])[:2] + (countries or [])[:1]) or None
    queries = _seed_queries(industries, cities, targets.sectors, taxonomy,
                            limit=max_search_queries, areas=areas)
    queries += await generate_search_queries(llm, offer, region)
    targets.search_queries = _dedupe(queries)[:max_search_queries]

    log.info("derived discovery targets from offer: sectors=%s osm=%d overture=%d queries=%d",
             targets.sectors, len(targets.osm_categories), len(targets.overture_categories),
             len(targets.search_queries))
    return targets
