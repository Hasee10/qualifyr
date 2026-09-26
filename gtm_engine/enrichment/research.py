"""Per-company research brief (P5).

A research engine's deliverable is not a row in a table — it is a short, factual account of
*why this company, and who to talk to*, that a human can read and act on. This assembles one
from what the pipeline already found: what the company is, the intent/buying signals that
survived the relevance gate, the decision-maker, and the qualification verdict.

Deterministic and grounded: every sentence is built from observed fields, nothing invented.
The LLM is never needed here — the point is a trustworthy summary, not prose."""

from __future__ import annotations

from gtm_engine.models import Classification, Contact, DiscoveredCompany, EmailStatus, Signals


def _sentence(parts: list[str]) -> str:
    return " ".join(p for p in parts if p).strip()


def build_research_brief(company: DiscoveredCompany, cls: Classification, contact: Contact,
                         signals: Signals, *, city: str | None = None,
                         industry: str | None = None, description: str | None = None) -> str:
    """A few grounded lines about the company, its signals and its decision-maker."""
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
        lines.append(who + ".")
    elif contact.email:
        lines.append(f"Contact: {contact.email} ({contact.email_status.value}); no named decision-maker found.")
    else:
        lines.append("No public contact found yet.")

    return "\n".join(lines)
