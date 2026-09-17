"""FastAPI skeleton (M1). Runs a campaign in the background and exposes leads/exports.
The UI layer will sit on top of these endpoints."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse

from gtm_engine import __version__
from gtm_engine.config import CampaignConfig, load_defaults, load_settings
from gtm_engine.export.csv_export import export_path, write_csv
from gtm_engine.models import CompanyType
from gtm_engine.pipeline import Pipeline
from gtm_engine.scraping.fetcher import HttpFetcher
from gtm_engine.storage.database import Database

log = logging.getLogger(__name__)
app = FastAPI(title="GTM Lead Engine", version=__version__)

_settings = load_settings()
_defaults = load_defaults()
_progress: dict[str, dict] = {}  # run_id -> {stage, done, total, message}


def _db() -> Database:
    return Database(_settings.db_path)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__}


@app.post("/campaigns/run")
async def run_campaign(campaign: CampaignConfig, background: BackgroundTasks) -> dict:
    """Start a run. Returns immediately; poll /runs/{run_id} for progress."""
    ticket = {"run_id": None, "stage": "queued", "done": 0, "total": 0, "message": ""}
    key = f"pending-{campaign.campaign_id}"
    _progress[key] = ticket

    async def job() -> None:
        db = _db()
        try:
            async with HttpFetcher(_settings) as fetcher:
                pipeline = Pipeline(_settings, _defaults, db, fetcher)

                def on_progress(stage: str, done: int, total: int, message: str) -> None:
                    ticket.update(stage=stage, done=done, total=total, message=message)

                result = await pipeline.run(campaign, progress=on_progress)
                ticket.update(run_id=result.run_id, stage="completed", message="done")
                _progress[result.run_id] = ticket
        except Exception as exc:  # noqa: BLE001
            ticket.update(stage="failed", message=str(exc))
            log.exception("run failed")
        finally:
            db.close()

    background.add_task(asyncio.ensure_future, job())
    return {"ticket": key}


@app.get("/runs/{run_id}")
def run_status(run_id: str) -> dict:
    live = _progress.get(run_id)
    db = _db()
    stored = db.get_run(run_id)
    db.close()
    if not live and not stored:
        raise HTTPException(404, "run not found")
    return {"live": live, "stored": stored}


@app.get("/campaigns/{campaign_id}/leads")
def leads(campaign_id: str, min_score: int = 0, buyers_only: bool = True, run_id: str | None = None) -> list[dict]:
    db = _db()
    rows = db.list_leads(campaign_id, run_id=run_id, min_score=min_score,
                         company_type=CompanyType.BUYER.value if buyers_only else None)
    db.close()
    return [r.model_dump(mode="json") for r in rows]


@app.get("/campaigns/{campaign_id}/export")
def export(campaign_id: str, min_score: int = 70, buyers_only: bool = True, run_id: str | None = None) -> FileResponse:
    db = _db()
    rows = db.list_leads(campaign_id, run_id=run_id, min_score=min_score,
                         company_type=CompanyType.BUYER.value if buyers_only else None)
    db.close()
    path: Path = write_csv(rows, export_path(_settings.export_dir, campaign_id, run_id or "latest", buyers_only))
    return FileResponse(path, media_type="text/csv", filename=path.name)
