"""Entity resolution across discovery sources: merge the same real company when it is
found under different name strings by different sources (e.g. an Overture POI and a GLEIF
LEI record for the same firm). Builds on `dedupe_companies` (domain / name+city), which stays
the primary pass for map-sourced data that carries no registry identifiers at all.

Match tiers, strongest first: LEI exact -> registration number exact (country-scoped) ->
domain exact -> normalized legal name + country fuzzy match. Registry sources write their
identifiers into stable `extra` keys: `extra["lei"]`, `extra["registration_number"]`.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

from gtm_engine.models import DiscoveredCompany
from gtm_engine.validation.dedupe import _merge, dedupe_companies

# Wider than dedupe.normalize_name's suffix list: also strips suffixes used by non-Pakistani
# jurisdictions (GLEIF/Companies House/EDGAR/Wikidata records), so e.g. SECP's "XYZ (PRIVATE)
# LIMITED" and GLEIF's "XYZ Pvt Ltd" normalize to the same string.
_WIDE_LEGAL_SUFFIX_RE = re.compile(
    r"\b(pvt\.?|private|ltd\.?|limited|llc|inc\.?|incorporated|co\.?|company|corp\.?|"
    r"corporation|smc-pvt|plc|gmbh|ag|s\.?a\.?|nv|bv|oy|ab|as|spa|srl|sarl|kk|"
    r"\(pvt\)|\(private\)|holdings?|group)\b",
    re.IGNORECASE,
)

FUZZY_NAME_THRESHOLD = 0.88


def normalize_legal_name(name: str) -> str:
    n = _WIDE_LEGAL_SUFFIX_RE.sub(" ", name.lower())
    n = re.sub(r"[^a-z0-9]+", " ", n)
    return " ".join(n.split())


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def resolve_entities(companies: Iterable[DiscoveredCompany]) -> list[DiscoveredCompany]:
    base = dedupe_companies(companies)
    if len(base) <= 1:
        return base

    merged: list[DiscoveredCompany] = []
    lei_index: dict[str, int] = {}
    regnum_index: dict[tuple[str, str], int] = {}
    domain_index: dict[str, int] = {}

    for c in base:
        lei = (c.extra or {}).get("lei")
        regnum = (c.extra or {}).get("registration_number")
        country = (c.country or "").strip().lower()
        domain = c.domain

        target_idx = None
        if lei and lei in lei_index:
            target_idx = lei_index[lei]
        elif regnum and (country, regnum) in regnum_index:
            target_idx = regnum_index[(country, regnum)]
        elif domain and domain in domain_index:
            target_idx = domain_index[domain]

        if target_idx is not None:
            merged[target_idx] = _merge(merged[target_idx], c)
            idx = target_idx
        else:
            merged.append(c)
            idx = len(merged) - 1

        if lei:
            lei_index.setdefault(lei, idx)
        if regnum:
            regnum_index.setdefault((country, regnum), idx)
        if domain:
            domain_index.setdefault(domain, idx)

    return _fuzzy_merge_by_name(merged)


def _fuzzy_merge_by_name(companies: list[DiscoveredCompany]) -> list[DiscoveredCompany]:
    """Last-resort pass for records with no shared identifier at all (e.g. an SECP record
    and a Wikidata record for the same firm, neither carrying the other's registry ID).
    Country-scoped on purpose: never merge across different countries on name alone."""
    out: list[DiscoveredCompany] = []
    for c in companies:
        c_norm = normalize_legal_name(c.name)
        c_country = (c.country or "").strip().lower()
        match_idx = None
        if c_norm:
            for idx, existing in enumerate(out):
                if (existing.country or "").strip().lower() != c_country:
                    continue
                if _name_similarity(c_norm, normalize_legal_name(existing.name)) >= FUZZY_NAME_THRESHOLD:
                    match_idx = idx
                    break
        if match_idx is None:
            out.append(c)
        else:
            out[match_idx] = _merge(out[match_idx], c)
    return out
