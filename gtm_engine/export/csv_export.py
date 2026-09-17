"""CSV export in the exact column order the spec requires. UTF-8 with BOM so Excel on
Windows opens Urdu/Arabic company names correctly."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable

from gtm_engine.models import CSV_COLUMNS, Lead


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)


def lead_row(lead: Lead) -> dict[str, str]:
    data = lead.model_dump()
    return {col: _cell(data.get(col)) for col in CSV_COLUMNS}


def write_csv(leads: Iterable[Lead], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for lead in leads:
            writer.writerow(lead_row(lead))
    return path


def export_path(export_dir: Path, campaign_id: str, run_id: str, qualified_only: bool) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = "qualified" if qualified_only else "all"
    return export_dir / f"{campaign_id}_{stamp}_{run_id}_{suffix}.csv"
