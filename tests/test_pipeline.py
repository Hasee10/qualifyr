"""End-to-end: mocked Overpass + three fake websites -> qualified CSV holds only the
retailer, once, with evidence and a score reason. Mirrors the Phase-1 acceptance test."""

import csv
import json

import httpx
import respx

from conftest import fixture
from gtm_engine.export.csv_export import write_csv
from gtm_engine.models import CSV_COLUMNS, CompanyType, Priority, SequenceStatus
from gtm_engine.pipeline import Pipeline
from gtm_engine.scraping.fetcher import HttpFetcher
from gtm_engine.storage.database import Database


class FakeMX:
    async def has_mx(self, domain: str) -> bool:
        return domain in {"zarafabrics.pk", "pixeldigital.pk"}


def _html(body: str) -> httpx.Response:
    return httpx.Response(200, text=body, headers={"content-type": "text/html; charset=utf-8"})


def _mock_world(settings):
    respx.get(url__startswith=settings.overpass_url).mock(
        return_value=httpx.Response(200, json=json.loads(fixture("overpass_islamabad.json"))))
    respx.get("https://www.zarafabrics.pk/").mock(return_value=_html(fixture("retailer_home.html")))
    respx.get("https://www.zarafabrics.pk/pages/about-us").mock(return_value=_html(fixture("retailer_about.html")))
    respx.get("https://www.zarafabrics.pk/pages/contact-us").mock(return_value=_html(fixture("retailer_contact.html")))
    respx.get("https://pixeldigital.pk/").mock(return_value=_html(fixture("agency_home.html")))
    respx.get("https://comingsoon-traders.pk/").mock(return_value=_html(fixture("thin_home.html")))
    respx.get(url__regex=r".*").mock(return_value=httpx.Response(404))


@respx.mock
async def test_full_run_matches_acceptance_criteria(campaign, settings, defaults, tmp_path):
    _mock_world(settings)
    campaign.geography.cities = ["Islamabad"]
    db = Database(settings.db_path)
    async with HttpFetcher(settings) as fetcher:
        pipeline = Pipeline(settings, defaults, db, fetcher, mx=FakeMX())
        result = await pipeline.run(campaign)

    s = result.stats
    assert s.discovered == 5 and s.after_dedupe == 4  # two Zara nodes merged by domain
    assert s.processed == 4 and s.errors == 0
    assert s.vendor == 1 and s.buyer >= 1

    by_name = {l.company_name: l for l in result.leads}
    zara = by_name["Zara Fabrics"]
    assert zara.company_type == CompanyType.BUYER
    assert zara.priority in (Priority.HIGH, Priority.QUALIFIED)
    assert zara.total_score >= campaign.min_score
    assert zara.contact_name == "Ahmed Raza" and zara.contact_email == "ahmed.raza@zarafabrics.pk"
    assert zara.email_status.value == "mx_valid"
    assert zara.outreach_ready is True
    assert zara.score_reason and zara.buyer_fit_reason
    assert zara.source_url.startswith("https://www.openstreetmap.org/")
    assert "shopify" in zara.technologies
    assert "sells online" in zara.personalization_hook

    pixel = by_name["Pixel Digital"]
    assert pixel.company_type == CompanyType.VENDOR and pixel.priority == Priority.REJECT and not pixel.outreach_ready

    thin = by_name["Comingsoon Traders"]
    assert thin.company_type in (CompanyType.UNKNOWN, CompanyType.BUYER)  # category match may lift it
    assert not thin.outreach_ready  # no email -> never outreach

    # Unnamed Mobile Shop had only a facebook "website": no domain, search disabled -> no website
    assert by_name["Unnamed Mobile Shop"].website is None and s.no_website == 1

    # No duplicate domains in output
    domains = [l.domain for l in result.leads if l.domain]
    assert len(domains) == len(set(domains))

    # CSV: exact columns, only qualified buyers
    qualified = [l for l in result.leads if l.company_type == CompanyType.BUYER and l.total_score >= campaign.min_score]
    out = write_csv(qualified, tmp_path / "q.csv")
    with out.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0].keys()) == CSV_COLUMNS
    assert {r["company_name"] for r in rows} == {"Zara Fabrics"}
    assert rows[0]["outreach_ready"] == "true"

    # Stored and queryable
    stored = db.list_leads(campaign.campaign_id, min_score=campaign.min_score, company_type="BUYER")
    assert [l.company_name for l in stored] == ["Zara Fabrics"]
    assert db.get_run(result.run_id)["status"] == "completed"
    db.close()


@respx.mock
async def test_rerun_updates_lead_in_place_and_respects_suppression(campaign, settings, defaults):
    _mock_world(settings)
    campaign.geography.cities = ["Islamabad"]
    db = Database(settings.db_path)
    async with HttpFetcher(settings) as fetcher:
        pipeline = Pipeline(settings, defaults, db, fetcher, mx=FakeMX())
        first = await pipeline.run(campaign)
        db.add_suppression("zarafabrics.pk", "domain", "asked not to be contacted")
        second = await pipeline.run(campaign)

    z1 = next(l for l in first.leads if l.company_name == "Zara Fabrics")
    z2 = next(l for l in second.leads if l.company_name == "Zara Fabrics")
    assert z1.lead_id == z2.lead_id
    assert z1.outreach_ready and not z2.outreach_ready
    assert z2.sequence_status == SequenceStatus.SUPPRESSED
    assert len(db.list_leads(campaign.campaign_id)) == len(second.leads)  # no duplicate rows
    db.close()
