"""Free-tier product limits: at most 3 campaigns per user, at most 10 leads per campaign.

Local/self-host operators (no auth, user_id None) are unlimited; these tests simulate a
signed-in user by overriding current_user_id.
"""

import pytest
from fastapi.testclient import TestClient

from conftest import bypass_auth
from gtm_engine.storage.database import Database


@pytest.fixture
def client(settings, tmp_path, monkeypatch):
    import gtm_engine.api.main as m
    from gtm_engine.api.auth import current_user_id
    monkeypatch.setattr(m, "_settings", settings)
    camp_dir = tmp_path / "campaigns"
    camp_dir.mkdir()
    monkeypatch.setattr(m, "CAMPAIGN_DIR", camp_dir)
    # Make sure the DB schema exists.
    Database(settings.database_url).close()
    bypass_auth(m, monkeypatch)
    # Simulate a signed-in user so the per-user quota applies.
    m.app.dependency_overrides[current_user_id] = lambda: "user-free-1"
    yield TestClient(m.app)
    m.app.dependency_overrides.pop(current_user_id, None)


def _create(client, name, max_companies=50):
    return client.post("/campaigns", json={
        "name": name, "offer": "x", "countries": ["Pakistan"], "provinces": [],
        "cities": ["Lahore"], "target_industries": [], "buyer_keywords": [],
        "osm_categories": [], "overture_categories": [], "min_score": 70,
        "max_companies": max_companies,
    })


def test_fourth_campaign_is_blocked(client):
    for i in range(3):
        assert _create(client, f"Camp {i}").status_code == 201
    r = _create(client, "Camp 4")
    assert r.status_code == 403
    assert "limited to 3 campaigns" in r.json()["detail"]


def test_max_companies_capped_at_ten_on_create(client):
    r = _create(client, "Capped", max_companies=200)
    assert r.status_code == 201
    cid = r.json()["campaign_id"]
    detail = client.get(f"/campaigns/{cid}").json()
    assert detail["max_companies"] == 10


def test_health_exposes_limits(client):
    limits = client.get("/health").json()["limits"]
    assert limits == {"max_campaigns": 3, "max_leads_per_campaign": 10}


def test_my_limits_reports_free_tier(client):
    r = client.get("/settings/limits").json()
    assert r == {"unlimited": False, "max_campaigns": 3, "max_leads_per_campaign": 10}


@pytest.fixture
def master_client(settings, tmp_path, monkeypatch):
    """A client acting as a master (unlimited) account via the UNLIMITED_EMAILS allowlist."""
    import gtm_engine.api.main as m
    from gtm_engine.api.auth import current_user_email, current_user_id
    monkeypatch.setattr(m, "_settings", settings)
    monkeypatch.setattr(m, "UNLIMITED_EMAILS", {"boss@example.com"})
    camp_dir = tmp_path / "campaigns"
    camp_dir.mkdir()
    monkeypatch.setattr(m, "CAMPAIGN_DIR", camp_dir)
    Database(settings.database_url).close()
    bypass_auth(m, monkeypatch)
    m.app.dependency_overrides[current_user_id] = lambda: "user-master"
    m.app.dependency_overrides[current_user_email] = lambda: "boss@example.com"
    yield TestClient(m.app)
    m.app.dependency_overrides.pop(current_user_id, None)
    m.app.dependency_overrides.pop(current_user_email, None)


def test_master_account_is_unlimited(master_client):
    # Well past the 3-campaign cap.
    for i in range(6):
        assert _create(master_client, f"Master {i}", max_companies=200).status_code == 201
    r = master_client.get("/settings/limits").json()
    assert r["unlimited"] is True
    # Lead cap is not clamped for a master account.
    cid = _create(master_client, "Big", max_companies=200).json()["campaign_id"]
    assert master_client.get(f"/campaigns/{cid}").json()["max_companies"] == 200
