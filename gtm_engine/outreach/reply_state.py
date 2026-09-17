"""Reply, bounce and unsubscribe detection over IMAP (Gmail). Runs before every send
batch so a lead who answered yesterday never gets today's follow-up."""

from __future__ import annotations

import email
import imaplib
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from email.header import decode_header, make_header
from email.utils import parseaddr

from gtm_engine.models import Lead, SequenceStatus
from gtm_engine.outreach.config import OutreachSettings
from gtm_engine.outreach.ledger import Ledger
from gtm_engine.outreach.sequencer import ACTIVE, stop_lead
from gtm_engine.storage.database import Database

log = logging.getLogger(__name__)

_STOP_RE = re.compile(r"\b(stop|unsubscribe|remove me|opt[ -]?out|don'?t (email|contact) me)\b", re.I)
_BOUNCE_SENDERS = ("mailer-daemon", "postmaster", "mail delivery", "delivery status")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


@dataclass
class InboundMessage:
    from_addr: str
    subject: str
    body: str
    in_reply_to: str | None = None
    references: str = ""


@dataclass
class SyncReport:
    replied: int = 0
    unsubscribed: int = 0
    bounced: int = 0
    scanned: int = 0
    details: list[str] = field(default_factory=list)


def _decode(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:  # noqa: BLE001 - malformed headers are common in bounces
        return value


def _text_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        return ""
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")


def parse_message(raw: bytes) -> InboundMessage:
    msg = email.message_from_bytes(raw)
    return InboundMessage(
        from_addr=parseaddr(_decode(msg.get("From")))[1].lower(),
        subject=_decode(msg.get("Subject")),
        body=_text_body(msg)[:5000],
        in_reply_to=(msg.get("In-Reply-To") or "").strip() or None,
        references=msg.get("References") or "",
    )


def fetch_recent(settings: OutreachSettings, since_days: int = 14) -> list[InboundMessage]:
    if not settings.credentials_present:
        log.warning("no credentials: skipping reply sync")
        return []
    since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
    out: list[InboundMessage] = []
    with imaplib.IMAP4_SSL(settings.imap_host) as conn:
        conn.login(settings.smtp_user, settings.smtp_password)
        conn.select("INBOX", readonly=True)
        status, data = conn.search(None, f'(SINCE "{since}")')
        if status != "OK":
            return out
        for num in data[0].split():
            status, parts = conn.fetch(num, "(RFC822)")
            if status == "OK" and parts and isinstance(parts[0], tuple):
                out.append(parse_message(parts[0][1]))
    return out


def apply_inbound(db: Database, campaign_id: str, messages: list[InboundMessage],
                  ledger: Ledger | None = None) -> SyncReport:
    """Match inbound mail to active leads by sender address or by thread id."""
    report = SyncReport(scanned=len(messages))
    active: list[Lead] = db.leads_by_status(campaign_id, [s.value for s in ACTIVE])
    by_email = {l.contact_email.lower(): l for l in active if l.contact_email}
    by_thread = {l.thread_message_id: l for l in active if l.thread_message_id}

    for m in messages:
        lead = by_email.get(m.from_addr)
        if lead is None and m.in_reply_to:
            lead = by_thread.get(m.in_reply_to)
        if lead is None:
            for mid in by_thread:
                if mid in m.references:
                    lead = by_thread[mid]
                    break

        # Bounces come from the mail system, not the lead: find our lead's address inside.
        if lead is None and any(s in m.from_addr or s in m.subject.lower() for s in _BOUNCE_SENDERS):
            for addr in _EMAIL_RE.findall(m.body):
                if addr.lower() in by_email:
                    lead = by_email[addr.lower()]
                    stop_lead(db, lead, SequenceStatus.BOUNCED, "bounce notification", ledger)
                    report.bounced += 1
                    report.details.append(f"{lead.company_name}: bounced")
                    break
            continue
        if lead is None:
            continue

        text = f"{m.subject}\n{m.body[:600]}"
        if _STOP_RE.search(text):
            stop_lead(db, lead, SequenceStatus.UNSUBSCRIBED, "asked to stop", ledger)
            report.unsubscribed += 1
            report.details.append(f"{lead.company_name}: unsubscribed")
        else:
            stop_lead(db, lead, SequenceStatus.REPLIED, f"replied: {m.subject[:80]}", ledger)
            report.replied += 1
            report.details.append(f"{lead.company_name}: replied")
        # A lead stops once; drop it from further matching in this batch.
        by_email.pop(lead.contact_email.lower(), None)
        if lead.thread_message_id:
            by_thread.pop(lead.thread_message_id, None)
    return report


def sync_replies(db: Database, campaign_id: str, settings: OutreachSettings, ledger: Ledger | None = None) -> SyncReport:
    return apply_inbound(db, campaign_id, fetch_recent(settings), ledger)


def verify_sent(settings: OutreachSettings, ledger: Ledger, folder: str = '"[Gmail]/Sent Mail"') -> list[tuple[str, str, bool]]:
    """Confirm each ledger Message-ID exists in the mailbox's Sent folder.
    Returns (email, step, found)."""
    results: list[tuple[str, str, bool]] = []
    if not settings.credentials_present:
        return results
    with imaplib.IMAP4_SSL(settings.imap_host) as conn:
        conn.login(settings.smtp_user, settings.smtp_password)
        status, _ = conn.select(folder, readonly=True)
        if status != "OK":
            raise RuntimeError(f"cannot open {folder}")
        for addr, steps in ledger.data["sent"].items():
            for step, rec in steps.items():
                mid = rec.get("message_id")
                if not mid:
                    results.append((addr, step, False))
                    continue
                st, data = conn.search(None, "HEADER", "Message-ID", mid)
                results.append((addr, step, st == "OK" and bool(data and data[0])))
    return results
