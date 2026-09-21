"""Deterministic 0-100 lead score with human-readable reasons. Weights come from the
campaign config; this module only decides how each dimension earns its points."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from gtm_engine.config.schema import CampaignConfig
from gtm_engine.models import (
    Classification, CompanyQuality, CompanyType, Contact, DiscoveredCompany, EmailStatus,
    Priority, ScoreBreakdown, Signals,
)


@dataclass
class ScoreInputs:
    company: DiscoveredCompany
    classification: Classification
    quality: CompanyQuality
    contact: Contact
    signals: Signals


def _scale(points: float, max_points: int, default_max: int) -> int:
    """Rescale points designed against default_max onto the configured max."""
    return int(round(min(points, default_max) * max_points / default_max))


def _geo_points(company: DiscoveredCompany, campaign: CampaignConfig, reasons: list[str]) -> float:
    pts = 0.0
    countries = {c.lower() for c in campaign.geography.countries}
    cities = {c.lower() for c in campaign.geography.cities}
    if company.country and company.country.lower() in countries:
        pts += 10
        reasons.append(f"in target country ({company.country})")
    elif not countries:
        pts += 10
    if company.city and company.city.lower() in cities:
        pts += 10
        reasons.append(f"in target city ({company.city})")
    elif not cities:
        pts += 10
    elif company.city:
        reasons.append(f"city '{company.city}' not in campaign list")
    return pts


def score_lead(inputs: ScoreInputs, campaign: CampaignConfig) -> ScoreBreakdown:
    w = campaign.weights
    reasons: list[str] = []
    cls, q, contact, sig = inputs.classification, inputs.quality, inputs.contact, inputs.signals

    # --- ICP fit (default 50): geography 20, industry/buyer terms 20, company type 10
    icp = _geo_points(inputs.company, campaign, reasons)
    identity_hits = [h for h in cls.buyer_hits]
    if identity_hits:
        n = min(len(identity_hits), 4)
        icp += 5 * n
        reasons.append(f"{n} ICP term(s) matched: {', '.join(identity_hits[:4])}")
    if cls.company_type == CompanyType.BUYER:
        icp += 10
    elif cls.company_type == CompanyType.UNKNOWN:
        icp += 3
        reasons.append("company type unknown: insufficient evidence")
    icp_pts = _scale(icp, w.icp_fit, 50)

    # --- Company quality (default 15)
    cq = 0.0
    if q.reachable:
        cq += 5
    if q.https:
        cq += 2
    if q.has_contact_page:
        cq += 3
    if q.has_about_page:
        cq += 2
    if q.has_public_email or q.has_phone:
        cq += 3
    if q.reachable and q.mobile_friendly is False:
        cq -= 1
    if q.copyright_year and q.copyright_year <= datetime.now(timezone.utc).year - 3:
        cq -= 1
    cq = max(cq, 0)
    if not q.reachable:
        reasons.append("website unreachable")
    if q.notes:
        reasons.append("quality notes: " + "; ".join(q.notes[:3]))
    cq_pts = _scale(cq, w.company_quality, 15)

    # --- Buyer evidence (default 15): classification confidence + operating-business signals
    be = 0.0
    if cls.company_type == CompanyType.BUYER:
        be += 6 + 6 * cls.confidence
        if not cls.vendor_hits:
            be += 3
        else:
            reasons.append(f"minor vendor mentions present: {', '.join(cls.vendor_hits[:3])}")
    be_pts = _scale(be, w.buyer_evidence, 15)

    # --- Contact quality (default 10)
    cp = 0.0
    if contact.is_decision_maker and contact.name:
        cp += 5
        reasons.append(f"decision-maker found: {contact.name} ({contact.role})")
    email_pts = {EmailStatus.DELIVERABLE: 4, EmailStatus.MX_VALID: 3, EmailStatus.UNVERIFIED: 2, EmailStatus.GENERIC: 1.5}
    cp += email_pts.get(contact.email_status, 0)
    if contact.email_status == EmailStatus.DELIVERABLE:
        reasons.append(f"decision-maker mailbox confirmed ({contact.email_pattern or 'verified'})")
    elif contact.email_status == EmailStatus.GENERIC:
        reasons.append("only a generic business mailbox is public")
    if contact.phone_type == "mobile":
        cp += 1
        reasons.append("mobile number published (owner-level contact)")
    elif contact.email_status in (EmailStatus.NONE, EmailStatus.INVALID):
        reasons.append("no usable email")
    if contact.profile_url:
        cp += 2
    cp_pts = _scale(cp, w.contact_quality, 10)

    # --- Buying / pain signals (default 10)
    bs = 2.5 * len(sig.buying) + 1.5 * len(sig.pain)
    ecommerce_tech = [t for t in sig.technologies if t in ("shopify", "woocommerce", "magento")]
    if ecommerce_tech:
        bs += 2
        reasons.append("ecommerce platform detected: " + ", ".join(ecommerce_tech))
    if sig.news:
        reasons.append(f"in the news: {sig.news[0]['title'][:60]} ({sig.news[0]['source']})")
    if sig.domain_age_years is not None and sig.domain_age_years < 2:
        bs += 1.5
        reasons.append(f"young domain ({sig.domain_age_years} y): new or recently relaunched business")
    if sig.buying:
        reasons.append("buying signals: " + ", ".join(sig.buying))
    if sig.pain:
        reasons.append("pain signals: " + ", ".join(sig.pain))
    bs_pts = _scale(bs, w.buying_signals, 10)

    total = icp_pts + cq_pts + be_pts + cp_pts + bs_pts

    # --- Routing
    r = campaign.routing
    if cls.company_type == CompanyType.VENDOR:
        priority = Priority.REJECT
        reasons.insert(0, "classified as VENDOR: rejected regardless of score")
    elif total >= r.high_priority:
        priority = Priority.HIGH
    elif total >= r.qualified:
        priority = Priority.QUALIFIED
    elif total >= r.review:
        priority = Priority.REVIEW
    else:
        priority = Priority.REJECT
    if cls.company_type == CompanyType.UNKNOWN and priority in (Priority.HIGH, Priority.QUALIFIED):
        priority = Priority.REVIEW
        reasons.append("held for review: buyer status unconfirmed")
    if q.website_mismatch and priority in (Priority.HIGH, Priority.QUALIFIED):
        priority = Priority.REVIEW
        reasons.append("held for review: website may belong to a different company")

    return ScoreBreakdown(
        icp_fit=icp_pts, company_quality=cq_pts, buyer_evidence=be_pts,
        contact_quality=cp_pts, buying_signals=bs_pts, total=int(total),
        reasons=reasons, priority=priority,
    )


def is_outreach_ready(cls: Classification, score: ScoreBreakdown, contact: Contact, campaign: CampaignConfig) -> bool:
    """The only gate that lets a lead into the outreach queue."""
    return (
        cls.company_type == CompanyType.BUYER
        and score.total >= campaign.min_score
        and score.priority in (Priority.HIGH, Priority.QUALIFIED)
        and contact.email is not None
        and contact.email_status in (EmailStatus.MX_VALID, EmailStatus.GENERIC, EmailStatus.DELIVERABLE)
    )
