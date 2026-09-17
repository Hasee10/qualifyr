"""Pick the most relevant decision-maker from public company pages. Only names and
roles the company itself publishes; nothing is guessed."""

from __future__ import annotations

from gtm_engine.config.schema import CampaignConfig, DefaultRules
from gtm_engine.models import Contact, EmailStatus
from gtm_engine.scraping.site_crawler import SiteSnapshot
from gtm_engine.validation.emails import is_generic_mailbox


def role_rank(role: str, campaign: CampaignConfig, defaults: DefaultRules) -> int:
    """Higher is better. -1 means the role is on the sell side and must be dropped."""
    r = role.lower()
    if any(b in r for b in defaults.role_blacklist):
        return -1
    score = 0
    for i, target in enumerate(campaign.target_roles):
        if target and target in r:
            score = max(score, 100 - i)  # campaign order expresses preference
    for i, allowed in enumerate(defaults.buyer_role_whitelist):
        if allowed in r:
            score = max(score, 50 - min(i, 40))
    return score


def _match_personal_email(name: str, emails: list[str], generic: list[str]) -> str | None:
    """first.last@ / flast@ / first@ patterns against public emails found on the site."""
    parts = [p for p in name.lower().replace(".", " ").split() if p.isalpha()]
    if not parts:
        return None
    first, last = parts[0], parts[-1]
    candidates = {f"{first}.{last}", f"{first}{last}", f"{first[0]}{last}", f"{first}_{last}", first, f"{first}.{last[0]}"}
    for email in emails:
        local = email.split("@", 1)[0]
        if local in candidates and not is_generic_mailbox(email, generic):
            return email
    return None


def choose_contact(snapshot: SiteSnapshot, campaign: CampaignConfig, defaults: DefaultRules) -> Contact:
    """Return the best contact. If no named decision-maker is public, fall back to the
    company's business mailbox so the lead stays actionable (flagged as generic)."""
    emails = snapshot.emails
    best: tuple[int, str, str] | None = None
    for name, role in snapshot.team:
        rank = role_rank(role, campaign, defaults)
        if rank <= 0:
            continue
        if best is None or rank > best[0]:
            best = (rank, name, role)

    social = snapshot.social
    profile = social.get("linkedin")
    source_url = snapshot.pages["team"].url if "team" in snapshot.pages else (
        snapshot.pages["about"].url if "about" in snapshot.pages else snapshot.final_url)

    if best:
        _, name, role = best
        personal = _match_personal_email(name, emails, defaults.generic_email_prefixes)
        fallback = next((e for e in emails), None)
        return Contact(
            name=name, role=role, email=personal or fallback,
            email_status=EmailStatus.UNVERIFIED if (personal or fallback) else EmailStatus.NONE,
            phone=snapshot.phones[0] if snapshot.phones else None,
            profile_url=profile, source_url=source_url, is_decision_maker=True,
            evidence=f"'{name}' listed as '{role}' on {source_url}",
        )

    business_email = next((e for e in emails), None)
    return Contact(
        name=None, role=None, email=business_email,
        email_status=EmailStatus.UNVERIFIED if business_email else EmailStatus.NONE,
        phone=snapshot.phones[0] if snapshot.phones else None,
        profile_url=profile, source_url=source_url, is_decision_maker=False,
        evidence="no named decision-maker published; business mailbox only" if business_email
                 else "no public contact found",
    )
