"""FastAPI backend for the web UI. No auth (single operator, local). Every send goes
through the human-approval queue: preview -> edit -> approve -> send."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from gtm_engine import __version__
from gtm_engine.config import CampaignConfig, load_campaign, load_defaults, load_settings
from gtm_engine.config.loader import CONFIG_DIR
from gtm_engine.export.csv_export import export_path, write_csv
from gtm_engine.models import CompanyType, SequenceStatus
from gtm_engine.outreach.cli import ledger_path
from gtm_engine.outreach.config import load_outreach_settings, load_templates
from gtm_engine.outreach.ledger import Ledger
from gtm_engine.outreach.reply_state import sync_replies
from gtm_engine.outreach.sender import make_sender
from gtm_engine.outreach.sequencer import ACTIVE, enqueue, prepare_drafts, send_due, stop_lead
from gtm_engine.outreach.templates import render
from gtm_engine.pipeline import Pipeline
from gtm_engine.scraping.fetcher import HttpFetcher
from gtm_engine.storage.database import Database

log = logging.getLogger(__name__)
app = FastAPI(title="GTM Lead Engine", version=__version__)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"], allow_headers=["*"],
)

_settings = load_settings()
_defaults = load_defaults()
_runs: dict[str, dict] = {}          # campaign_id -> live progress of the current/last run
CAMPAIGN_DIR = CONFIG_DIR / "campaigns"


def _db() -> Database:
    return Database(_settings.db_path)


def _campaign_files() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for path in sorted(CAMPAIGN_DIR.glob("*.yaml")):
        try:
            out[load_campaign(path).campaign_id] = path
        except Exception as exc:  # noqa: BLE001 - a broken YAML must not hide the others
            log.warning("skipping %s: %s", path.name, exc)
    return out


def _campaign(campaign_id: str) -> CampaignConfig:
    path = _campaign_files().get(campaign_id)
    if path:
        return load_campaign(path)
    db = _db()
    cfg = db.campaign_config(campaign_id)
    db.close()
    if not cfg:
        raise HTTPException(404, f"campaign '{campaign_id}' not found")
    return CampaignConfig.model_validate(cfg)


# -- health / campaigns -------------------------------------------------------------

@app.get("/health")
def health() -> dict:
    o = load_outreach_settings()
    return {"status": "ok", "version": __version__, "smtp_configured": o.credentials_present,
            "require_approval": o.require_approval}


@app.get("/campaigns")
def campaigns() -> list[dict]:
    db = _db()
    out = []
    for cid, path in _campaign_files().items():
        c = load_campaign(path)
        leads = db.list_leads(cid)
        buyers = [l for l in leads if l.company_type == CompanyType.BUYER]
        out.append({
            "campaign_id": cid, "name": c.name, "offer": c.offer, "file": path.name,
            "cities": c.geography.cities, "countries": c.geography.countries,
            "min_score": c.min_score, "max_companies": c.max_companies,
            "leads": len(leads), "buyers": len(buyers),
            "qualified": sum(1 for l in buyers if l.total_score >= c.min_score),
            "outreach_ready": sum(1 for l in leads if l.outreach_ready),
            "last_run": (db.list_runs(cid) or [None])[0],
            "live": _runs.get(cid),
        })
    db.close()
    return out


@app.get("/campaigns/{campaign_id}")
def campaign_detail(campaign_id: str) -> dict:
    return _campaign(campaign_id).model_dump(mode="json")


class RunRequest(BaseModel):
    max_companies: int | None = None


@app.post("/campaigns/{campaign_id}/run")
async def run_campaign(campaign_id: str, req: RunRequest) -> dict:
    campaign = _campaign(campaign_id)
    if req.max_companies:
        campaign.max_companies = req.max_companies
    if _runs.get(campaign_id, {}).get("stage") not in (None, "completed", "failed"):
        raise HTTPException(409, "a run is already in progress for this campaign")
    ticket = {"run_id": None, "stage": "starting", "done": 0, "total": 0, "message": "", "stats": None}
    _runs[campaign_id] = ticket

    async def job() -> None:
        db = _db()
        try:
            async with HttpFetcher(_settings) as fetcher:
                def on_progress(stage: str, done: int, total: int, message: str) -> None:
                    ticket.update(stage=stage, done=done, total=total, message=message)
                result = await Pipeline(_settings, _defaults, db, fetcher).run(campaign, progress=on_progress)
                ticket.update(run_id=result.run_id, stage="completed", message="done", stats=result.stats.as_dict())
        except Exception as exc:  # noqa: BLE001
            ticket.update(stage="failed", message=str(exc))
            log.exception("run failed")
        finally:
            db.close()

    asyncio.create_task(job())
    return ticket


@app.get("/campaigns/{campaign_id}/progress")
def progress(campaign_id: str) -> dict:
    return _runs.get(campaign_id) or {"stage": "idle"}


@app.get("/campaigns/{campaign_id}/stats")
def stats(campaign_id: str) -> dict:
    campaign = _campaign(campaign_id)
    db = _db()
    leads = db.list_leads(campaign_id)
    db.close()
    by_type = {t.value: 0 for t in CompanyType}
    by_status = {s.value: 0 for s in SequenceStatus}
    by_priority: dict[str, int] = {}
    bands = {"0-49": 0, "50-69": 0, "70-79": 0, "80-100": 0}
    for l in leads:
        by_type[l.company_type.value] += 1
        by_status[l.sequence_status.value] += 1
        by_priority[l.priority.value] = by_priority.get(l.priority.value, 0) + 1
        s = l.total_score
        bands["0-49" if s < 50 else "50-69" if s < 70 else "70-79" if s < 80 else "80-100"] += 1
    sent = sum(v for k, v in by_status.items() if k.endswith("_sent") or k in ("replied", "bounced", "unsubscribed"))
    return {
        "campaign_id": campaign_id, "leads": len(leads), "by_type": by_type, "by_status": by_status,
        "by_priority": by_priority, "score_bands": bands,
        "qualified": sum(1 for l in leads if l.company_type == CompanyType.BUYER and l.total_score >= campaign.min_score),
        "outreach_ready": sum(1 for l in leads if l.outreach_ready),
        "emails_sent": sent, "replied": by_status["replied"], "bounced": by_status["bounced"],
    }


# -- leads --------------------------------------------------------------------------------

@app.get("/campaigns/{campaign_id}/leads")
def leads(campaign_id: str, min_score: int = 0, company_type: str | None = None,
          outreach_ready: bool | None = None, limit: int = 500) -> list[dict]:
    db = _db()
    rows = db.list_leads(campaign_id, min_score=min_score, company_type=company_type, outreach_ready=outreach_ready)
    db.close()
    return [_lead_summary(l) for l in rows[:limit]]


def _lead_summary(l) -> dict:
    d = l.model_dump(mode="json")
    d.pop("evidence", None)
    return d


@app.get("/leads/{lead_id}")
def lead_detail(lead_id: str) -> dict:
    db = _db()
    l = db.get_lead(lead_id)
    if not l:
        db.close()
        raise HTTPException(404, "lead not found")
    events = db.events_for(lead_id)
    drafts = [db.get_draft(lead_id, s) for s in ("email_1", "followup_1", "followup_2")]
    db.close()
    d = l.model_dump(mode="json")
    d["events"] = events
    d["drafts"] = [x for x in drafts if x]
    return d


class SuppressRequest(BaseModel):
    reason: str | None = None


@app.post("/leads/{lead_id}/suppress")
def suppress(lead_id: str, req: SuppressRequest) -> dict:
    db = _db()
    l = db.get_lead(lead_id)
    if not l:
        db.close()
        raise HTTPException(404, "lead not found")
    if l.domain:
        db.add_suppression(l.domain, "domain", req.reason or "suppressed from UI")
    if l.contact_email:
        db.add_suppression(l.contact_email, "email", req.reason or "suppressed from UI")
    stop_lead(db, l, SequenceStatus.SUPPRESSED, req.reason or "suppressed from UI", Ledger(ledger_path(l.campaign_id)))
    db.close()
    return {"ok": True}


@app.get("/campaigns/{campaign_id}/export")
def export(campaign_id: str, min_score: int = 70, buyers_only: bool = True) -> FileResponse:
    db = _db()
    rows = db.list_leads(campaign_id, min_score=min_score,
                         company_type=CompanyType.BUYER.value if buyers_only else None)
    db.close()
    path = write_csv(rows, export_path(_settings.export_dir, campaign_id, "ui", buyers_only))
    return FileResponse(path, media_type="text/csv", filename=path.name)


# -- outreach: approval queue ------------------------------------------------------------

@app.get("/campaigns/{campaign_id}/outreach/queue")
def outreach_queue(campaign_id: str) -> dict:
    """Everything due now, each with its draft (rendered on first view)."""
    campaign = _campaign(campaign_id)
    osettings, templates = load_outreach_settings(), load_templates()
    db = _db()
    enqueue(db, campaign_id, osettings, Ledger(ledger_path(campaign_id)))
    items = prepare_drafts(db, campaign, osettings, templates)
    counts = {s.value: 0 for s in SequenceStatus}
    for l in db.list_leads(campaign_id):
        counts[l.sequence_status.value] += 1
    db.close()
    return {
        "items": [{"lead": _lead_summary(i["lead"]), "step": i["step"], "draft": i["draft"]} for i in items],
        "counts": counts,
        "smtp_configured": osettings.credentials_present,
        "daily_limit": osettings.daily_limit,
        "sent_today": Ledger(ledger_path(campaign_id)).sent_on(datetime.now(timezone.utc).strftime("%Y-%m-%d")),
    }


class DraftUpdate(BaseModel):
    subject: str
    body: str


@app.get("/leads/{lead_id}/drafts/{step}")
def get_draft(lead_id: str, step: str) -> dict:
    db = _db()
    l = db.get_lead(lead_id)
    if not l:
        db.close()
        raise HTTPException(404, "lead not found")
    draft = db.get_draft(lead_id, step)
    if not draft:
        campaign = _campaign(l.campaign_id)
        r = render(step, l, campaign, load_outreach_settings(), load_templates())
        draft = db.upsert_draft(lead_id, step, r.subject, r.body)
    db.close()
    return draft


@app.put("/leads/{lead_id}/drafts/{step}")
def update_draft(lead_id: str, step: str, req: DraftUpdate) -> dict:
    db = _db()
    existing = db.get_draft(lead_id, step)
    if existing and existing["status"] == "sent":
        db.close()
        raise HTTPException(409, "already sent")
    if "{" in req.subject + req.body and "}" in req.subject + req.body:
        db.close()
        raise HTTPException(422, "unfilled {placeholder} in draft")
    draft = db.upsert_draft(lead_id, step, req.subject.strip(), req.body, status="pending", edited=True)
    db.close()
    return draft


@app.post("/leads/{lead_id}/drafts/{step}/approve")
def approve_draft(lead_id: str, step: str) -> dict:
    db = _db()
    d = db.get_draft(lead_id, step)
    if not d:
        db.close()
        raise HTTPException(404, "no draft")
    if d["status"] == "sent":
        db.close()
        raise HTTPException(409, "already sent")
    db.set_draft_status(lead_id, step, "approved")
    db.add_event(lead_id, "approved", step=step)
    out = db.get_draft(lead_id, step)
    db.close()
    return out


@app.post("/leads/{lead_id}/drafts/{step}/reject")
def reject_draft(lead_id: str, step: str) -> dict:
    db = _db()
    if not db.get_draft(lead_id, step):
        db.close()
        raise HTTPException(404, "no draft")
    db.set_draft_status(lead_id, step, "rejected")
    db.add_event(lead_id, "rejected", step=step)
    out = db.get_draft(lead_id, step)
    db.close()
    return out


@app.post("/leads/{lead_id}/drafts/{step}/reset")
def reset_draft(lead_id: str, step: str) -> dict:
    """Discard edits and re-render from the template."""
    db = _db()
    l = db.get_lead(lead_id)
    if not l:
        db.close()
        raise HTTPException(404, "lead not found")
    r = render(step, l, _campaign(l.campaign_id), load_outreach_settings(), load_templates())
    draft = db.upsert_draft(lead_id, step, r.subject, r.body, status="pending", edited=False)
    db.close()
    return draft


class SendRequest(BaseModel):
    limit: int | None = None
    dry_run: bool = False
    ignore_window: bool = False


@app.post("/campaigns/{campaign_id}/outreach/send")
def outreach_send(campaign_id: str, req: SendRequest) -> dict:
    """Send approved, due emails. Runs the reply sync first so nobody who answered gets a follow-up."""
    campaign = _campaign(campaign_id)
    osettings, templates = load_outreach_settings(), load_templates()
    db = _db()
    ledger = Ledger(ledger_path(campaign_id))
    sync = None
    if osettings.credentials_present and not req.dry_run:
        try:
            r = sync_replies(db, campaign_id, osettings, ledger)
            sync = {"replied": r.replied, "unsubscribed": r.unsubscribed, "bounced": r.bounced, "scanned": r.scanned}
        except Exception as exc:  # noqa: BLE001 - a mailbox hiccup must not block a supervised send
            sync = {"error": str(exc)}
    dry = req.dry_run or not osettings.credentials_present
    if dry:
        # No trace on the real DB or ledger: work on throwaway copies.
        db.close()
        scratch = _settings.db_path.parent / "outbox"
        scratch.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_settings.db_path, scratch / "dryrun.sqlite")
        db = Database(scratch / "dryrun.sqlite")
        ledger.path = scratch / "dryrun_ledger.json"
    sender = make_sender(osettings, _settings.db_path.parent / "outbox", force_dry_run=dry)
    report = send_due(db, campaign, osettings, templates, sender, ledger, limit=req.limit, ignore_window=req.ignore_window)
    if hasattr(sender, "close"):
        sender.close()
    db.close()
    return {"sent": report.sent, "skipped": report.skipped, "failed": report.failed,
            "stopped_reason": report.stopped_reason, "details": report.details,
            "mode": sender.name, "sync": sync}


@app.post("/campaigns/{campaign_id}/outreach/sync")
def outreach_sync(campaign_id: str) -> dict:
    osettings = load_outreach_settings()
    if not osettings.credentials_present:
        raise HTTPException(400, "SMTP credentials not configured")
    db = _db()
    r = sync_replies(db, campaign_id, osettings, Ledger(ledger_path(campaign_id)))
    db.close()
    return {"replied": r.replied, "unsubscribed": r.unsubscribed, "bounced": r.bounced,
            "scanned": r.scanned, "details": r.details}


@app.get("/campaigns/{campaign_id}/outreach/activity")
def outreach_activity(campaign_id: str, limit: int = 100) -> list[dict]:
    db = _db()
    rows = db.conn.execute(
        "SELECT e.*, l.data_json FROM outreach_events e JOIN leads l ON l.lead_id = e.lead_id "
        "WHERE l.campaign_id = ? ORDER BY e.event_id DESC LIMIT ?", (campaign_id, limit)
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        lead = json.loads(d.pop("data_json"))
        d["company_name"] = lead.get("company_name")
        d["contact_email"] = lead.get("contact_email")
        out.append(d)
    db.close()
    return out


@app.get("/campaigns/{campaign_id}/outreach/sequence")
def outreach_sequence(campaign_id: str) -> list[dict]:
    """Every lead that is in or has finished the sequence."""
    db = _db()
    active = [s.value for s in ACTIVE] + [SequenceStatus.FOLLOWUP_2_SENT.value, SequenceStatus.REPLIED.value,
                                          SequenceStatus.BOUNCED.value, SequenceStatus.UNSUBSCRIBED.value,
                                          SequenceStatus.SUPPRESSED.value]
    rows = db.leads_by_status(campaign_id, active)
    db.close()
    return [_lead_summary(l) for l in rows]
