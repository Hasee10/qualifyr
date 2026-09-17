"""Queue + sequence state machine.

    not_queued -> queued -> email_1_sent -> followup_1_sent -> followup_2_sent (done)
                                 \\-> replied | bounced | unsubscribed | suppressed  (terminal)

Only leads that passed the outreach gate (outreach_ready) are ever queued, and the
ledger is consulted before every send so an address never receives a step twice."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from gtm_engine.config.schema import CampaignConfig
from gtm_engine.models import CompanyType, EmailStatus, Lead, SequenceStatus, utcnow
from gtm_engine.outreach.config import OutreachSettings, Templates
from gtm_engine.outreach.ledger import Ledger
from gtm_engine.outreach.sender import OutgoingEmail, Sender
from gtm_engine.outreach.templates import render
from gtm_engine.storage.database import Database

log = logging.getLogger(__name__)

ACTIVE = [SequenceStatus.QUEUED, SequenceStatus.EMAIL_1_SENT, SequenceStatus.FOLLOWUP_1_SENT]
TERMINAL = {SequenceStatus.REPLIED, SequenceStatus.BOUNCED, SequenceStatus.UNSUBSCRIBED,
            SequenceStatus.SUPPRESSED, SequenceStatus.FOLLOWUP_2_SENT, SequenceStatus.COMPLETED}

# status -> (step to send now, status after sending)
NEXT_STEP: dict[SequenceStatus, tuple[str, SequenceStatus]] = {
    SequenceStatus.QUEUED: ("email_1", SequenceStatus.EMAIL_1_SENT),
    SequenceStatus.EMAIL_1_SENT: ("followup_1", SequenceStatus.FOLLOWUP_1_SENT),
    SequenceStatus.FOLLOWUP_1_SENT: ("followup_2", SequenceStatus.FOLLOWUP_2_SENT),
}


@dataclass
class SendReport:
    sent: int = 0
    skipped: int = 0
    failed: int = 0
    stopped_reason: str | None = None
    details: list[str] = field(default_factory=list)


def in_send_window(now: datetime, settings: OutreachSettings) -> bool:
    local = now.astimezone(ZoneInfo(settings.timezone))
    if settings.skip_weekends and local.weekday() >= 5:
        return False
    return settings.send_window_start_hour <= local.hour < settings.send_window_end_hour


def eligible(lead: Lead, settings: OutreachSettings) -> tuple[bool, str]:
    if lead.company_type != CompanyType.BUYER:
        return False, "not a buyer"
    if not lead.outreach_ready:
        return False, "not outreach-ready"
    if not lead.contact_email or lead.email_status not in (EmailStatus.MX_VALID, EmailStatus.GENERIC):
        return False, "no validated email"
    if settings.require_approval and not lead.approved:
        return False, "awaiting approval"
    if lead.sequence_status != SequenceStatus.NOT_QUEUED:
        return False, f"already {lead.sequence_status.value}"
    return True, "ok"


def enqueue(db: Database, campaign_id: str, settings: OutreachSettings, ledger: Ledger) -> list[Lead]:
    queued: list[Lead] = []
    for lead in db.list_leads(campaign_id, outreach_ready=True):
        ok, why = eligible(lead, settings)
        if not ok:
            log.debug("skip %s: %s", lead.company_name, why)
            continue
        email = lead.contact_email
        if db.is_suppressed(lead.domain, email) or ledger.is_stopped(email):
            lead.sequence_status = SequenceStatus.SUPPRESSED
            db.update_lead(lead)
            continue
        if ledger.has_sent(email, "email_1"):
            # DB lost the state but the ledger remembers: rebuild from the ledger.
            _restore_from_ledger(lead, ledger, settings)
            db.update_lead(lead)
            continue
        lead.sequence_status = SequenceStatus.QUEUED
        lead.next_contact_at = utcnow()
        db.update_lead(lead)
        db.add_event(lead.lead_id, "queued")
        queued.append(lead)
    log.info("queued %d lead(s) for %s", len(queued), campaign_id)
    return queued


def _restore_from_ledger(lead: Lead, ledger: Ledger, settings: OutreachSettings) -> None:
    steps = ledger.steps_sent(lead.contact_email)
    order = ["email_1", "followup_1", "followup_2"]
    done = [s for s in order if s in steps]
    last = done[-1]
    lead.thread_message_id = steps["email_1"].get("message_id")
    lead.last_sent_at = datetime.fromisoformat(steps[last]["at"])
    lead.email_1_sent_at = datetime.fromisoformat(steps["email_1"]["at"])
    if "followup_1" in steps:
        lead.followup_1_at = datetime.fromisoformat(steps["followup_1"]["at"])
    if "followup_2" in steps:
        lead.followup_2_at = datetime.fromisoformat(steps["followup_2"]["at"])
        lead.sequence_status = SequenceStatus.FOLLOWUP_2_SENT
        return
    lead.sequence_status = SequenceStatus.FOLLOWUP_1_SENT if last == "followup_1" else SequenceStatus.EMAIL_1_SENT
    lead.next_contact_at = _next_contact(lead.sequence_status, lead.last_sent_at, settings)


def _next_contact(status: SequenceStatus, sent_at: datetime, settings: OutreachSettings) -> datetime | None:
    if status == SequenceStatus.EMAIL_1_SENT:
        return sent_at + timedelta(days=settings.followup_1_after_days)
    if status == SequenceStatus.FOLLOWUP_1_SENT:
        return sent_at + timedelta(days=settings.followup_2_after_days)
    return None


def due_leads(db: Database, campaign_id: str, now: datetime | None = None) -> list[Lead]:
    now = now or utcnow()
    out: list[Lead] = []
    for lead in db.leads_by_status(campaign_id, [s.value for s in ACTIVE]):
        if lead.next_contact_at is None or lead.next_contact_at <= now:
            out.append(lead)
    # Email 1 first (new conversations), then oldest follow-ups.
    out.sort(key=lambda l: (0 if l.sequence_status == SequenceStatus.QUEUED else 1, l.next_contact_at or now))
    return out


def stop_lead(db: Database, lead: Lead, status: SequenceStatus, reason: str, ledger: Ledger | None = None) -> None:
    lead.sequence_status = status
    lead.outreach_ready = False
    lead.next_contact_at = None
    if status == SequenceStatus.REPLIED:
        lead.reply_status = reason
    db.update_lead(lead)
    db.add_event(lead.lead_id, status.value, detail=reason)
    if status in (SequenceStatus.UNSUBSCRIBED, SequenceStatus.BOUNCED) and lead.contact_email:
        db.add_suppression(lead.contact_email, "email", reason)
        if ledger:
            ledger.record_stop(lead.contact_email, status.value)


def send_due(db: Database, campaign: CampaignConfig, settings: OutreachSettings, templates: Templates,
             sender: Sender, ledger: Ledger, *, limit: int | None = None, now: datetime | None = None,
             sleep=time.sleep, ignore_window: bool = False) -> SendReport:
    report = SendReport()
    now = now or utcnow()
    if not ignore_window and not in_send_window(now, settings):
        report.stopped_reason = "outside send window"
        return report

    day = now.strftime("%Y-%m-%d")
    already_today = max(db.events_today("sent", day), ledger.sent_on(day))
    budget = settings.daily_limit - already_today
    if limit is not None:
        budget = min(budget, limit)
    if budget <= 0:
        report.stopped_reason = f"daily limit reached ({already_today}/{settings.daily_limit})"
        return report

    consecutive_failures = 0
    for lead in due_leads(db, campaign.campaign_id, now):
        if report.sent >= budget:
            report.stopped_reason = "daily limit reached"
            break
        step, next_status = NEXT_STEP[lead.sequence_status]
        email = lead.contact_email
        if db.is_suppressed(lead.domain, email) or ledger.is_stopped(email):
            stop_lead(db, lead, SequenceStatus.SUPPRESSED, "suppressed before send", ledger)
            report.skipped += 1
            continue
        if ledger.has_sent(email, step):
            log.warning("%s already received %s per ledger; advancing without sending", email, step)
            _advance(db, lead, step, next_status, ledger.steps_sent(email)[step].get("message_id"), settings)
            report.skipped += 1
            continue

        rendered = render(step, lead, campaign, settings, templates)
        result = sender.send(OutgoingEmail(
            to=email, subject=rendered.subject, body=rendered.body,
            in_reply_to=lead.thread_message_id if step != "email_1" else None,
            lead_id=lead.lead_id, step=step,
        ))
        if not result.ok:
            report.failed += 1
            consecutive_failures += 1
            db.add_event(lead.lead_id, "send_failed", step=step, detail=result.error)
            report.details.append(f"{lead.company_name}: {result.error}")
            if result.error and result.error.startswith("recipient_refused"):
                stop_lead(db, lead, SequenceStatus.BOUNCED, result.error, ledger)
            if consecutive_failures >= 3:
                report.stopped_reason = "three consecutive send failures; check credentials/limits"
                break
            continue

        consecutive_failures = 0
        ledger.record_sent(email, step, result.message_id, lead.lead_id, now)
        _advance(db, lead, step, next_status, result.message_id, settings, now)
        db.add_event(lead.lead_id, "sent", step=step, detail=result.message_id)
        report.sent += 1
        report.details.append(f"{lead.company_name} <{email}>: {step} via {sender.name}")
        if report.sent < budget:
            sleep(settings.delay_between_sends_s)
    return report


def _advance(db: Database, lead: Lead, step: str, next_status: SequenceStatus, message_id: str | None,
             settings: OutreachSettings, now: datetime | None = None) -> None:
    now = now or utcnow()
    if step == "email_1":
        lead.email_1_sent_at = now
        lead.thread_message_id = message_id
    elif step == "followup_1":
        lead.followup_1_at = now
    else:
        lead.followup_2_at = now
    lead.last_sent_at = now
    lead.sequence_status = next_status
    lead.next_contact_at = _next_contact(lead.sequence_status, now, settings)
    db.update_lead(lead)
