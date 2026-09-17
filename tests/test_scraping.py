import httpx
import respx

from conftest import fixture
from gtm_engine.scraping.fetcher import HttpFetcher
from gtm_engine.scraping.parsers import classify_link, extract_phones, parse_page
from gtm_engine.scraping.site_crawler import SiteCrawler


def test_parse_retailer_home():
    page = parse_page("https://www.zarafabrics.pk/", fixture("retailer_home.html"))
    assert page.title.startswith("Zara Fabrics")
    assert "clothing retailer" in page.description
    assert page.internal_links["about"] == "https://www.zarafabrics.pk/pages/about-us"
    assert page.internal_links["contact"] == "https://www.zarafabrics.pk/pages/contact-us"
    assert page.internal_links["careers"] == "https://www.zarafabrics.pk/pages/careers"
    assert page.social["facebook"] == "https://www.facebook.com/zarafabricspk"
    assert page.social["whatsapp"].startswith("https://wa.me/")
    assert "script" not in page.text.lower()
    assert page.phones and "051-2345678" in page.phones[0]


def test_parse_about_finds_team_pairs():
    page = parse_page("https://www.zarafabrics.pk/pages/about-us", fixture("retailer_about.html"))
    assert ("Ahmed Raza", "Founder & CEO") in page.team
    assert ("Sana Malik", "Head of Ecommerce") in page.team
    assert ("Bilal Khan", "Sales Executive") in page.team
    assert page.social["linkedin"] == "https://www.linkedin.com/company/zara-fabrics"


def test_parse_contact_prefers_mailto():
    page = parse_page("https://www.zarafabrics.pk/pages/contact-us", fixture("retailer_contact.html"))
    assert page.emails == ["info@zarafabrics.pk", "ahmed.raza@zarafabrics.pk"]


def test_classify_link_by_text_and_path():
    assert classify_link("https://x.pk/some-opaque-id", "About Us") == "about"
    assert classify_link("https://x.pk/pages/contact-us", "") == "contact"
    assert classify_link("https://x.pk/blog", "Blog") is None


def test_extract_phones_ignores_prices():
    text = "Price Rs. 1299 - Call 0300 1234567 or +92 51 2345678. Order #123456789012345"
    phones = extract_phones(text)
    assert "0300 1234567" in phones
    assert any("2345678" in p for p in phones)
    assert not any("1299" == p for p in phones)


def _mock_site(base: str = "https://www.zarafabrics.pk"):
    respx.get(f"{base}/").mock(return_value=httpx.Response(200, text=fixture("retailer_home.html"), headers={"content-type": "text/html"}))
    respx.get(f"{base}/pages/about-us").mock(return_value=httpx.Response(200, text=fixture("retailer_about.html"), headers={"content-type": "text/html"}))
    respx.get(f"{base}/pages/contact-us").mock(return_value=httpx.Response(200, text=fixture("retailer_contact.html"), headers={"content-type": "text/html"}))
    respx.get(url__regex=rf"{base}/.*").mock(return_value=httpx.Response(404))


@respx.mock
async def test_crawler_collects_key_pages(settings):
    _mock_site()
    async with HttpFetcher(settings) as fetcher:
        snap = await SiteCrawler(fetcher, max_pages=6).crawl("https://www.zarafabrics.pk")
    assert snap.reachable and snap.https
    assert {"home", "about", "contact"} <= set(snap.pages)
    assert snap.emails[0] == "info@zarafabrics.pk"
    assert ("Ahmed Raza", "Founder & CEO") in snap.team
    assert "linkedin" in snap.social


@respx.mock
async def test_crawler_respects_page_budget(settings):
    _mock_site()
    async with HttpFetcher(settings) as fetcher:
        snap = await SiteCrawler(fetcher, max_pages=2).crawl("https://www.zarafabrics.pk")
    assert set(snap.pages) == {"home", "about"}


@respx.mock
async def test_crawler_unreachable(settings):
    respx.get(url__regex=r"https://dead\.pk.*").mock(side_effect=httpx.ConnectError("boom"))
    respx.get(url__regex=r"http://dead\.pk.*").mock(side_effect=httpx.ConnectError("boom"))
    async with HttpFetcher(settings) as fetcher:
        snap = await SiteCrawler(fetcher).crawl("https://dead.pk")
    assert not snap.reachable and snap.error.startswith("http_error")


@respx.mock
async def test_fetcher_retries_then_gives_up(settings):
    settings.max_retries = 1
    route = respx.get("https://flaky.pk/").mock(return_value=httpx.Response(503))
    async with HttpFetcher(settings) as fetcher:
        res = await fetcher.get("https://flaky.pk/")
    assert route.call_count == 2 and not res.ok


@respx.mock
async def test_fetcher_honours_robots(settings):
    settings.respect_robots = True
    respx.get("https://private.pk/robots.txt").mock(return_value=httpx.Response(200, text="User-agent: *\nDisallow: /\n", headers={"content-type": "text/plain"}))
    page = respx.get("https://private.pk/").mock(return_value=httpx.Response(200, text="<html></html>"))
    async with HttpFetcher(settings) as fetcher:
        res = await fetcher.get("https://private.pk/")
    assert res.error == "robots_disallowed" and page.call_count == 0


def test_team_extractor_ignores_product_headings():
    html = """<div><h3>BIRTHDAY ITEMS</h3><p>Biscuits &amp; Cookies</p></div>
    <div><h3>Almond Gifts</h3><p>Premium pack</p></div>
    <div><h3>Ahmed Raza</h3><p>Chief Operating Officer</p></div>
    <div><h3>Sara Khan</h3><p>COO</p></div>"""
    page = parse_page("https://x.pk/", html)
    assert page.team == [("Ahmed Raza", "Chief Operating Officer"), ("Sara Khan", "COO")]


def test_inline_decision_maker_patterns():
    html = """<p>Founded in 2010 by Ahmed Raza, CEO of the company, Zara Fabrics now has six outlets.
    Our Managing Director: Sana Malik oversees operations. Contact - Support team for help.</p>"""
    page = parse_page("https://x.pk/about", html)
    assert ("Ahmed Raza", "CEO") in page.team
    assert ("Sana Malik", "Managing Director") in page.team
    assert all("Support" not in n for n, _ in page.team)
