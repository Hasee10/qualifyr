"""Postgres (Supabase) repository. Was SQLite; kept the same plain-SQL, thin-repository
shape (see docs/DECISIONS.md) so only this module and its constructor argument changed —
every caller still just does `Database(dsn)` and calls the same methods."""

from __future__ import annotations

import json
import re
import urllib.parse

import psycopg
from psycopg.rows import dict_row

from gtm_engine.models import Lead, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    campaign_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    owner_id TEXT
);
-- Multi-tenancy: scope a campaign (and thus its leads) to the account that created it.
-- Added by migration so databases created before multi-tenancy pick the column up too;
-- NULL owner means a shared/legacy campaign, visible to everyone.
ALTER TABLE campaigns ADD COLUMN IF NOT EXISTS owner_id TEXT;

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
    event_id SERIAL PRIMARY KEY,
    lead_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    step TEXT,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_progress (
    campaign_id TEXT PRIMARY KEY,
    run_id TEXT,
    stage TEXT,
    done INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0,
    message TEXT,
    updated_at TEXT NOT NULL
);
"""


# DSNs whose schema this process has already ensured. Every API request opens a fresh
# Database, and re-running ~10 DDL statements per request would dominate the latency of
# an otherwise trivial read; once per process (warm serverless container) is enough.
_SCHEMA_READY: set[str] = set()

# A fixed key for the advisory lock that serialises schema creation (see __init__). Any
# constant works - it only ever guards the DDL below, which is idempotent and rare.
_SCHEMA_LOCK_KEY = 0x67746D5F736368  # "gtm_sch"


def _search_path_of(dsn: str) -> str | None:
    """The schema named by `?options=-csearch_path=NAME` in a DSN, if any.

    Only the tests use this (each gets a disposable schema); production DSNs carry no
    options and land in `public`.
    """
    query = urllib.parse.urlsplit(dsn).query
    for value in urllib.parse.parse_qs(query).get("options", []):
        match = re.search(r"-c\s*search_path\s*=\s*([^\s,]+)", value)
        if match:
            return match.group(1)
    return None


class Database:
    def __init__(self, dsn: str, *, dry_run: bool = False, ensure_schema: bool | None = None):
        """`dry_run=True` opens a transaction that is rolled back on close() instead of
        committed, so simulated writes (e.g. `outreach send --dry-run`) are invisible to
        every other connection and never touch real data - replaces the old SQLite
        file-copy trick, and works against live current state instead of a stale copy.

        `ensure_schema` defaults to "once per DSN per process"; pass False to skip the
        DDL entirely or True to force it."""
        if not dsn:
            raise ValueError(
                "no database DSN: set GTM_DATABASE_URL to the Supabase Postgres "
                "connection string (see .env.example)"
            )
        self.dsn = dsn
        self.dry_run = dry_run
        # prepare_threshold=None disables psycopg's automatic prepared statements, which
        # PgBouncer in transaction mode (Supabase's :6543 pooler, the right choice for
        # serverless) cannot carry across pooled connections. Harmless on :5432.
        self.conn = psycopg.connect(
            dsn, row_factory=dict_row, autocommit=False, prepare_threshold=None
        )
        # A search_path in the DSN's `options=` is a *startup parameter*, and PgBouncer
        # does not forward those - against Supabase's pooler it is silently dropped and
        # every query quietly resolves in `public` instead. That failure is invisible
        # (no error, just the wrong schema), so re-apply it as an explicit SET, which
        # goes over the wire as a normal statement and always takes effect.
        schema = _search_path_of(dsn)
        if schema:
            self.conn.execute(f'SET search_path TO "{schema}"')
            self.conn.commit()
        if ensure_schema is None:
            ensure_schema = dsn not in _SCHEMA_READY
        if ensure_schema:
            # `CREATE TABLE IF NOT EXISTS` is not atomic against a concurrent create: two
            # connections can both find a table absent and both try to create it, and one
            # then fails on the pg_type unique index (seen when a burst of requests hits a
            # cold, empty database at once). A transaction-scoped advisory lock serialises
            # this DDL across connections; it releases on commit, so it is safe through a
            # transaction-mode pooler (PgBouncer) too.
            self.conn.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK_KEY,))
            self.conn.execute(SCHEMA)
            self.conn.commit()
            _SCHEMA_READY.add(dsn)

    def _commit(self) -> None:
        if not self.dry_run:
            self.conn.commit()

    def close(self) -> None:
        if self.dry_run:
            self.conn.rollback()
        self.conn.close()

    # -- campaigns / runs -------------------------------------------------

    def upsert_campaign(self, campaign_id: str, name: str, config: dict, owner_id: str | None = None) -> None:
        # owner_id is set on create and preserved on later updates (a run re-upserts the
        # campaign but must not blank its owner), so COALESCE keeps the existing owner when
        # the caller passes None.
        self.conn.execute(
            "INSERT INTO campaigns (campaign_id, name, config_json, created_at, owner_id) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (campaign_id) DO UPDATE SET name = EXCLUDED.name, config_json = EXCLUDED.config_json, "
            "owner_id = COALESCE(campaigns.owner_id, EXCLUDED.owner_id)",
            (campaign_id, name, json.dumps(config, default=str), utcnow().isoformat(), owner_id),
        )
        self._commit()

    def list_campaigns(self, owner_id: str | None = None) -> list[dict]:
        """User-created campaigns, newest first. With owner_id, only that owner's campaigns
        plus legacy shared (NULL-owner) ones; without it (local operator), all of them."""
        sql = "SELECT campaign_id, name, config_json, created_at, owner_id FROM campaigns"
        params: list = []
        if owner_id is not None:
            sql += " WHERE owner_id = %s OR owner_id IS NULL"
            params.append(owner_id)
        sql += " ORDER BY created_at DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [{"campaign_id": r["campaign_id"], "name": r["name"], "created_at": r["created_at"],
                 "owner_id": r["owner_id"], "config": json.loads(r["config_json"])} for r in rows]

    def campaign_owner(self, campaign_id: str) -> str | None:
        row = self.conn.execute("SELECT owner_id FROM campaigns WHERE campaign_id = %s", (campaign_id,)).fetchone()
        return row["owner_id"] if row else None

    def delete_campaign(self, campaign_id: str) -> None:
        self.conn.execute("DELETE FROM campaigns WHERE campaign_id = %s", (campaign_id,))
        self._commit()

    def start_run(self, run_id: str, campaign_id: str) -> None:
        self.conn.execute(
            "INSERT INTO runs (run_id, campaign_id, started_at, status) VALUES (%s, %s, %s, 'running')",
            (run_id, campaign_id, utcnow().isoformat()),
        )
        self._commit()

    def finish_run(self, run_id: str, status: str, stats: dict) -> None:
        self.conn.execute(
            "UPDATE runs SET finished_at = %s, status = %s, stats_json = %s WHERE run_id = %s",
            (utcnow().isoformat(), status, json.dumps(stats, default=str), run_id),
        )
        self._commit()

    def get_run(self, run_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM runs WHERE run_id = %s", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_runs(self, campaign_id: str | None = None) -> list[dict]:
        if campaign_id:
            rows = self.conn.execute(
                "SELECT * FROM runs WHERE campaign_id = %s ORDER BY started_at DESC", (campaign_id,)
            )
        else:
            rows = self.conn.execute("SELECT * FROM runs ORDER BY started_at DESC")
        return [dict(r) for r in rows]

    # -- run progress (polled by GET /campaigns/{id}/progress) --------------

    def set_run_progress(self, campaign_id: str, run_id: str | None, stage: str,
                          done: int, total: int, message: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO run_progress (campaign_id, run_id, stage, done, total, message, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (campaign_id) DO UPDATE SET run_id = EXCLUDED.run_id, stage = EXCLUDED.stage, "
            "done = EXCLUDED.done, total = EXCLUDED.total, message = EXCLUDED.message, "
            "updated_at = EXCLUDED.updated_at",
            (campaign_id, run_id, stage, done, total, message, utcnow().isoformat()),
        )
        self._commit()

    def get_run_progress(self, campaign_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM run_progress WHERE campaign_id = %s", (campaign_id,)
        ).fetchone()
        return dict(row) if row else None

    # -- companies ----------------------------------------------------------

    def upsert_company(self, company_key: str, campaign_id: str, name: str, *,
                       domain: str | None, website: str | None, country: str | None,
                       city: str | None, source: str, source_url: str | None, raw: dict) -> bool:
        """Returns True if the company was new for this campaign."""
        exists = self.conn.execute(
            "SELECT 1 FROM companies WHERE company_key = %s", (company_key,)
        ).fetchone()
        self.conn.execute(
            "INSERT INTO companies (company_key, campaign_id, name, domain, website, "
            "country, city, source, source_url, discovered_at, raw_json) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (company_key) DO UPDATE SET campaign_id = EXCLUDED.campaign_id, "
            "name = EXCLUDED.name, domain = EXCLUDED.domain, website = EXCLUDED.website, "
            "country = EXCLUDED.country, city = EXCLUDED.city, source = EXCLUDED.source, "
            "source_url = EXCLUDED.source_url, discovered_at = EXCLUDED.discovered_at, "
            "raw_json = EXCLUDED.raw_json",
            (company_key, campaign_id, name, domain, website, country, city, source,
             source_url, utcnow().isoformat(), json.dumps(raw, default=str)),
        )
        self._commit()
        return exists is None

    # -- pages --------------------------------------------------------------

    def save_page(self, company_key: str, url: str, kind: str, status_code: int,
                  title: str | None, text: str) -> None:
        self.conn.execute(
            "INSERT INTO pages (url, company_key, kind, status_code, title, text, fetched_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (url) DO UPDATE SET company_key = EXCLUDED.company_key, kind = EXCLUDED.kind, "
            "status_code = EXCLUDED.status_code, title = EXCLUDED.title, text = EXCLUDED.text, "
            "fetched_at = EXCLUDED.fetched_at",
            (url, company_key, kind, status_code, title, text, utcnow().isoformat()),
        )
        self._commit()

    # -- leads --------------------------------------------------------------

    def save_lead(self, lead: Lead, run_id: str | None, company_key: str | None) -> None:
        self.conn.execute(
            "INSERT INTO leads (lead_id, campaign_id, run_id, company_key, company_type, "
            "total_score, priority, outreach_ready, sequence_status, contact_email, data_json, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (lead_id) DO UPDATE SET campaign_id = EXCLUDED.campaign_id, run_id = EXCLUDED.run_id, "
            "company_key = EXCLUDED.company_key, company_type = EXCLUDED.company_type, "
            "total_score = EXCLUDED.total_score, priority = EXCLUDED.priority, "
            "outreach_ready = EXCLUDED.outreach_ready, sequence_status = EXCLUDED.sequence_status, "
            "contact_email = EXCLUDED.contact_email, data_json = EXCLUDED.data_json, "
            "updated_at = EXCLUDED.updated_at",
            (lead.lead_id, lead.campaign_id, run_id, company_key, lead.company_type.value,
             lead.total_score, lead.priority.value, int(lead.outreach_ready),
             lead.sequence_status.value, lead.contact_email,
             lead.model_dump_json(), utcnow().isoformat()),
        )
        self._commit()

    def update_lead(self, lead: Lead) -> None:
        """Update a lead's state without touching run_id/company_key (outreach stages)."""
        self.conn.execute(
            "UPDATE leads SET company_type = %s, total_score = %s, priority = %s, outreach_ready = %s, "
            "sequence_status = %s, contact_email = %s, data_json = %s, updated_at = %s WHERE lead_id = %s",
            (lead.company_type.value, lead.total_score, lead.priority.value, int(lead.outreach_ready),
             lead.sequence_status.value, lead.contact_email, lead.model_dump_json(),
             utcnow().isoformat(), lead.lead_id),
        )
        self._commit()

    def get_lead(self, lead_id: str) -> Lead | None:
        row = self.conn.execute("SELECT data_json FROM leads WHERE lead_id = %s", (lead_id,)).fetchone()
        return Lead.model_validate_json(row["data_json"]) if row else None

    def list_leads(self, campaign_id: str, *, run_id: str | None = None,
                   min_score: int | None = None, company_type: str | None = None,
                   outreach_ready: bool | None = None) -> list[Lead]:
        sql = "SELECT data_json FROM leads WHERE campaign_id = %s"
        params: list = [campaign_id]
        if run_id:
            sql += " AND run_id = %s"
            params.append(run_id)
        if min_score is not None:
            sql += " AND total_score >= %s"
            params.append(min_score)
        if company_type:
            sql += " AND company_type = %s"
            params.append(company_type)
        if outreach_ready is not None:
            sql += " AND outreach_ready = %s"
            params.append(int(outreach_ready))
        sql += " ORDER BY total_score DESC"
        rows = self.conn.execute(sql, params).fetchall()
        return [Lead.model_validate_json(r["data_json"]) for r in rows]

    def leads_by_status(self, campaign_id: str, statuses: list[str]) -> list[Lead]:
        placeholders = ",".join("%s" for _ in statuses)
        rows = self.conn.execute(
            f"SELECT data_json FROM leads WHERE campaign_id = %s AND sequence_status IN ({placeholders}) "
            "ORDER BY total_score DESC", [campaign_id, *statuses]
        ).fetchall()
        return [Lead.model_validate_json(r["data_json"]) for r in rows]

    def campaign_config(self, campaign_id: str) -> dict | None:
        row = self.conn.execute("SELECT config_json FROM campaigns WHERE campaign_id = %s", (campaign_id,)).fetchone()
        return json.loads(row["config_json"]) if row else None

    def campaign_counts(self, campaign_id: str, min_score: int) -> dict:
        """Lead tallies for a campaign in one aggregate query, computed in Postgres from the
        indexed columns rather than by loading and JSON-parsing every Lead in Python. This is
        what /campaigns needs per campaign for the dropdown, and doing it in SQL keeps that
        list fast no matter how many leads a campaign accumulates."""
        row = self.conn.execute(
            "SELECT COUNT(*) AS leads, "
            "COUNT(*) FILTER (WHERE company_type = 'BUYER') AS buyers, "
            "COUNT(*) FILTER (WHERE company_type = 'BUYER' AND total_score >= %s) AS qualified, "
            "COUNT(*) FILTER (WHERE outreach_ready = 1) AS outreach_ready "
            "FROM leads WHERE campaign_id = %s",
            (min_score, campaign_id),
        ).fetchone()
        return {"leads": row["leads"], "buyers": row["buyers"],
                "qualified": row["qualified"], "outreach_ready": row["outreach_ready"]}

    def campaign_of_lead(self, lead_id: str) -> str | None:
        """The campaign a lead belongs to, or None if the lead is unknown. Used to scope
        lead-level routes to the campaign's owner without deserialising the whole Lead."""
        row = self.conn.execute("SELECT campaign_id FROM leads WHERE lead_id = %s", (lead_id,)).fetchone()
        return row["campaign_id"] if row else None

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
            "SELECT COUNT(*) AS n FROM outreach_events WHERE event_type = %s AND created_at LIKE %s",
            (event_type, day_prefix + "%"),
        ).fetchone()["n"]

    def lead_for_company(self, campaign_id: str, company_key: str) -> Lead | None:
        row = self.conn.execute(
            "SELECT data_json FROM leads WHERE campaign_id = %s AND company_key = %s "
            "ORDER BY updated_at DESC LIMIT 1", (campaign_id, company_key)
        ).fetchone()
        return Lead.model_validate_json(row["data_json"]) if row else None

    # -- suppressions ---------------------------------------------------------

    def add_suppression(self, value: str, kind: str, reason: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO suppressions (value, kind, reason, created_at) VALUES (%s, %s, %s, %s) "
            "ON CONFLICT (value) DO UPDATE SET kind = EXCLUDED.kind, reason = EXCLUDED.reason, "
            "created_at = EXCLUDED.created_at",
            (value.lower().strip(), kind, reason, utcnow().isoformat()),
        )
        self._commit()

    def is_suppressed(self, *values: str | None) -> bool:
        vals = [v.lower().strip() for v in values if v]
        if not vals:
            return False
        placeholders = ",".join("%s" for _ in vals)
        return self.conn.execute(
            f"SELECT 1 FROM suppressions WHERE value IN ({placeholders}) LIMIT 1", vals
        ).fetchone() is not None

    # -- drafts (human approval) ----------------------------------------------

    def get_draft(self, lead_id: str, step: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM drafts WHERE lead_id = %s AND step = %s", (lead_id, step)).fetchone()
        return dict(row) if row else None

    def upsert_draft(self, lead_id: str, step: str, subject: str, body: str, *,
                     status: str = "pending", edited: bool = False) -> dict:
        existing = self.get_draft(lead_id, step)
        created = existing["created_at"] if existing else utcnow().isoformat()
        approved_at = utcnow().isoformat() if status == "approved" else (existing or {}).get("approved_at")
        self.conn.execute(
            "INSERT INTO drafts (lead_id, step, subject, body, status, edited, created_at, approved_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (lead_id, step) DO UPDATE SET subject = EXCLUDED.subject, body = EXCLUDED.body, "
            "status = EXCLUDED.status, edited = EXCLUDED.edited, created_at = EXCLUDED.created_at, "
            "approved_at = EXCLUDED.approved_at",
            (lead_id, step, subject, body, status, int(edited), created, approved_at),
        )
        self._commit()
        return self.get_draft(lead_id, step)

    def set_draft_status(self, lead_id: str, step: str, status: str) -> None:
        self.conn.execute(
            "UPDATE drafts SET status = %s, approved_at = COALESCE(approved_at, %s) WHERE lead_id = %s AND step = %s",
            (status, utcnow().isoformat() if status == "approved" else None, lead_id, step),
        )
        self._commit()

    def drafts_by_status(self, status: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM drafts WHERE status = %s ORDER BY created_at", (status,))]

    def list_suppressions(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute("SELECT * FROM suppressions ORDER BY created_at DESC")]

    def remove_suppression(self, value: str) -> bool:
        cur = self.conn.execute("DELETE FROM suppressions WHERE value = %s", (value.lower().strip(),))
        self._commit()
        return cur.rowcount > 0

    # -- outreach events -----------------------------------------------------

    def add_event(self, lead_id: str, event_type: str, step: str | None = None,
                  detail: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO outreach_events (lead_id, event_type, step, detail, created_at) VALUES (%s, %s, %s, %s, %s)",
            (lead_id, event_type, step, detail, utcnow().isoformat()),
        )
        self._commit()

    def events_for(self, lead_id: str) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM outreach_events WHERE lead_id = %s ORDER BY event_id", (lead_id,)
        )]
