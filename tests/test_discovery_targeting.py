"""E1: the offer drives which map categories are searched, from a curated taxonomy so every
derived category is valid."""

from gtm_engine.discovery.targeting import (
    _niche_fallback, derive_discovery_targets, load_taxonomy, load_valid_osm_tags, match_sectors,
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


def test_valid_osm_tags_loads():
    tags = load_valid_osm_tags()
    assert "shop" in tags and "office" in tags and "craft" in tags
    assert "watches" in tags["shop"]
    assert "newspaper" in tags["office"]
    assert "watchmaker" in tags["craft"]


def test_niche_fallback_newspaper():
    tags = load_valid_osm_tags()
    result = _niche_fallback(["newspaper"], tags)
    assert not result.empty
    assert result.sectors == ["_niche"]
    assert "office=newspaper" in result.osm_categories


def test_niche_fallback_watchmaker():
    tags = load_valid_osm_tags()
    result = _niche_fallback(["watch repair"], tags)
    assert not result.empty
    osm_str = " ".join(result.osm_categories)
    assert "watches" in osm_str or "watchmaker" in osm_str


def test_niche_fallback_travel_agency():
    tags = load_valid_osm_tags()
    result = _niche_fallback(["travel agency"], tags)
    assert not result.empty
    assert any("travel" in t for t in result.osm_categories)


def test_niche_fallback_unknown_returns_overture_only():
    tags = load_valid_osm_tags()
    result = _niche_fallback(["quantum widgets"], tags)
    assert "quantum widgets" in result.overture_categories


async def test_derive_targets_niche_uses_fallback_not_general_retail():
    t = await derive_discovery_targets("Find newspaper offices in Islamabad",
                                       industries=["newspaper offices"])
    assert "_niche" in t.sectors or "office=newspaper" in t.osm_categories
    assert "general_retail" not in t.sectors


async def test_derive_targets_grocery_still_matches_taxonomy():
    t = await derive_discovery_targets("Find grocery stores in Islamabad",
                                       industries=["grocery stores"])
    assert "grocery_supermarket" in t.sectors
    assert "shop=supermarket" in t.osm_categories


async def test_seed_queries_include_areas():
    t = await derive_discovery_targets("Find newspaper offices near G-7 Islamabad",
                                       industries=["newspaper offices"],
                                       cities=["Islamabad"], areas=["G-7"])
    assert any("G-7" in q for q in t.search_queries)
