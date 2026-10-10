"""P4 tier dataclass: three tiers, resolver with fallback, env-var back-compat for free tier."""

from gtm_engine.pricing.tiers import (
    ENTERPRISE, FREE, PRO, TIERS, allowed_per_run_for, resolved_max_campaigns,
    resolved_monthly_credits, tier_for,
)


def test_three_tiers_only():
    assert set(TIERS.keys()) == {"free", "pro", "enterprise"}


def test_prices_match_ceo_direction():
    assert FREE.price_usd_per_month == 0
    assert PRO.price_usd_per_month == 30
    assert ENTERPRISE.price_usd_per_month == 50


def test_free_is_byok_only():
    assert FREE.byok_only is True
    assert PRO.byok_only is False
    assert ENTERPRISE.byok_only is False


def test_credits_scale_with_tier():
    assert FREE.monthly_credits < PRO.monthly_credits < ENTERPRISE.monthly_credits


def test_allowed_per_run_includes_3_5_10_everywhere():
    for t in TIERS.values():
        assert {3, 5, 10}.issubset(set(t.allowed_leads_per_run))


def test_pro_and_enterprise_have_bigger_per_run_options():
    assert 50 in PRO.allowed_leads_per_run
    assert 100 in ENTERPRISE.allowed_leads_per_run
    assert 100 not in PRO.allowed_leads_per_run


def test_tier_for_resolves_known_names_case_insensitive():
    assert tier_for("free") is FREE
    assert tier_for("PRO") is PRO
    assert tier_for("Enterprise") is ENTERPRISE


def test_tier_for_falls_back_to_free_on_unknown_or_none():
    assert tier_for(None) is FREE
    assert tier_for("") is FREE
    assert tier_for("unknown_tier") is FREE


def test_env_override_for_free_max_campaigns(monkeypatch):
    monkeypatch.setenv("GTM_FREE_MAX_CAMPAIGNS", "7")
    assert resolved_max_campaigns(FREE) == 7
    # Paid tiers are not overrideable via this env var.
    assert resolved_max_campaigns(PRO) == PRO.max_campaigns


def test_env_override_for_free_monthly_credits(monkeypatch):
    monkeypatch.setenv("GTM_FREE_MONTHLY_CREDITS", "100")
    assert resolved_monthly_credits(FREE) == 100
    assert resolved_monthly_credits(ENTERPRISE) == ENTERPRISE.monthly_credits


def test_allowed_per_run_is_sorted():
    for t in TIERS.values():
        assert allowed_per_run_for(t) == sorted(allowed_per_run_for(t))


def test_tier_is_frozen_dataclass():
    import dataclasses
    assert dataclasses.is_dataclass(FREE)
    # Frozen means attempts to mutate raise FrozenInstanceError.
    import pytest
    with pytest.raises(Exception):
        FREE.monthly_credits = 999  # type: ignore[misc]
