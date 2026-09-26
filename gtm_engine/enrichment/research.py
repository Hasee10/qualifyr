"""Per-company research brief (P5).

A research engine's deliverable is not a row in a table — it is a short, factual account of
*why this company, and who to talk to*, that a human can read and act on. This assembles one
from what the pipeline already found: what the company is, the intent/buying signals that
survived the relevance gate, the decision-maker, and the qualification verdict.

Deterministic and grounded: every sentence is built from observed fields, nothing invented.
The LLM is never needed here — the point is a trustworthy summary, not prose."""

from __future__ import annotations

from gtm_engine.models import Classification, CompanyQuality, Contact, DiscoveredCompany, EmailStatus, Signals


def _sentence(parts: list[str]) -> str:
    return " ".join(p for p in parts if p).strip()


def _web_presence(quality: CompanyQuality | None) -> str | None:
    """The Section-6 website activity/quality point, stated plainly — including the 'reachable
    but almost nothing public' case (e.g. a single-page site with no about/contact/email), which
    is itself a strong outreach signal and must not be hidden."""
    if quality is None:
        return None
    if quality.website_mismatch:
        return "Web presence: the site found did not appear to belong to this company, so its details were not used."
    if not quality.reachable:
        return "Web presence: no reachable website found."
    bits = ["single-page site" if quality.page_count <= 1 else f"{quality.page_count} pages",
            "HTTPS" if quality.https else "no HTTPS"]
    missing = [name for present, name in (
        (quality.has_about_page, "about"), (quality.has_contact_page, "contact")) if not present]
    if missing:
        bits.append("no " + "/".join(missing) + " page")
    if not (quality.has_public_email or quality.has_phone):
        bits.append("no public email or phone")
    if quality.mobile_friendly is False:
        bits.append("not mobile-friendly")
    if quality.copyright_year:
        bits.append(f"footer year {quality.copyright_year}")
    line = "Web presence: " + "; ".join(bits) + "."
    if quality.page_count <= 1 and not quality.has_about_page and not quality.has_contact_page \
            and not quality.has_public_email:
        line += " Limited public information available."
    return line


def build_research_brief(company: DiscoveredCompany, cls: Classification, contact: Contact,
                         signals: Signals, *, city: str | None = None,
                         industry: str | None = None, description: str | None = None,
                         quality: CompanyQuality | None = None) -> str:
    """A grounded per-company account covering the Section-6 research checklist: what the company
    is, its web presence, whether it plausibly needs the offer (intent), the buying signals, the
    technologies, and who to talk to — every line built from observed fields, nothing invented."""
    lines: list[str] = []

    where = ", ".join(x for x in (city or company.city, company.country) if x)
    what = industry or company.category
    head = _sentence([
        f"{company.name}",
        f"— {what}" if what else "",
        f"in {where}" if where else "",
        f". {description.strip().rstrip('.')}." if description else ".",
    ])
    lines.append(head)

    web = _web_presence(quality)
    if web:
        lines.append(web)

    # Whether it plausibly needs the offer — the intent verdict leads when the LLM judged it.
    if cls.intent_buyer is not None:
        verdict = "likely a buyer" if cls.intent_buyer else "no evident need for the offer"
        lines.append(f"Intent: {verdict} ({cls.intent_confidence:.0%})"
                     + (f" — {cls.intent_reason}" if cls.intent_reason else "") + ".")

    # Why it is (or is not yet) a buyer.
    if cls.company_type.value == "BUYER" and cls.reasons:
        lines.append("Buyer: " + cls.reasons[0] + ".")

    # Relevant intent/buying signals — the reason to reach out now.
    reasons: list[str] = []
    for s in (signals.intent or [])[:2]:
        rel = ", ".join(s.get("relevance", [])) if s.get("relevance") else ""
        reasons.append(f"{s.get('kind')} ({rel})" if rel else f"{s.get('kind')}: {s.get('text', '')[:60]}")
    if signals.job_openings:
        g = [j for j in signals.job_openings if j.get("growth_role")]
        reasons.append(f"hiring for {g[0]['title']}" if g else f"{len(signals.job_openings)} open role(s)")
    if signals.press_mentions:
        reasons.append(f"{signals.press_mentions[0]['kind'].replace('_', ' ')} in the press")
    if signals.news:
        reasons.append(f"recently in the news ({signals.news[0].get('source', '')})")
    if reasons:
        lines.append("Signals: " + "; ".join(reasons) + ".")

    if signals.technologies:
        lines.append("Tech: " + ", ".join(signals.technologies[:6]) + ".")

    # Who to talk to.
    if contact.name:
        who = _sentence([
            f"Decision-maker: {contact.name}",
            f"({contact.role})" if contact.role else "",
        ])
        if contact.email and contact.email_status == EmailStatus.DELIVERABLE:
            who += f", {contact.email} (confirmed)"
        elif contact.email:
            who += f", {contact.email} ({contact.email_status.value})"
        if contact.phone:
            who += f", {contact.phone}" + (f" ({contact.phone_type})" if contact.phone_type else "")
        if contact.profile_url and "/in/" in contact.profile_url:
            who += f", {contact.profile_url}"
        lines.append(who + ".")
    elif contact.email:
        lines.append(f"Contact: {contact.email} ({contact.email_status.value}); no named decision-maker found.")
    else:
        lines.append("No public contact found yet.")

    if company.source:
        lines.append(f"Source: {company.source}" + (f" ({company.source_url})" if company.source_url else "") + ".")

    return "\n".join(lines)
