"""Campaign lead counts (the fast SQL aggregate behind /campaigns) and the CSV export filters.

The counts must stay correct after moving them from a full lead load to a COUNT query, and the
CSV must honour the same type + min-score filters the Leads table shows. DB-backed.
"""

import csv
import io

import pytest
from fastapi.testclient import TestClient

from conftest import bypass_auth
from gtm_engine.models import CompanyType, EmailStatus, Lead, Priority
from gtm_engine.storage.database import Database


def _lead(cid, name, ctype, score, ready):
    return Lead(campaign_id=cid, company_name=name, domain=f"{name}.pk".lower(), company_type=ctype,
                total_score=score, priority=Priority.QUALIFIED, contact_email=f"a@{name}.pk".lower(),
                email_status=EmailStatus.MX_VALID, outreach_ready=ready)


@pytest.fixture
def client(settings, tmp_path, monkeypatch):
    import gtm_engine.api.main as m
    monkeypatch.setattr(m, "_settings", settings)
    camp_dir = tmp_path / "campaigns"
    camp_dir.mkdir()
    # min_score 70, so "qualified" = BUYER with score >= 70.
    (camp_dir / "c.yaml").write_text(
        "campaign_id: test-retail\nname: T\noffer: x\nmin_score: 70\ngeography:\n  cities: [Lahore]\n"
        "osm_categories: [shop=clothes]\n", encoding="utf-8")
    monkeypatch.setattr(m, "CAMPAIGN_DIR", camp_dir)
    db = Database(settings.database_url)
    for l in [
        _lead("test-retail", "BuyerA", CompanyType.BUYER, 80, True),
        _lead("test-retail", "BuyerB", CompanyType.BUYER, 90, True),
        _lead("test-retail", "BuyerLow", CompanyType.BUYER, 50, False),
        _lead("test-retail", "VendorX", CompanyType.VENDOR, 95, False),
        _lead("test-retail", "UnknownY", CompanyType.UNKNOWN, 60, False),
    ]:
        db.save_lead(l, "r", l.domain)
    db.close()
    bypass_auth(m, monkeypatch)
    return TestClient(m.app)


def test_campaign_summary_counts_match_the_data(client):
    row = next(c for c in client.get("/campaigns").json() if c["campaign_id"] == "test-retail")
    assert row["leads"] == 5
    assert row["buyers"] == 3
    assert row["qualified"] == 2        # BUYER and score >= 70 (the 80 and 90, not the 50)
    assert row["outreach_ready"] == 2


def _rows(resp):
    assert resp.status_code == 200, resp.text
    return list(csv.DictReader(io.StringIO(resp.text)))


def test_export_defaults_to_qualified_buyers(client):
    rows = _rows(client.get("/campaigns/test-retail/export"))  # min_score 70, buyers_only default
    names = {r["company_name"] for r in rows}
    assert names == {"BuyerA", "BuyerB"}


def test_export_honours_company_type_filter(client):
    vendors = _rows(client.get("/campaigns/test-retail/export?min_score=0&company_type=VENDOR"))
    assert {r["company_name"] for r in vendors} == {"VendorX"}
    unknown = _rows(client.get("/campaigns/test-retail/export?min_score=0&company_type=UNKNOWN"))
    assert {r["company_name"] for r in unknown} == {"UnknownY"}


def test_export_all_types_when_no_type_and_not_buyers_only(client):
    everyone = _rows(client.get("/campaigns/test-retail/export?min_score=0&buyers_only=false"))
    assert len(everyone) == 5


def test_export_min_score_filters_rows(client):
    rows = _rows(client.get("/campaigns/test-retail/export?min_score=85&buyers_only=false"))
    assert {r["company_name"] for r in rows} == {"BuyerB", "VendorX"}  # only score >= 85
