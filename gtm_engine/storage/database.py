"""SQLite repository. Plain SQL kept portable (no SQLite-only syntax beyond
INSERT OR REPLACE) so this can be pointed at Postgres/Supabase later."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from gtm_engine.models import Lead, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    stats_json TEXT
);

CREATE TABLE IF NOT EXISTS companies (
    company_key TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT,
    website TEXT,
    country TEXT,
    city TEXT,
    source TEXT,
    source_url TEXT,
    discovered_at TEXT NOT NULL,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS pages (
    url TEXT PRIMARY KEY,
    company_key TEXT NOT NULL,
    kind TEXT,
    status_code INTEGER,
    title TEXT,
    text TEXT,
    fetched_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS leads (
    lead_id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL,
    run_id TEXT,
    company_key TEXT,
    company_type TEXT NOT NULL,
    total_score INTEGER NOT NULL,
    priority TEXT NOT NULL,
    outreach_ready INTEGER NOT NULL DEFAULT 0,
    sequence_status TEXT NOT NULL,
    contact_email TEXT,
    data_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leads_campaign ON leads(campaign_id);
CREATE INDEX IF NOT EXISTS idx_leads_company ON leads(company_key);

CREATE TABLE IF NOT EXISTS suppressions (
    value TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    lead_id TEXT NOT NULL,
    step TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,               -- pending | approved | rejected | sent
    edited INTEGER NOT NULL DEFAULT 0,  -- 1 when a human changed the rendered text
    created_at TEXT NOT NULL,
    approved_at TEXT,
    PRIMARY KEY (lead_id, step)
);

CREATE TABLE IF NOT EXISTS outreach_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    step TEXT,
    detail TEXT,
    created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        if str(path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(path))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    # -- campaigns / runs -------------------------------------------------

    def upsert_campaign(self, campaign_id: str, name: str, config: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO campaigns (campaign_id, name, config_json, created_at) "
            "VALUES (?, ?, ?, COALESCE((SELECT created_at FROM campaigns WHERE campaign_id = ?), ?))",
            (campaign_id, name, json.dumps(config, default=str), campaign_id, utcnow().isoformat()),
        )
        self.conn.commit()

    def start_run(self, run_id: str, campaign_id: str) -> None:
        self.conn.execute(
            "INSERT INTO runs (run_id, campaign_id, started_at, status) VALUES (?, ?, ?, 'running')",
            (run_id, campaign_id, utcnow().isoformat()),
        )
        self.conn.commit()

    def finish_run(self, run_id: str, status: str, stats: dict) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at = ?, status = ?, stats_json = ? WHERE run_id = ?",
            (utcnow().isoformat(), status, json.dumps(stats, default=str), run_id),
        )
        self.conn.commit()

    def get_run(self, run_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, campaign_id: str | None = None) -> list[dict]:
        if campaign_id:
            rows = self.conn.execute(
                "SELECT * FROM runs WHERE campaign_id = ? ORDER BY started_at DESC", (campaign_id,)
            )
        else:
            rows = self.conn.execute("SELECT * FROM runs ORDER BY started_at DESC")
        return [dict(r) for r in rows]

    # -- companies ----------------------------------------------------------

    def upsert_company(self, company_key: str, campaign_id: str, name: str, *,
                       domain: str | None, website: str | None, country: str | None,
                       city: str | None, source: str, source_url: str | None, raw: dict) -> bool:
        """Returns True if the company was new for this campaign."""
        exists = self.conn.execute(
            "SELECT 1 FROM companies WHERE company_key = ?", (company_key,)
        ).fetchone()
        self.conn.execute(
            "INSERT OR REPLACE INTO companies (company_key, campaign_id, name, domain, website, "
            "country, city, source, source_url, discovered_at, raw_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (company_key, campaign_id, name, domain, website, country, city, source,
             source_url, utcnow().isoformat(), json.dumps(raw, default=str)),
        )
        self.conn.commit()
        return exists is None

    # -- pages --------------------------------------------------------------

    def save_page(self, company_key: str, url: str, kind: str, status_code: int,
                  title: str | None, text: str) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO pages (url, company_key, kind, status_code, title, text, fetched_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (url, company_key, kind, status_code, title, text, utcnow().isoformat()),
        )
        self.conn.commit()

    # -- leads --------------------------------------------------------------

    def save_lead(self, lead: Lead, run_id: str | None, company_key: str | None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO leads (lead_id, campaign_id, run_id, company_key, company_type, "
            "total_score, priority, outreach_ready, sequence_status, contact_email, data_json, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (lead.lead_id, lead.campaign_id, run_id, company_key, lead.company_type.value,
             lead.total_score, lead.priority.value, int(lead.outreach_ready),
             lead.sequence_status.value, lead.contact_email,
             lead.model_dump_json(), utcnow().isoformat()),
        )
        self.conn.commit()

    def update_lead(self, lead: Lead) -> None:
        """Update a lead's state without touching run_id/company_key (outreach stages)."""
        self.conn.execute(
            "UPDATE leads SET company_type = ?, total_score = ?, priority = ?, outreach_ready = ?, "
            "sequence_status = ?, contact_email = ?, data_json = ?, updated_at = ? WHERE lead_id = ?",
            (lead.company_type.value, lead.total_score, lead.priority.value, int(lead.outreach_ready),
             lead.sequence_status.value, lead.contact_email, lead.model_dump_json(),
             utcnow().isoformat(), lead.lead_id),
        )
        self.conn.commit()

    def get_lead(self, lead_id: str) -> Lead | None:
        row = self.conn.execute("SELECT data_json FROM leads WHERE lead_id = ?", (lead_id,)).fetchone()
        return Lead.model_validate_json(row["data_json"]) if row else None

    def list_leads(self, campaign_id: str, *, run_id: str | None = None,
                   min_score: int | None = None, company_type: str | None = None,
                   outreach_ready: bool | None = None) -> list[Lead]:
        sql = "SELECT data_json FROM leads WHERE campaign_id = ?"
        params: list = [campaign_id]
        if run_id:
            sql += " AND run_id = ?"
            params.append(run_id)
        if min_score is not None:
            sql += " AND total_score >= ?"
            params.append(min_score)
        if company_type:
            sql += " AND company_type = ?"
            params.append(company_type)
        if outreach_ready is not None:
            sql += " AND outreach_ready = ?"
            params.append(int(outreach_ready))
        sql += " ORDER BY total_score DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [Lead.model_validate_json(r["data_json"]) for r in rows]

    def leads_by_status(self, campaign_id: str, statuses: list[str]) -> list[Lead]:
        placeholders = ",".join("?" for _ in statuses)
        rows = self.conn.execute(
            f"SELECT data_json FROM leads WHERE campaign_id = ? AND sequence_status IN ({placeholders}) "
            "ORDER BY total_score DESC", [campaign_id, *statuses]
        ).fetchall()
        return [Lead.model_validate_json(r["data_json"]) for r in rows]

    def campaign_config(self, campaign_id: str) -> dict | None:
        row = self.conn.execute("SELECT config_json FROM campaigns WHERE campaign_id = ?", (campaign_id,)).fetchone()
        return json.loads(row["config_json"]) if row else None

    def bounced_today(self, campaign_id: str, day: str, mailbox: str | None = None,
                      legacy_mailbox: str | None = None) -> int:
        """Leads that bounced among those sent on `day` (optionally by one mailbox; leads
        without a recorded mailbox belong to `legacy_mailbox`)."""
        n = 0
        for l in self.leads_by_status(campaign_id, ["bounced"]):
            if not l.last_sent_at or l.last_sent_at.strftime("%Y-%m-%d") != day:
                continue
            owner = (l.mailbox or legacy_mailbox or mailbox or "").lower()
            if mailbox is None or owner == mailbox.lower():
                n += 1
        return n

    def events_today(self, event_type: str, day_prefix: str) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM outreach_events WHERE event_type = ? AND created_at LIKE ?",
            (event_type, day_prefix + "%"),
        ).fetchone()[0]

    def lead_for_company(self, campaign_id: str, company_key: str) -> Lead | None:
        row = self.conn.execute(
            "SELECT data_json FROM leads WHERE campaign_id = ? AND company_key = ? "
            "ORDER BY updated_at DESC LIMIT 1", (campaign_id, company_key)
        ).fetchone()
        return Lead.model_validate_json(row["data_json"]) if row else None

    # -- suppressions ---------------------------------------------------------

    def add_suppression(self, value: str, kind: str, reason: str | None = None) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO suppressions (value, kind, reason, created_at) VALUES (?, ?, ?, ?)",
            (value.lower().strip(), kind, reason, utcnow().isoformat()),
        )
        self.conn.commit()

    def is_suppressed(self, *values: str | None) -> bool:
        vals = [v.lower().strip() for v in values if v]
        if not vals:
            return False
        placeholders = ",".join("?" for _ in vals)
        return self.conn.execute(
            f"SELECT 1 FROM suppressions WHERE value IN ({placeholders}) LIMIT 1", vals
        ).fetchone() is not None

    # -- drafts (human approval) ----------------------------------------------

    def get_draft(self, lead_id: str, step: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM drafts WHERE lead_id = ? AND step = ?", (lead_id, step)).fetchone()
        return dict(row) if row else None

    def upsert_draft(self, lead_id: str, step: str, subject: str, body: str, *,
                     status: str = "pending", edited: bool = False) -> dict:
        existing = self.get_draft(lead_id, step)
        created = existing["created_at"] if existing else utcnow().isoformat()
        approved_at = utcnow().isoformat() if status == "approved" else (existing or {}).get("approved_at")
        self.conn.execute(
            "INSERT OR REPLACE INTO drafts (lead_id, step, subject, body, status, edited, created_at, approved_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (lead_id, step, subject, body, status, int(edited), created, approved_at),
        )
        self.conn.commit()
        return self.get_draft(lead_id, step)

    def set_draft_status(self, lead_id: str, step: str, status: str) -> None:
        self.conn.execute(
            "UPDATE drafts SET status = ?, approved_at = COALESCE(approved_at, ?) WHERE lead_id = ? AND step = ?",
            (status, utcnow().isoformat() if status == "approved" else None, lead_id, step),
        )
        self.conn.commit()

    def drafts_by_status(self, status: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM drafts WHERE status = ? ORDER BY created_at", (status,))]

    def list_suppressions(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM suppressions ORDER BY created_at DESC")]

    def remove_suppression(self, value: str) -> bool:
        cur = self.conn.execute("DELETE FROM suppressions WHERE value = ?", (value.lower().strip(),))
        self.conn.commit()
        return cur.rowcount > 0

    # -- outreach events -----------------------------------------------------

    def add_event(self, lead_id: str, event_type: str, step: str | None = None,
                  detail: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO outreach_events (lead_id, event_type, step, detail, created_at) VALUES (?, ?, ?, ?, ?)",
            (lead_id, event_type, step, detail, utcnow().isoformat()),
        )
        self.conn.commit()

    def events_for(self, lead_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM outreach_events WHERE lead_id = ? ORDER BY event_id", (lead_id,)
        )]
