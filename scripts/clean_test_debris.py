"""Remove rows the test suite wrote into the real database.

Background: the per-test schema isolation silently failed for one run (Supabase's
pooler drops the `options=-csearch_path=` startup parameter, so every test resolved
in `public`). Fixed in storage/database.py, but the rows it already wrote are still
there — and `outreach.yml` runs on a cron against this same database, so fake leads
are not merely untidy.

Prints what it would delete and exits. Pass --apply to actually delete.

    .venv\\Scripts\\python.exe scripts\\clean_test_debris.py
    .venv\\Scripts\\python.exe scripts\\clean_test_debris.py --apply
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg

from gtm_engine.config.loader import load_settings

# What the fixtures create. tests/conftest.py uses campaign_id "test-retail"; the lead
# factories in test_mailboxes/test_outreach use domains co0.pk .. co9.pk with contact
# addresses owner@coN.pk. Narrow on purpose — a broad "delete where domain like '%.pk'"
# would take real Pakistani prospects with it, which is the whole target market.
TEST_CAMPAIGNS = ("test-retail",)
TEST_EMAIL_PATTERN = r"^owner@co\d+\.pk$"
TEST_DOMAIN_PATTERN = r"^co\d+\.pk$"

PREVIEW = [
    ("leads (test campaign)",
     "SELECT count(*) FROM leads WHERE campaign_id = ANY(%s)"),
    ("leads (fixture domains, any campaign)",
     "SELECT count(*) FROM leads WHERE domain ~ %s OR contact_email ~ %s"),
    ("companies (test campaign)",
     "SELECT count(*) FROM companies WHERE campaign_id = ANY(%s)"),
    ("runs (test campaign)",
     "SELECT count(*) FROM runs WHERE campaign_id = ANY(%s)"),
    ("campaigns",
     "SELECT count(*) FROM campaigns WHERE campaign_id = ANY(%s)"),
    ("run_progress",
     "SELECT count(*) FROM run_progress WHERE campaign_id = ANY(%s)"),
    ("suppressions (fixture addresses)",
     "SELECT count(*) FROM suppressions WHERE value ~ %s"),
]


def main() -> None:
    apply = "--apply" in sys.argv
    dsn = load_settings().database_url
    if not dsn:
        sys.exit("GTM_DATABASE_URL is not set")

    with psycopg.connect(dsn, autocommit=False) as conn:
        print(f"{'what':42} {'rows':>6}")
        print("-" * 50)
        for label, sql in PREVIEW:
            params = ([list(TEST_CAMPAIGNS)] if "ANY" in sql
                      else [TEST_DOMAIN_PATTERN, TEST_EMAIL_PATTERN][: sql.count("%s")])
            n = conn.execute(sql, params).fetchone()[0]
            print(f"{label:42} {n:>6}")

        print("\nreal (non-test) leads that would be KEPT:")
        kept = conn.execute(
            "SELECT campaign_id, count(*) FROM leads "
            "WHERE NOT (campaign_id = ANY(%s)) AND NOT (domain ~ %s) "
            "GROUP BY campaign_id ORDER BY 2 DESC",
            [list(TEST_CAMPAIGNS), TEST_DOMAIN_PATTERN],
        ).fetchall()
        for row in kept or [("(none)", 0)]:
            print(f"  {row[0]:40} {row[1]:>6}")

        if not apply:
            print("\nPreview only. Re-run with --apply to delete.")
            return

        # Children first: outreach_events and drafts reference leads by lead_id.
        lead_ids = "SELECT lead_id FROM leads WHERE campaign_id = ANY(%s) OR domain ~ %s"
        args = [list(TEST_CAMPAIGNS), TEST_DOMAIN_PATTERN]
        conn.execute(f"DELETE FROM outreach_events WHERE lead_id IN ({lead_ids})", args)
        conn.execute(f"DELETE FROM drafts WHERE lead_id IN ({lead_ids})", args)
        conn.execute("DELETE FROM leads WHERE campaign_id = ANY(%s) OR domain ~ %s", args)
        conn.execute("DELETE FROM companies WHERE campaign_id = ANY(%s)", [list(TEST_CAMPAIGNS)])
        conn.execute("DELETE FROM run_progress WHERE campaign_id = ANY(%s)", [list(TEST_CAMPAIGNS)])
        conn.execute("DELETE FROM runs WHERE campaign_id = ANY(%s)", [list(TEST_CAMPAIGNS)])
        conn.execute("DELETE FROM campaigns WHERE campaign_id = ANY(%s)", [list(TEST_CAMPAIGNS)])
        conn.execute("DELETE FROM suppressions WHERE value ~ %s", [TEST_EMAIL_PATTERN])
        conn.commit()
        print("\ndeleted.")


if __name__ == "__main__":
    main()
