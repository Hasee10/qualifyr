from pathlib import Path

import pytest

from gtm_engine.config.schema import CampaignConfig, DefaultRules, EngineSettings, GeographyConfig
from gtm_engine.config.loader import load_defaults

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def defaults() -> DefaultRules:
    return load_defaults()


@pytest.fixture
def campaign() -> CampaignConfig:
    return CampaignConfig(
        campaign_id="test-retail",
        name="Retail test",
        offer="Inventory automation",
        target_industries=["retail", "clothing", "fashion"],
        geography=GeographyConfig(countries=["Pakistan"], cities=["Islamabad", "Rawalpindi"]),
        target_roles=["founder", "ceo", "head of ecommerce"],
        buyer_keywords=["retailer", "store", "brand", "outlet", "online store", "shop"],
        osm_categories=["shop=clothes", "shop=furniture"],
        min_score=70,
        max_pages_per_site=4,
    )


@pytest.fixture
def settings(tmp_path: Path) -> EngineSettings:
    return EngineSettings(
        db_path=tmp_path / "test.sqlite",
        export_dir=tmp_path / "exports",
        per_host_delay_s=0.0,
        search_delay_s=0.0,
        max_retries=0,
        respect_robots=False,
        enable_search_fallback=False,
        overpass_url="https://overpass.test/api/interpreter",
        overpass_mirrors=[],
        email_verification="off",
        enable_domain_age=False,
        enable_news_signals=False,
        enable_intent_signals=False,
    )
