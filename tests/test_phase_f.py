"""Phase F: Sheets mirror, suppression management, campaign YAML editor endpoints."""

import httpx
import pytest

from gtm_engine.export.sheets import EXTRA_COLUMNS, SheetsExporter, rows_for
from gtm_engine.models import CSV_COLUMNS, CompanyType, EmailStatus, Lead, Priority
from gtm_engine.storage.database import Database


def _lead(**kw) -> Lead:
    base = dict(campaign_id="test-retail", company_name="Zara Fabrics", domain="zarafabrics.pk", city="Islamabad",
                company_type=CompanyType.BUYER, total_score=88, priority=Priority.HIGH, contact_email="a@zarafabrics.pk",
                email_status=EmailStatus.MX_VALID, outreach_ready=True, phone_type="mobile", reply_label="interested")
    base.update(kw)
    return Lead(**base)


def test_rows_for_sheet_has_csv_columns_plus_extras():
    rows = rows_for([_lead(), _lead(company_name="MCC", domain_age_years=12.5)])
    assert rows[0] == CSV_COLUMNS + EXTRA_COLUMNS
    assert rows[1][CSV_COLUMNS.index("company_name")] == "Zara Fabrics"
    assert rows[1][len(CSV_COLUMNS) + EXTRA_COLUMNS.index("reply_label")] == "interested"
    assert rows[2][len(CSV_COLUMNS) + EXTRA_COLUMNS.index("domain_age_years")] == "12.5"
    assert all(len(r) == len(rows[0]) for r in rows)


def test_sheets_exporter_creates_tab_clears_and_writes():
    calls: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.url.path.endswith("/sheet123") and request.method == "GET":
            return httpx.Response(200, json={"sheets": [{"properties": {"title": "Sheet1"}}]})
        return httpx.Response(200, json={})
    client = httpx.Client(transport=httpx.MockTransport(handler), headers={"Authorization": "Bearer t"})
    n = SheetsExporter("sheet123", "t", client=client).replace("retail-isb-001", rows_for([_lead(), _lead()]))
    assert n == 2
    assert calls[0] == ("GET", "/v4/spreadsheets/sheet123")
    assert calls[1] == ("POST", "/v4/spreadsheets/sheet123:batchUpdate")     # tab did not exist -> created
    assert calls[2][1].endswith(":clear") and calls[3][0] == "PUT"


def test_suppression_list_and_removal(settings):
    db = Database(settings.db_path)
    db.add_suppression("Info@X.pk", "email", "test")
    db.add_suppression("bad.pk", "domain")
    rows = db.list_suppressions()
    assert {r["value"] for r in rows} == {"info@x.pk", "bad.pk"}
    assert db.remove_suppression("INFO@x.pk") and not db.remove_suppression("nope@x.pk")
    assert not db.is_suppressed("info@x.pk") and db.is_suppressed("bad.pk")
    db.close()


@pytest.fixture
def client(settings, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import gtm_engine.api.main as m
    monkeypatch.setattr(m, "_settings", settings)
    camp_dir = tmp_path / "campaigns"
    camp_dir.mkdir()
    (camp_dir / "one.yaml").write_text("campaign_id: one\nname: One\noffer: x\ngeography:\n  cities: [Lahore]\nosm_categories: [shop=clothes]\n", encoding="utf-8")
    monkeypatch.setattr(m, "CAMPAIGN_DIR", camp_dir)
    return TestClient(m.app), camp_dir


def test_campaign_yaml_roundtrip_and_validation(client):
    c, camp_dir = client
    got = c.get("/campaigns/one/yaml").json()
    assert got["file"] == "one.yaml" and "campaign_id: one" in got["yaml"]
    bad = c.post("/campaigns/validate", json={"yaml": "campaign_id: two\nname: T\noffer: x\nweights: {icp_fit: 90, company_quality: 15, buyer_evidence: 15, contact_quality: 10, buying_signals: 10}"}).json()
    assert bad["ok"] is False and "sum to 100" in bad["error"]
    ok = c.post("/campaigns/validate", json={"yaml": "campaign_id: two\nname: Two\noffer: x\ngeography:\n  cities: [Karachi]\nchamber_sources: [kcci]"}).json()
    assert ok["ok"] and ok["sources"] == ["kcci"]
    # mismatch between URL and YAML is refused
    assert c.put("/campaigns/one/yaml", json={"yaml": "campaign_id: two\nname: Two\noffer: x"}).status_code == 422
    # new campaign file is created
    r = c.put("/campaigns/two/yaml", json={"yaml": "campaign_id: two\nname: Two\noffer: x\ngeography:\n  cities: [Karachi]\nchamber_sources: [kcci]\n"})
    assert r.status_code == 200 and (camp_dir / "two.yaml").exists()
    assert {x["campaign_id"] for x in c.get("/campaigns").json()} == {"one", "two"}


def test_suppression_endpoints(client):
    c, _ = client
    assert c.post("/suppressions", json={"value": "Spam@X.pk", "reason": "asked"}).json()["value"] == "spam@x.pk"
    rows = c.get("/suppressions").json()
    assert rows[0]["value"] == "spam@x.pk" and rows[0]["kind"] == "email"
    assert c.delete("/suppressions/spam@x.pk").status_code == 200
    assert c.delete("/suppressions/spam@x.pk").status_code == 404


def test_sheets_status_and_guard(client, monkeypatch):
    c, _ = client
    monkeypatch.delenv("GTM_SHEETS_SPREADSHEET_ID", raising=False)
    assert c.get("/sheets/status").json()["configured"] is False
    assert c.post("/campaigns/one/export/sheets").status_code == 400
