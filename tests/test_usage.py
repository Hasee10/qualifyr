from gtm_engine.api import usage as usage_api
from gtm_engine.storage.database import Database


def test_daily_cap_enforced_without_monthly_limit(pg_schema):
    db = Database(pg_schema())
    for _ in range(3):
        assert db.check_and_increment_usage("u1", "brave", limit=3) is True
    assert db.check_and_increment_usage("u1", "brave", limit=3) is False


def test_monthly_cap_enforced_independently_of_daily(pg_schema):
    db = Database(pg_schema())
    # Daily limit is generous; monthly limit of 2 should bite first.
    assert db.check_and_increment_usage("u1", "runs", limit=100, monthly_limit=2) is True
    assert db.check_and_increment_usage("u1", "runs", limit=100, monthly_limit=2) is True
    assert db.check_and_increment_usage("u1", "runs", limit=100, monthly_limit=2) is False


def test_daily_cap_bites_even_under_a_generous_monthly_cap(pg_schema):
    db = Database(pg_schema())
    assert db.check_and_increment_usage("u1", "runs", limit=1, monthly_limit=100) is True
    assert db.check_and_increment_usage("u1", "runs", limit=1, monthly_limit=100) is False


def test_get_usage_reports_daily_and_monthly_counts(pg_schema):
    db = Database(pg_schema())
    db.check_and_increment_usage("u1", "runs", limit=10, monthly_limit=10)
    db.check_and_increment_usage("u1", "runs", limit=10, monthly_limit=10)
    rows = {r["resource"]: r for r in db.get_usage("u1")}
    assert rows["runs"]["daily_count"] == 2
    assert rows["runs"]["monthly_count"] == 2


def test_check_usage_passes_through_monthly_limit_for_runs(pg_schema, monkeypatch):
    db = Database(pg_schema())
    monkeypatch.setattr(usage_api, "MONTHLY_LIMITS", {"runs": 2})
    monkeypatch.setattr(usage_api, "MONTHLY_MAX_LIMITS", {"runs": 20})
    assert usage_api.check_usage(db, "u1", "runs") is True
    assert usage_api.check_usage(db, "u1", "runs") is True
    assert usage_api.check_usage(db, "u1", "runs") is False


def test_monthly_limit_none_for_resources_without_a_monthly_cap():
    # places intentionally has no monthly cap yet - see comment in api/usage.py.
    assert usage_api._monthly_limit("places") is None
    assert usage_api._monthly_limit("brave") is None
    assert usage_api._monthly_limit("runs") == usage_api.MONTHLY_LIMITS["runs"]


def test_get_all_usage_includes_monthly_fields_only_for_capped_resources(pg_schema):
    db = Database(pg_schema())
    usage_api.check_usage(db, "u1", "runs")
    report = usage_api.get_all_usage(db, "u1")
    assert "monthly_count" in report["runs"]
    assert "monthly_limit" in report["runs"]
    assert "monthly_count" not in report["brave"]
