import json

import httpx
import respx

from conftest import fixture
from gtm_engine.discovery.geocode import NOMINATIM_URL, BBox, Geocoder
from gtm_engine.discovery.osm import OSMDiscovery, build_query, element_to_company, tag_filter
from gtm_engine.discovery.search import WebsiteFinder, name_matches, parse_results
from gtm_engine.scraping.fetcher import HttpFetcher


def test_tag_filter():
    assert tag_filter("shop=clothes") == '["shop"="clothes"]'
    assert tag_filter("shop=*") == '["shop"]'
    assert tag_filter("amenity") == '["amenity"]'


def test_build_query_uses_bbox_and_categories():
    q = build_query(BBox(33.5, 72.8, 33.8, 73.2), ["shop=clothes", "shop=*"], 60)
    assert 'nwr["shop"="clothes"]["name"](33.5,72.8,33.8,73.2);' in q
    assert 'nwr["shop"]["name"](33.5,72.8,33.8,73.2);' in q
    assert "[timeout:60]" in q
    assert "out center tags" in q


def test_element_to_company_maps_tags():
    el = json.loads(fixture("overpass_islamabad.json"))["elements"][0]
    c = element_to_company(el, "Islamabad", "Pakistan", None)
    assert c.name == "Zara Fabrics"
    assert c.website == "https://www.zarafabrics.pk/"
    assert c.category == "shop=clothes"
    assert c.phone == "+92 51 2345678"
    assert c.address == "Blue Area, Islamabad"
    assert c.source_url == "https://www.openstreetmap.org/node/1"


def test_element_without_name_is_dropped():
    assert element_to_company({"type": "node", "id": 5, "tags": {"shop": "clothes"}}, "X", "PK", None) is None


def _mock_nominatim():
    return respx.get(url__startswith=NOMINATIM_URL).mock(
        return_value=httpx.Response(200, json=[{"boundingbox": ["33.5", "33.8", "72.8", "73.2"]}]))


@respx.mock
async def test_geocoder_caches_to_disk(settings, tmp_path):
    route = _mock_nominatim()
    cache = tmp_path / "geo.json"
    async with HttpFetcher(settings) as fetcher:
        g = Geocoder(fetcher, cache)
        box = await g.bbox("Islamabad", "Pakistan")
        assert box == BBox(33.5, 72.8, 33.8, 73.2)
        assert await Geocoder(HttpFetcher(settings), cache).bbox("Islamabad", "Pakistan") == box
    assert route.call_count == 1


@respx.mock
async def test_osm_discovery_yields_companies(campaign, settings):
    _mock_nominatim()
    respx.get(url__startswith=settings.overpass_url).mock(
        return_value=httpx.Response(200, json=json.loads(fixture("overpass_islamabad.json")))
    )
    async with HttpFetcher(settings) as fetcher:
        found = [c async for c in OSMDiscovery(fetcher, settings).discover(campaign)]
    # 5 named elements x 2 cities (same mocked response), unnamed one dropped
    assert len(found) == 10
    assert all(c.source == "osm" for c in found)
    assert {c.city for c in found} == {"Islamabad", "Rawalpindi"}


@respx.mock
async def test_osm_failure_is_empty_not_exception(campaign, settings):
    _mock_nominatim()
    respx.get(url__startswith=settings.overpass_url).mock(return_value=httpx.Response(504))
    async with HttpFetcher(settings) as fetcher:
        found = [c async for c in OSMDiscovery(fetcher, settings).discover(campaign)]
    assert found == []


# --- search fallback -----------------------------------------------------------

DDG_HTML = """
<html><body>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.facebook.com%2Fkhaadi">Khaadi - Facebook</a>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.daraz.pk%2Fkhaadi">Khaadi on Daraz</a>
<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.khaadi.com%2Fpk%2F">Khaadi | Official Online Store</a>
</body></html>
"""


def test_parse_results_unwraps_redirects():
    res = parse_results(DDG_HTML)
    assert res[0][0] == "https://www.facebook.com/khaadi"
    assert res[2] == ("https://www.khaadi.com/pk/", "Khaadi | Official Online Store")


def test_name_matches_is_conservative():
    assert name_matches("Khaadi", "khaadi.com", None)
    assert name_matches("Al Fatah Electronics", "alfatah.pk", None)
    assert not name_matches("Al Fatah Electronics", "electronics.pk", "Electronics store")
    assert name_matches("Sapphire Retail", "sapphireonline.pk", "Sapphire | Online Store")
    assert not name_matches("Sapphire Retail", "random.pk", "Buy stuff online")


@respx.mock
async def test_website_finder_skips_directories(campaign, settings):
    settings.enable_search_fallback = True
    respx.get(url__startswith="https://html.duckduckgo.com/html/").mock(return_value=httpx.Response(200, text=DDG_HTML))
    async with HttpFetcher(settings) as fetcher:
        found = await WebsiteFinder(fetcher, settings).find("Khaadi", "Lahore", "Pakistan")
    assert found == "https://khaadi.com"


async def test_website_finder_disabled(settings):
    async with HttpFetcher(settings) as fetcher:
        assert await WebsiteFinder(fetcher, settings).find("Khaadi", None, None) is None


def test_osm_city_is_the_searched_city_not_urdu_tag():
    el = {"type": "node", "id": 9, "tags": {"name": "Bata", "shop": "shoes", "addr:city": "راولپنڈی"}}
    c = element_to_company(el, "Rawalpindi", "Pakistan", None)
    assert c.city == "Rawalpindi" and c.extra["addr_city"] == "راولپنڈی"


def test_name_matches_label_inside_name():
    assert name_matches("ElectricStorePk Electric Store", "electricstore.pk", None)
    assert not name_matches("XS Mobile", "whatmobile.com.pk", "WhatMobile - phone prices")
    assert not name_matches("Food 24 Hours", "archivesouthasia.com", None)
