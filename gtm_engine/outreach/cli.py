"""`gtm outreach ...` subcommands."""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from gtm_engine.config import CampaignConfig, load_settings
from gtm_engine.config.loader import PROJECT_ROOT
from gtm_engine.models import SequenceStatus
from gtm_engine.outreach.config import load_outreach_settings, load_templates
from gtm_engine.outreach.ledger import Ledger
from gtm_engine.outreach.reply_state import sync_replies
from gtm_engine.outreach.sender import make_sender
from gtm_engine.outreach.sequencer import due_leads, enqueue, send_due
from gtm_engine.outreach.templates import render
from gtm_engine.storage.database import Database


def ledger_path(campaign_id: str) -> Path:
    return PROJECT_ROOT / "leads" / campaign_id / "outreach_ledger.json"


def _campaign(db: Database, campaign_id: str) -> CampaignConfig:
    cfg = db.campaign_config(campaign_id)
    if not cfg:
        sys.exit(f"campaign '{campaign_id}' not found in the database; run it first")
    return CampaignConfig.model_validate(cfg)


def cmd_queue(args: argparse.Namespace) -> int:
    settings, osettings = load_settings(), load_outreach_settings()
    db = Database(settings.db_path)
    queued = enqueue(db, args.campaign_id, osettings, Ledger(ledger_path(args.campaign_id)))
    for l in queued:
        print(f"  queued  {l.company_name:<30} {l.contact_email}")
    print(f"{len(queued)} lead(s) queued")
    db.close()
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    settings, osettings, templates = load_settings(), load_outreach_settings(), load_templates()
    dry_run = args.dry_run or not osettings.credentials_present
    if dry_run:
        # A dry run must leave no trace: work on a throwaway copy of the DB and ledger so
        # the real ledger never claims an email was sent.
        scratch = settings.db_path.parent / "outbox"
        scratch.mkdir(parents=True, exist_ok=True)
        db_copy = scratch / "dryrun.sqlite"
        shutil.copyfile(settings.db_path, db_copy)
        db = Database(db_copy)
        ledger = Ledger(ledger_path(args.campaign_id))
        ledger.path = scratch / "dryrun_ledger.json"
        print("DRY RUN: no email will be sent; state changes go to data/outbox/ only")
    else:
        db = Database(settings.db_path)
        ledger = Ledger(ledger_path(args.campaign_id))
    campaign = _campaign(db, args.campaign_id)
    if not args.no_queue:
        enqueue(db, args.campaign_id, osettings, ledger)
    if not args.no_sync and not dry_run:
        r = sync_replies(db, args.campaign_id, osettings, ledger)
        print(f"reply sync: {r.replied} replied, {r.unsubscribed} unsubscribed, {r.bounced} bounced ({r.scanned} scanned)")
    sender = make_sender(osettings, settings.db_path.parent / "outbox", force_dry_run=dry_run)
    report = send_due(db, campaign, osettings, templates, sender, ledger, limit=args.limit,
                      ignore_window=args.ignore_window)
    for d in report.details:
        print("  " + d)
    print(f"sent {report.sent}, skipped {report.skipped}, failed {report.failed} via {sender.name}"
          + (f" — stopped: {report.stopped_reason}" if report.stopped_reason else ""))
    if hasattr(sender, "close"):
        sender.close()
    db.close()
    return 0 if report.failed == 0 else 1


def cmd_sync(args: argparse.Namespace) -> int:
    settings, osettings = load_settings(), load_outreach_settings()
    db = Database(settings.db_path)
    r = sync_replies(db, args.campaign_id, osettings, Ledger(ledger_path(args.campaign_id)))
    for d in r.details:
        print("  " + d)
    print(f"{r.replied} replied, {r.unsubscribed} unsubscribed, {r.bounced} bounced ({r.scanned} scanned)")
    db.close()
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    counts: dict[str, int] = {}
    for l in db.list_leads(args.campaign_id):
        counts[l.sequence_status.value] = counts.get(l.sequence_status.value, 0) + 1
    for k in [s.value for s in SequenceStatus]:
        if counts.get(k):
            print(f"  {k:<16} {counts[k]}")
    due = due_leads(db, args.campaign_id)
    print(f"due now: {len(due)}")
    for l in due[:20]:
        print(f"    {l.sequence_status.value:<16} {l.company_name:<30} {l.contact_email}")
    db.close()
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    n = 0
    for l in db.list_leads(args.campaign_id, outreach_ready=True):
        if args.all or l.lead_id in args.lead_ids:
            l.approved = not args.revoke
            db.update_lead(l)
            n += 1
    print(f"{'revoked' if args.revoke else 'approved'} {n} lead(s)")
    db.close()
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    settings, osettings, templates = load_settings(), load_outreach_settings(), load_templates()
    db = Database(settings.db_path)
    campaign = _campaign(db, args.campaign_id)
    leads = db.list_leads(args.campaign_id, outreach_ready=True)[: args.count]
    for l in leads:
        for step in ("email_1", "followup_1", "followup_2"):
            r = render(step, l, campaign, osettings, templates)
            print(f"===== {l.company_name} <{l.contact_email}> — {step}")
            print(f"Subject: {r.subject}\n\n{r.body}")
    db.close()
    return 0


def add_outreach_parser(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("outreach", help="queue, send and track the email sequence")
    s = p.add_subparsers(dest="outreach_command", required=True)

    q = s.add_parser("queue", help="move outreach-ready leads into the queue")
    q.add_argument("campaign_id")
    q.set_defaults(func=cmd_queue)

    sd = s.add_parser("send", help="sync replies, then send whatever is due (respects window + daily cap)")
    sd.add_argument("campaign_id")
    sd.add_argument("--limit", type=int, default=None, help="max emails this invocation")
    sd.add_argument("--dry-run", action="store_true", help="write .eml files to data/outbox instead of sending")
    sd.add_argument("--ignore-window", action="store_true", help="send outside business hours (testing)")
    sd.add_argument("--no-queue", action="store_true")
    sd.add_argument("--no-sync", action="store_true")
    sd.set_defaults(func=cmd_send)

    sy = s.add_parser("sync", help="check the inbox for replies, bounces and STOP requests")
    sy.add_argument("campaign_id")
    sy.set_defaults(func=cmd_sync)

    st = s.add_parser("status", help="sequence counts and what is due")
    st.add_argument("campaign_id")
    st.set_defaults(func=cmd_status)

    ap = s.add_parser("approve", help="mark leads approved (only matters when require_approval is true)")
    ap.add_argument("campaign_id")
    ap.add_argument("lead_ids", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--revoke", action="store_true")
    ap.set_defaults(func=cmd_approve)

    pv = s.add_parser("preview", help="render the 3 emails for the top leads without sending")
    pv.add_argument("campaign_id")
    pv.add_argument("--count", type=int, default=2)
    pv.set_defaults(func=cmd_preview)
