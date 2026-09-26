"""E1: the offer drives which map categories are searched, from a curated taxonomy so every
derived category is valid."""

from gtm_engine.discovery.targeting import (
    derive_discovery_targets, load_taxonomy, match_sectors,
)


class FakeLLM:
    name = "fake"

    def __init__(self, reply: str):
        self.reply = reply

    async def complete(self, system, user, *, max_tokens=400):
        return self.reply


def test_taxonomy_loads_with_known_sectors():
    tax = load_taxonomy()
    assert "clothing_apparel" in tax and "electronics" in tax and "general_retail" in tax
    assert "shop=clothes" in tax["clothing_apparel"]["osm"]


def test_match_sectors_from_offer_text():
    tax = load_taxonomy()
    assert "clothing_apparel" in match_sectors("inventory software for clothing brands", None, tax)
    assert "electronics" in match_sectors("POS for mobile phone shops", None, tax)
    # A specific match must not also drag in the broad general_retail fallback.
    assert "general_retail" not in match_sectors("apparel retailers", None, tax)


def test_match_sectors_falls_back_to_general_retail():
    tax = load_taxonomy()
    assert match_sectors("software for shops and outlets", None, tax) == ["general_retail"]
    assert match_sectors("quantum widgets for nobody", None, tax) == []


async def test_derive_targets_deterministic_expands_to_valid_categories():
    t = await derive_discovery_targets("inventory software for clothing and footwear retailers", ["fashion"])
    assert "shop=clothes" in t.osm_categories and "shop=shoes" in t.osm_categories
    assert "clothing" in t.overture_categories
    assert set(t.sectors) >= {"clothing_apparel", "footwear"}


async def test_derive_targets_never_leaves_an_offer_empty():
    t = await derive_discovery_targets("some very niche B2B thing")
    assert not t.empty and t.sectors == ["general_retail"]  # always something to search


async def test_llm_widens_sectors_but_only_valid_keys():
    # The model suggests one valid sector and one nonsense key; only the valid one is kept.
    llm = FakeLLM('["furniture_home", "made_up_sector"]')
    t = await derive_discovery_targets("home fit-out services", None, llm)
    assert "furniture_home" in t.sectors and "made_up_sector" not in t.sectors
    assert "shop=furniture" in t.osm_categories


async def test_no_offer_returns_empty():
    t = await derive_discovery_targets("")
    assert t.empty and t.sectors == []
