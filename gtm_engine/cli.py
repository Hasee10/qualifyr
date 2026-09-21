"""Command line entry point: run a campaign, export leads, manage suppressions."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from gtm_engine.config import load_campaign, load_defaults, load_settings
from gtm_engine.export.csv_export import export_path, write_csv
from gtm_engine.models import CompanyType
from gtm_engine.outreach.cli import add_outreach_parser
from gtm_engine.pipeline import Pipeline
from gtm_engine.scraping.browser import build_fetcher
from gtm_engine.storage.database import Database


def _setup_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


def _progress(stage: str, done: int, total: int, message: str) -> None:
    suffix = f"{done}/{total}" if total else str(done)
    print(f"[{stage:>8}] {suffix:<9} {message}", file=sys.stderr, flush=True)


async def _run(args: argparse.Namespace) -> int:
    settings = load_settings()
    _setup_logging(args.log_level or settings.log_level)
    defaults = load_defaults()
    campaign = load_campaign(args.campaign)
    if args.max_companies:
        campaign.max_companies = args.max_companies
    db = Database(settings.db_path)
    async with build_fetcher(settings) as fetcher:
        pipeline = Pipeline(settings, defaults, db, fetcher)
        result = await pipeline.run(campaign, progress=_progress)
    if getattr(fetcher, "fallbacks", 0):
        print(f"  browser fallback rendered {fetcher.fallbacks} page(s)")

    s = result.stats
    print(f"\nrun {result.run_id} finished")
    print(f"  discovered {s.discovered} -> {s.after_dedupe} unique; processed {s.processed}")
    print(f"  BUYER {s.buyer} | VENDOR {s.vendor} | UNKNOWN {s.unknown}")
    print(f"  qualified {s.qualified} | outreach-ready {s.outreach_ready} | no website {s.no_website} | unreachable {s.unreachable} | duplicates {s.duplicates} | errors {s.errors}")

    qualified = [l for l in result.leads if l.company_type == CompanyType.BUYER and l.total_score >= campaign.min_score]
    out_q = write_csv(qualified, export_path(settings.export_dir, campaign.campaign_id, result.run_id, True))
    out_all = write_csv(result.leads, export_path(settings.export_dir, campaign.campaign_id, result.run_id, False))
    print(f"  qualified CSV: {out_q}")
    print(f"  full CSV:      {out_all}")
    db.close()
    return 0


def _export(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    leads = db.list_leads(args.campaign_id, run_id=args.run_id,
                          min_score=None if args.all else args.min_score,
                          company_type=None if args.all else CompanyType.BUYER.value)
    out = Path(args.out) if args.out else export_path(settings.export_dir, args.campaign_id, args.run_id or "latest", not args.all)
    write_csv(leads, out)
    print(f"wrote {len(leads)} leads -> {out}")
    db.close()
    return 0


def _sheets(args: argparse.Namespace) -> int:
    from gtm_engine.export import sheets as sheets_export
    settings = load_settings()
    db = Database(settings.db_path)
    leads = db.list_leads(args.campaign_id, min_score=None if args.all else args.min_score,
                          company_type=None if args.all else CompanyType.BUYER.value)
    db.close()
    info = sheets_export.export_leads(leads, args.campaign_id, tab=args.tab)
    print(f"wrote {info['rows']} leads -> {info['url']} (tab {info['tab']})")
    return 0


def _suppress(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    kind = "email" if "@" in args.value else "domain"
    db.add_suppression(args.value, kind, args.reason)
    print(f"suppressed {kind}: {args.value}")
    db.close()
    return 0


def _runs(args: argparse.Namespace) -> int:
    settings = load_settings()
    db = Database(settings.db_path)
    for r in db.list_runs(args.campaign_id):
        print(f"{r['run_id']}  {r['campaign_id']}  {r['status']:<9}  {r['started_at'][:19]}  {r.get('stats_json') or ''}")
    db.close()
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gtm", description="Buyer-only GTM lead engine")
    sub = p.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a campaign end-to-end and export CSVs")
    run.add_argument("campaign", help="path to campaign YAML")
    run.add_argument("--max-companies", type=int, default=None)
    run.add_argument("--log-level", default=None)
    run.set_defaults(func=lambda a: asyncio.run(_run(a)))

    exp = sub.add_parser("export", help="export stored leads for a campaign")
    exp.add_argument("campaign_id")
    exp.add_argument("--run-id", default=None)
    exp.add_argument("--min-score", type=int, default=70)
    exp.add_argument("--all", action="store_true", help="include vendors/unknown/rejected")
    exp.add_argument("--out", default=None)
    exp.set_defaults(func=_export)

    sh = sub.add_parser("sheets", help="mirror leads to the configured Google Sheet")
    sh.add_argument("campaign_id")
    sh.add_argument("--min-score", type=int, default=70)
    sh.add_argument("--all", action="store_true")
    sh.add_argument("--tab", default=None)
    sh.set_defaults(func=_sheets)

    sup = sub.add_parser("suppress", help="never contact this email or domain again")
    sup.add_argument("value")
    sup.add_argument("--reason", default=None)
    sup.set_defaults(func=_suppress)

    runs = sub.add_parser("runs", help="list past runs")
    runs.add_argument("--campaign-id", default=None)
    runs.set_defaults(func=_runs)

    add_outreach_parser(sub)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
