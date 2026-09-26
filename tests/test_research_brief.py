"""P5: the per-company research brief is grounded and covers the decision-maker."""

from gtm_engine.enrichment.research import build_research_brief
from gtm_engine.models import Classification, CompanyType, Contact, DiscoveredCompany, EmailStatus, Signals


def _company(**kw):
    return DiscoveredCompany(name=kw.pop("name", "Rakht"), source="osm", city=kw.pop("city", "Lahore"),
                             country="Pakistan", category=kw.pop("category", "shop=clothes"), **kw)


def test_brief_names_company_signals_and_decision_maker():
    company = _company()
    cls = Classification(company_type=CompanyType.BUYER, confidence=0.8, reasons=["buyer terms in identity: retailer"])
    contact = Contact(name="Ahmed Raza", role="CEO", email="ahmed@rakht.pk",
                      email_status=EmailStatus.DELIVERABLE, phone="0300 1234567", phone_type="mobile")
    signals = Signals(intent=[{"kind": "hiring", "text": "inventory manager", "relevance": ["inventory"]}],
                      job_openings=[{"title": "Inventory Manager", "growth_role": True}])
    brief = build_research_brief(company, cls, contact, signals, city="Lahore",
                                 industry="clothing", description="A clothing retailer with six outlets")

    assert "Rakht" in brief and "Lahore" in brief and "clothing retailer" in brief.lower()
    assert "Buyer:" in brief and "retailer" in brief
    assert "hiring" in brief and "inventory" in brief          # relevance surfaced
    assert "Ahmed Raza" in brief and "CEO" in brief and "confirmed" in brief   # decision-maker + verified email
    assert "0300 1234567" in brief


def test_brief_handles_no_contact():
    brief = build_research_brief(_company(), Classification(company_type=CompanyType.UNKNOWN),
                                 Contact(), Signals())
    assert "Rakht" in brief and "No public contact found" in brief


def test_brief_notes_unverified_email_without_a_name():
    contact = Contact(email="info@rakht.pk", email_status=EmailStatus.GENERIC)
    brief = build_research_brief(_company(), Classification(company_type=CompanyType.BUYER), contact, Signals())
    assert "info@rakht.pk" in brief and "generic" in brief and "no named decision-maker" in brief.lower()
