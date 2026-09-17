"""BUYER / VENDOR / UNKNOWN gate. Deterministic and explainable: every decision carries
the matched terms and where they matched. Nothing reaches contact discovery or
outreach without passing here."""

from __future__ import annotations

import re
from dataclasses import dataclass

from gtm_engine.config.schema import CampaignConfig, DefaultRules
from gtm_engine.models import Classification, CompanyType

# Weight of a hit by where it appears. Identity fields describe what the company *is*;
# body text describes what it talks about (and includes footers, vendor credits, ads).
W_IDENTITY = 3
W_BODY = 1
IDENTITY_CHARS = 800  # leading chars of about/home text treated as identity


@dataclass
class TextBundle:
    name: str
    title: str | None
    description: str | None
    about_text: str | None
    body_text: str
    category: str | None = None  # discovery category, e.g. "shop=clothes"

    @property
    def identity(self) -> str:
        parts = [self.name, self.title or "", self.description or "", (self.about_text or "")[:IDENTITY_CHARS]]
        return " ".join(parts).lower()

    @property
    def body(self) -> str:
        return self.body_text.lower()


def _find_terms(text: str, terms: list[str]) -> list[str]:
    hits: list[str] = []
    for term in terms:
        if not term:
            continue
        # Word-boundary match; multi-word terms match as a phrase.
        pattern = r"(?<![a-z0-9])" + re.escape(term.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, text):
            hits.append(term)
    return hits


class BuyerClassifier:
    def __init__(self, campaign: CampaignConfig, defaults: DefaultRules):
        allowed = set(campaign.allowed_vendor_keywords)
        self.vendor_terms = [t for t in dict.fromkeys(defaults.negative_keywords + campaign.negative_keywords)
                             if t not in allowed]
        self.vendor_phrases = [t for t in defaults.vendor_phrases if t not in allowed]
        self.buyer_terms = list(dict.fromkeys(campaign.buyer_keywords + campaign.target_industries))
        self.osm_categories = set(campaign.osm_categories)

    def classify(self, bundle: TextBundle) -> Classification:
        identity, body = bundle.identity, bundle.body
        reasons: list[str] = []

        vendor_name = _find_terms(bundle.name.lower(), self.vendor_terms)
        vendor_id = _find_terms(identity, self.vendor_terms)
        vendor_body = [t for t in _find_terms(body, self.vendor_terms) if t not in vendor_id]
        phrase_hits = _find_terms(body, self.vendor_phrases)
        buyer_id = _find_terms(identity, self.buyer_terms)
        buyer_body = [t for t in _find_terms(body, self.buyer_terms) if t not in buyer_id]

        vendor_score = W_IDENTITY * len(vendor_id) + W_BODY * len(vendor_body) + 0.5 * len(phrase_hits)
        buyer_score = W_IDENTITY * len(buyer_id) + W_BODY * min(len(buyer_body), 4)

        category_match = False
        if bundle.category:
            key = bundle.category.split("=")[0]
            category_match = bundle.category in self.osm_categories or f"{key}=*" in self.osm_categories
            if category_match:
                buyer_score += W_IDENTITY
                reasons.append(f"discovery category '{bundle.category}' matches campaign target")

        if vendor_name:
            reasons.append("vendor terms in company name: " + ", ".join(vendor_name))
        elif vendor_id:
            reasons.append("vendor terms in company identity: " + ", ".join(vendor_id))
        if vendor_body:
            reasons.append("vendor terms in page text: " + ", ".join(vendor_body[:6]))
        if len(phrase_hits) >= 2:
            reasons.append("sells-to-businesses phrasing: " + ", ".join(phrase_hits[:5]))
        if buyer_id:
            reasons.append("buyer terms in company identity: " + ", ".join(buyer_id))
        if buyer_body:
            reasons.append("buyer terms in page text: " + ", ".join(buyer_body[:6]))

        # --- decision ---------------------------------------------------------
        # The name says what the company is. "Retail Growth Consultancy" serves retailers;
        # it is not one, however often "retail" appears on its pages.
        if vendor_name:
            return Classification(company_type=CompanyType.VENDOR, confidence=0.9, reasons=reasons,
                                  buyer_hits=buyer_id + buyer_body, vendor_hits=vendor_id + vendor_body + phrase_hits)

        # A vendor term in the identity is decisive unless the identity is even more
        # clearly a buyer (e.g. "ABC Retail Consulting" is a vendor; "XYZ Store - IT
        # solutions for our customers" is ambiguous and falls to the score compare).
        if vendor_id and vendor_score >= buyer_score:
            conf = min(1.0, 0.6 + 0.1 * len(vendor_id))
            return Classification(company_type=CompanyType.VENDOR, confidence=conf, reasons=reasons,
                                  buyer_hits=buyer_id + buyer_body, vendor_hits=vendor_id + vendor_body + phrase_hits)

        # Body-only vendor evidence must be substantial before it outweighs buyer evidence.
        if not buyer_id and not category_match and (len(vendor_body) >= 3 or (vendor_body and len(phrase_hits) >= 3)):
            return Classification(company_type=CompanyType.VENDOR, confidence=0.55, reasons=reasons,
                                  buyer_hits=buyer_body, vendor_hits=vendor_body + phrase_hits)

        if buyer_id or category_match or len(buyer_body) >= 2:
            margin = buyer_score - vendor_score
            conf = max(0.5, min(1.0, 0.5 + margin / 10))
            if vendor_body or phrase_hits:
                reasons.append("buyer evidence outweighs weaker vendor mentions")
            return Classification(company_type=CompanyType.BUYER, confidence=round(conf, 2), reasons=reasons,
                                  buyer_hits=buyer_id + buyer_body, vendor_hits=vendor_body + phrase_hits)

        if not reasons:
            reasons.append("no buyer or vendor evidence found in available pages")
        return Classification(company_type=CompanyType.UNKNOWN, confidence=0.0, reasons=reasons,
                              buyer_hits=buyer_body, vendor_hits=vendor_body + phrase_hits)
