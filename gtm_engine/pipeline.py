"""End-to-end run for one campaign:
discover -> dedupe -> find website -> crawl -> classify -> enrich -> validate -> score -> store.
Each company is processed independently so one bad site never stalls the batch."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from gtm_engine.config.schema import CampaignConfig, DefaultRules, EngineSettings
from gtm_engine.discovery.chambers import KCCIDirectory
from gtm_engine.discovery.csv_seed import CSVSeedDiscovery
from gtm_engine.discovery.osm import OSMDiscovery
from gtm_engine.discovery.overture import OvertureDiscovery
from gtm_engine.discovery.search import WebsiteFinder
from gtm_engine.enrichment.contacts import choose_contact
from gtm_engine.enrichment.email_patterns import discover, infer_pattern
from gtm_engine.enrichment.external_signals import NewsChecker, domain_age
from gtm_engine.enrichment.phones import classify_phone
from gtm_engine.enrichment.signals import assess_quality, detect_signals, summarize
from gtm_engine.models import (
    Classification, CompanyQuality, CompanyType, Contact, DiscoveredCompany, EmailStatus, Lead,
    SequenceStatus, Signals, new_id,
)
from gtm_engine.qualification.buyer_classifier import BuyerClassifier, TextBundle
from gtm_engine.scoring.scoring import ScoreInputs, is_outreach_ready, score_lead
from gtm_engine.scraping.fetcher import Fetcher, HttpFetcher
from gtm_engine.scraping.site_crawler import SiteCrawler, SiteSnapshot
from gtm_engine.storage.database import Database
from gtm_engine.validation.dedupe import dedupe_companies
from gtm_engine.validation.domains import canonical_domain, company_key
from gtm_engine.validation.emails import MXChecker, classify_email, is_generic_mailbox
from gtm_engine.validation.verifier import EmailVerifier, MxOnlyVerifier, VerifyStatus, build_verifier

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, int, int, str], Awaitable[None] | None]


@dataclass
class RunStats:
    discovered: int = 0
    after_dedupe: int = 0
    processed: int = 0
    no_website: int = 0
    unreachable: int = 0
    buyer: int = 0
    vendor: int = 0
    unknown: int = 0
    qualified: int = 0
    outreach_ready: int = 0
    suppressed: int = 0
    duplicates: int = 0
    chains_excluded: int = 0
    errors: int = 0

    def as_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class RunResult:
    run_id: str
    campaign_id: str
    stats: RunStats
    leads: list[Lead] = field(default_factory=list)


def build_personalization_hook(company: DiscoveredCompany, cls: Classification, signals: Signals) -> str | None:
    """Only facts we observed. Nothing invented."""
    facts: list[str] = []
    if company.city:
        facts.append(f"based in {company.city}")
    if "ecommerce_active" in signals.buying:
        facts.append("sells online")
    if "operations_scale" in signals.buying:
        facts.append("operates multiple branches/outlets")
    if "hiring" in signals.buying:
        facts.append("currently hiring")
    if "expansion" in signals.buying:
        facts.append("recently expanding")
    tech = [t for t in signals.technologies if t in ("shopify", "woocommerce", "magento")]
    if tech:
        facts.append(f"runs on {tech[0]}")
    if "customer_service_load" in signals.pain:
        facts.append("takes orders over WhatsApp/DM")
    if signals.news:
        facts.append(f"recently in the news ({signals.news[0].get('source', '')})")
    if signals.domain_age_years is not None and signals.domain_age_years < 2:
        facts.append("recently launched online")
    return "; ".join(facts) if facts else None


class Pipeline:
    def __init__(self, settings: EngineSettings, defaults: DefaultRules, db: Database,
                 fetcher: Fetcher, mx: MXChecker | None = None, verifier: EmailVerifier | None = None):
        self.settings = settings
        self.defaults = defaults
        self.db = db
        self.fetcher = fetcher
        self.mx = mx if mx is not None else MXChecker(settings.dns_timeout_s)
        self.verifier = verifier
        self.website_finder = WebsiteFinder(fetcher, settings)
        self.news = NewsChecker(fetcher)
        self._news_budget = settings.news_max_companies_per_run

    async def _verifier(self) -> EmailVerifier:
        if self.verifier is None:
            self.verifier = await build_verifier(self.settings.email_verification, self.settings.reacher_url)
            log.info("email verifier: %s", self.verifier.name)
        return self.verifier

    # -- discovery ---------------------------------------------------------------

    async def discover(self, campaign: CampaignConfig, progress: ProgressFn | None = None) -> list[DiscoveredCompany]:
        sources = []
        if campaign.overture_categories and campaign.geography.cities:
            sources.append(OvertureDiscovery(self.fetcher, self.settings))
        if campaign.osm_categories and campaign.geography.cities:
            sources.append(OSMDiscovery(self.fetcher, self.settings))
        if "kcci" in campaign.chamber_sources:
            sources.append(KCCIDirectory(self.fetcher, self.settings))
        if campaign.seed_csv:
            sources.append(CSVSeedDiscovery(campaign.seed_csv))
        if not sources:
            log.warning("no discovery sources configured (need osm_categories+cities or seed_csv)")
        found: list[DiscoveredCompany] = []
        for src in sources:
            async for company in src.discover(campaign):
                found.append(company)
            await _emit(progress, "discover", len(found), 0, f"{src.name}: {len(found)} so far")
        return found

    # -- single company ----------------------------------------------------------

    async def process_company(self, company: DiscoveredCompany, campaign: CampaignConfig,
                              classifier: BuyerClassifier, run_id: str, stats: RunStats,
                              seen_keys: set[str] | None = None) -> Lead | None:
        """Returns None when the company turns out to duplicate one already processed
        in this run (its website, found by search, belongs to an earlier company)."""
        website = company.website
        if not website:
            website = await self.website_finder.find(company.name, company.city, company.country)
            if website:
                company = company.model_copy(update={"website": website, "domain": canonical_domain(website),
                                                     "source": f"{company.source}+search"})
        domain = company.domain or canonical_domain(website)
        key = company_key(domain, company.name, company.city)
        if seen_keys is not None:
            if key in seen_keys:
                stats.duplicates += 1
                log.info("skipping %s: %s already processed this run", company.name, key)
                return None
            seen_keys.add(key)
        self.db.upsert_company(key, campaign.campaign_id, company.name, domain=domain, website=website,
                               country=company.country, city=company.city, source=company.source,
                               source_url=company.source_url, raw=company.model_dump(mode="json"))

        if not website:
            stats.no_website += 1
            snapshot = SiteSnapshot(website="", final_url=None, reachable=False, https=False, error="no_website")
        else:
            crawler = SiteCrawler(self.fetcher, campaign.max_pages_per_site)
            snapshot = await crawler.crawl(website)
            if not snapshot.reachable:
                stats.unreachable += 1
            for kind, page in snapshot.pages.items():
                self.db.save_page(key, page.url, kind, 200, page.title, page.text[:5000])

        home = snapshot.pages.get("home")
        about = snapshot.pages.get("about")
        bundle = TextBundle(
            name=company.name,
            title=home.title if home else None,
            description=(home.description if home else None) or (about.description if about else None),
            about_text=(about.text if about else None) or (home.text if home else None),
            body_text=snapshot.all_text,
            category=company.category,
            site_reachable=snapshot.reachable,
        )
        cls = classifier.classify(bundle)
        quality = assess_quality(snapshot, company.name, domain)
        signals = detect_signals(snapshot, self.defaults) if snapshot.reachable else Signals()
        provenance: dict[str, str] = {"company": f"{company.source}: {company.source_url or 'record'}"}
        if snapshot.reachable:
            contact = choose_contact(snapshot, campaign, self.defaults, domain)
            if contact.email:
                provenance["contact_email"] = contact.email_source or "website"
            if contact.name:
                provenance["contact_name"] = f"team/about page: {contact.source_url}"
            if contact.phone:
                provenance["phone"] = "website"
        else:
            src_phone = classify_phone(company.phone)
            contact = Contact(
                email=company.email, phone=company.phone,
                phone_type=src_phone.kind if src_phone else None,
                email_status=EmailStatus.UNVERIFIED if company.email else EmailStatus.NONE,
                email_source=f"{company.source} record" if company.email else None,
                evidence="from discovery source only",
            )
            if company.email:
                provenance["contact_email"] = f"{company.source} record"
        rep = company.extra.get("representative")
        if rep and not contact.name:
            contact.name, contact.role = rep, f"Member representative ({company.source.upper()})"
            contact.is_decision_maker = True
            contact.evidence = f"registered representative in the {company.source.upper()} member directory"
            provenance["contact_name"] = f"{company.source} directory: {company.source_url}"
        # Discovery-source contact details fill gaps the website did not (waterfall).
        if not contact.email and company.email:
            contact.email = company.email
            contact.email_source = f"{company.source} record"
            provenance["contact_email"] = f"{company.source} record"
        if not contact.phone and company.phone:
            p = classify_phone(company.phone)
            contact.phone, contact.phone_type = company.phone, (p.kind if p else None)
            provenance["phone"] = f"{company.source} record"

        if cls.company_type != CompanyType.VENDOR and contact.email:
            contact.email_status = await classify_email(contact.email, self.defaults.generic_email_prefixes, self.mx)

        # Decision-maker email discovery: a named person but only a generic mailbox (or none).
        if (cls.company_type == CompanyType.BUYER and self.settings.discover_decision_maker_email
                and contact.is_decision_maker and contact.name and domain
                and contact.email_status in (EmailStatus.GENERIC, EmailStatus.NONE, EmailStatus.INVALID)):
            verifier = await self._verifier()
            known = [e for e in snapshot.emails if e.endswith("@" + domain)
                     and not is_generic_mailbox(e, self.defaults.generic_email_prefixes)]
            known_pattern = next((p for e in known for p in [infer_pattern(e, contact.name)] if p), None)
            found = await discover(contact.name, domain, verifier, known_pattern=known_pattern,
                                   generic_prefixes=self.defaults.generic_email_prefixes)
            provenance["email_discovery"] = f"{verifier.name}: {found.reason}; tried {found.tried}"
            if found.status == VerifyStatus.DELIVERABLE and found.email:
                contact.email, contact.email_status = found.email, EmailStatus.DELIVERABLE
                contact.email_pattern = found.pattern
                contact.email_source = f"pattern {found.pattern}, confirmed by {verifier.name}"
                provenance["contact_email"] = contact.email_source
            elif found.email:
                # Keep the generic mailbox as the sendable address; surface the guess for the reviewer.
                contact.candidate_email = found.email
                contact.email_pattern = found.pattern

        if cls.company_type == CompanyType.BUYER and snapshot.reachable:
            if self.settings.enable_domain_age and domain:
                age = await domain_age(self.fetcher, domain)
                if age:
                    signals.domain_age_years, signals.domain_age_note = age.years, age.note or None
                    provenance["domain_age"] = f"{age.source}: {age.note or f'registered {age.registered:%Y-%m-%d}'}"
            if self.settings.enable_news_signals and self._news_budget > 0:
                self._news_budget -= 1
                mentions = await self.news.mentions(company.name, company.country or "Pakistan")
                if mentions:
                    signals.news = [m.__dict__ for m in mentions]
                    signals.buying.setdefault("news_mention", []).extend(m.title for m in mentions[:2])
                    provenance["news"] = f"gdelt: {len(mentions)} article(s), latest {mentions[0].date}"

        score = score_lead(ScoreInputs(company, cls, quality, contact, signals), campaign)
        ready = is_outreach_ready(cls, score, contact, campaign)
        suppressed = self.db.is_suppressed(domain, contact.email)
        if suppressed:
            ready = False
            stats.suppressed += 1

        buying, pain = summarize(signals)
        description = bundle.description or (about.text[:300] if about else None) or (home.text[:300] if home else None)
        lead = Lead(
            campaign_id=campaign.campaign_id,
            company_name=company.name,
            domain=domain,
            website=snapshot.final_url or website,
            country=company.country,
            city=company.city,
            address=company.address,
            industry=company.category,
            company_description=description,
            company_type=cls.company_type,
            buyer_fit_score=score.icp_fit + score.buyer_evidence,
            buyer_fit_reason="; ".join(cls.reasons),
            company_quality_score=score.company_quality,
            buying_signal_score=score.buying_signals,
            total_score=score.total,
            score_reason="; ".join(score.reasons),
            contact_name=contact.name,
            contact_role=contact.role,
            contact_email=contact.email,
            email_status=contact.email_status,
            phone=contact.phone or company.phone,
            phone_type=contact.phone_type,
            candidate_email=contact.candidate_email,
            news_mentions=signals.news,
            domain_age_years=signals.domain_age_years,
            provenance=provenance,
            linkedin_or_public_profile_url=contact.profile_url,
            pain_signal=pain,
            buying_signal=buying,
            personalization_hook=build_personalization_hook(company, cls, signals),
            source=company.source,
            source_url=company.source_url,
            outreach_ready=ready,
            sequence_status=SequenceStatus.SUPPRESSED if suppressed else SequenceStatus.NOT_QUEUED,
            priority=score.priority,
            technologies=signals.technologies,
            evidence={
                "classification": cls.model_dump(mode="json"),
                "score": score.model_dump(mode="json"),
                "quality": quality.model_dump(mode="json"),
                "contact_evidence": contact.evidence,
                "pages": {k: p.url for k, p in snapshot.pages.items()},
                "crawl_error": snapshot.error,
            },
        )
        # One lead per company per campaign: reuse the id so re-runs update in place.
        previous = self.db.lead_for_company(campaign.campaign_id, key)
        if previous:
            lead.lead_id = previous.lead_id
            lead.sequence_status = previous.sequence_status if previous.sequence_status != SequenceStatus.NOT_QUEUED else lead.sequence_status
        self.db.save_lead(lead, run_id, key)
        return lead

    # -- full run --------------------------------------------------------------------

    async def run(self, campaign: CampaignConfig, progress: ProgressFn | None = None) -> RunResult:
        run_id = new_id("run")
        stats = RunStats()
        self.db.upsert_campaign(campaign.campaign_id, campaign.name, campaign.model_dump(mode="json"))
        self.db.start_run(run_id, campaign.campaign_id)
        log.info("run %s started for campaign %s", run_id, campaign.campaign_id)
        try:
            discovered = await self.discover(campaign, progress)
            stats.discovered = len(discovered)
            if campaign.exclude_chains:
                before = len(discovered)
                discovered = [c for c in discovered if not c.extra.get("brand")]
                stats.chains_excluded = before - len(discovered)
            companies = dedupe_companies(discovered)
            # Companies that already carry a website are cheaper and better documented; process them first.
            companies.sort(key=lambda c: 0 if c.website else 1)
            companies = companies[: campaign.max_companies]
            stats.after_dedupe = len(companies)
            await _emit(progress, "dedupe", len(companies), len(companies), f"{len(companies)} unique companies")

            classifier = BuyerClassifier(campaign, self.defaults)
            leads: list[Lead] = []
            sem = asyncio.Semaphore(self.settings.concurrency)
            # Keys of companies with a known domain are reserved up front so a search-found
            # domain for a later, domain-less company cannot collide with them.
            seen_keys: set[str] = {company_key(c.domain, c.name, c.city) for c in companies if c.domain}

            async def worker(c: DiscoveredCompany) -> None:
                async with sem:
                    try:
                        lead = await self.process_company(c, campaign, classifier, run_id, stats,
                                                          seen_keys if not c.domain else None)
                        if lead is None:
                            return
                        leads.append(lead)
                        _tally(stats, lead)
                    except Exception:  # noqa: BLE001 - one company must not kill the batch
                        stats.errors += 1
                        log.exception("failed processing %s", c.name)
                    stats.processed += 1
                    await _emit(progress, "process", stats.processed, len(companies), c.name)

            await asyncio.gather(*(worker(c) for c in companies))
            leads.sort(key=lambda l: l.total_score, reverse=True)
            self.db.finish_run(run_id, "completed", stats.as_dict())
            log.info("run %s finished: %s", run_id, stats.as_dict())
            return RunResult(run_id=run_id, campaign_id=campaign.campaign_id, stats=stats, leads=leads)
        except Exception:
            self.db.finish_run(run_id, "failed", stats.as_dict())
            raise


def _tally(stats: RunStats, lead: Lead) -> None:
    if lead.company_type == CompanyType.BUYER:
        stats.buyer += 1
    elif lead.company_type == CompanyType.VENDOR:
        stats.vendor += 1
    else:
        stats.unknown += 1
    if lead.priority.value in ("high_priority", "qualified") and lead.company_type == CompanyType.BUYER:
        stats.qualified += 1
    if lead.outreach_ready:
        stats.outreach_ready += 1


async def _emit(progress: ProgressFn | None, stage: str, done: int, total: int, message: str) -> None:
    if progress is None:
        return
    result = progress(stage, done, total, message)
    if asyncio.iscoroutine(result):
        await result
