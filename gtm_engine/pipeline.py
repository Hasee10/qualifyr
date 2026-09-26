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
from gtm_engine.discovery.targeting import derive_discovery_targets
from gtm_engine.discovery.web_search import WebSearchDiscovery
from gtm_engine.enrichment.contacts import choose_contact
from gtm_engine.enrichment.email_patterns import discover, infer_pattern
from gtm_engine.enrichment.external_signals import NewsChecker, domain_age
from gtm_engine.enrichment.github_signals import github_activity
from gtm_engine.enrichment.job_signals import job_board_signals
from gtm_engine.enrichment.press_signals import press_mentions
from gtm_engine.enrichment.research import build_research_brief
from gtm_engine.intent.company_pages import intent_from_pages
from gtm_engine.intent.ppra import PPRATenders
from gtm_engine.llm.client import build_llm
from gtm_engine.llm.tasks import draft_hook, extract_requirement, generate_keywords, judge_intent
from gtm_engine.qualification.relevance import relevant_terms
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
from gtm_engine.validation.liveness import HostResolver
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
    rejected_sites: int = 0      # parked / soft-404 / placeholder / marketplace redirect
    dead_websites: int = 0       # skipped before crawling: the domain no longer resolves
    intent_dropped_irrelevant: int = 0  # hiring/RFQ signals dropped for not matching the offer
    relevance_keywords: list[str] = field(default_factory=list)  # the offer's need-terms this run used
    discovery_sectors: list[str] = field(default_factory=list)   # sectors derived from the offer (E1)
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
    for s in signals.intent[:1]:
        if s.get("kind") == "tender":
            facts.append(f"tendering: {s['text'][:70]}")
        elif s.get("kind") == "hiring":
            facts.append(f"hiring a {s['matched_terms'][0]}" if s.get("matched_terms") else "hiring")
        elif s.get("kind") == "rfq":
            facts.append("has a live request for quotations")
    if signals.news:
        facts.append(f"recently in the news ({signals.news[0].get('source', '')})")
    if signals.domain_age_years is not None and signals.domain_age_years < 2:
        facts.append("recently launched online")
    if signals.job_openings:
        growth = [j for j in signals.job_openings if j.get("growth_role")]
        if growth:
            facts.append(f"hiring for {growth[0]['title']}")
        else:
            facts.append(f"{len(signals.job_openings)} open role(s) posted")
    if signals.press_mentions:
        facts.append(f"{signals.press_mentions[0]['kind'].replace('_', ' ')}: {signals.press_mentions[0]['title'][:60]}")
    if signals.github_activity:
        facts.append("actively engineering (public GitHub org)")
    return "; ".join(facts) if facts else None


# Above this confidence, the LLM's intent verdict is allowed to change the buyer/unknown call
# (promote a keyword-thin UNKNOWN to BUYER, or demote a keyword-only BUYER with no real need).
# Below it, the verdict is recorded and lightly scored but does not flip the type.
INTENT_THRESHOLD = 0.6


def _round_robin(lists: list[list]) -> list:
    """Flatten several source lists by taking one from each in turn (source order preserved
    within a round). Keeps every item; only the order changes, so a downstream cap samples all
    sources instead of draining the first one."""
    out: list = []
    for i in range(max((len(lst) for lst in lists), default=0)):
        for lst in lists:
            if i < len(lst):
                out.append(lst[i])
    return out


def _intent_evidence(company, bundle, signals=None) -> str:
    """The company's own evidence the intent judge reasons over: name, category, description,
    the observed operating signals, and about/body copy. Feeding the signals (multiple outlets,
    ecommerce, hiring, tech, tenders) alongside the page text stops a real multi-outlet buyer
    with a sparse homepage from being under-rated on marketing copy alone. Still its own
    evidence, so the verdict is about evident need, not about our keywords."""
    parts = [
        company.name or "",
        f"Category: {company.category}" if company.category else "",
        bundle.description or "",
    ]
    if signals is not None:
        facts: list[str] = []
        for group in (signals.buying or {}).values():
            facts += list(group)
        for group in (signals.pain or {}).values():
            facts += list(group)
        if facts:
            parts.append("Observed signals: " + "; ".join(facts[:8]))
        if signals.technologies:
            parts.append("Technologies: " + ", ".join(signals.technologies[:8]))
        if signals.job_openings:
            titles = [j.get("title", "") for j in signals.job_openings[:5] if j.get("title")]
            if titles:
                parts.append("Hiring: " + ", ".join(titles))
        for s in (signals.intent or [])[:3]:
            parts.append(f"Intent signal ({s.get('kind')}): {s.get('text', '')[:120]}")
    parts.append((bundle.about_text or bundle.body_text or "")[:3500])
    return "\n".join(p for p in parts if p).strip()


def apply_intent_verdict(cls: Classification, verdict: dict, *, threshold: float = INTENT_THRESHOLD) -> str:
    """Fold an LLM intent verdict into a Classification (mutates it) and return a provenance
    note. A confident buyer promotes a keyword-thin UNKNOWN to BUYER; a confident non-buyer
    demotes a keyword-only BUYER to UNKNOWN. The verdict is always recorded on the
    classification even when it is not strong enough to flip the type. The caller must not pass
    a VENDOR here — that is a hard reject and is never changed by intent."""
    cls.intent_buyer = verdict["buyer"]
    cls.intent_confidence = verdict["confidence"]
    cls.intent_reason = verdict["reason"]
    strong = verdict["confidence"] >= threshold
    pct = f"{verdict['confidence']:.0%}"
    if verdict["buyer"] and strong and cls.company_type == CompanyType.UNKNOWN:
        cls.company_type = CompanyType.BUYER
        cls.confidence = max(cls.confidence, verdict["confidence"])
        cls.reasons.append(f"intent: needs the offer ({pct}) — {verdict['reason']}")
    elif not verdict["buyer"] and strong and cls.company_type == CompanyType.BUYER:
        cls.company_type = CompanyType.UNKNOWN
        cls.reasons.append(f"intent: no evident need for the offer ({pct}) — {verdict['reason']}")
    return f"{verdict['by']}: {'buyer' if verdict['buyer'] else 'not a buyer'} ({pct})"


class Pipeline:
    def __init__(self, settings: EngineSettings, defaults: DefaultRules, db: Database,
                 fetcher: Fetcher, mx: MXChecker | None = None, verifier: EmailVerifier | None = None,
                 resolver: HostResolver | None = None):
        self.settings = settings
        self.defaults = defaults
        self.db = db
        # The DB is one sync psycopg connection (not thread-safe). Run its calls in a worker
        # thread so a slow query does not freeze the event loop for every other concurrent
        # company, and serialise them with a lock so the single connection is only ever touched
        # by one thread at a time. Net effect: concurrency=N genuinely overlaps the network-bound
        # work (crawl, LLM) instead of stalling on each blocking DB call.
        self._db_lock = asyncio.Lock()
        self.fetcher = fetcher
        self.mx = mx if mx is not None else MXChecker(settings.dns_timeout_s)
        self.resolver = resolver if resolver is not None else HostResolver(settings.dns_timeout_s)
        self.verifier = verifier
        self.website_finder = WebsiteFinder(fetcher, settings)
        self.news = NewsChecker(fetcher)
        self._news_budget = settings.news_max_companies_per_run
        self._website_finder_budget = settings.website_finder_max_per_run
        self._job_board_budget = settings.job_board_max_companies_per_run
        self._github_budget = settings.github_max_companies_per_run
        self._press_budget = settings.press_max_companies_per_run
        self.ppra = PPRATenders(fetcher, settings)
        self.llm = build_llm(settings.llm_provider, settings.llm_model) if settings.enable_llm else None
        if self.llm:
            log.info("llm layer: %s", self.llm.name)
        # The need-terms a hiring/intent signal must mention to count for this campaign
        # (what we SELL, not the buyer's sector). Filled per run by _build_relevance_keywords.
        self._relevance_keywords: list[str] = []

    async def _build_relevance_keywords(self, campaign: CampaignConfig) -> list[str]:
        """Terms that make a hiring/intent signal relevant to this offer. The campaign's own
        intent_keywords, plus keywords the LLM derives from the offer (or a deterministic
        fallback of the offer's words). Deliberately excludes target_industries: the sector a
        company is in does not make its hiring relevant to what we sell - that is exactly the
        'Imtiaz was hiring, but for their own retail floor' false positive we are removing."""
        need = list(campaign.intent_keywords)
        try:
            need += await generate_keywords(self.llm, campaign.offer)  # industries omitted on purpose
        except Exception as exc:  # noqa: BLE001 - relevance is a filter, never fatal
            log.debug("keyword generation failed: %s", exc)
        seen: set[str] = set()
        out: list[str] = []
        for t in need:
            t = (t or "").strip().lower()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out

    async def _verifier(self) -> EmailVerifier:
        if self.verifier is None:
            self.verifier = await build_verifier(self.settings.email_verification, self.settings.reacher_url)
            log.info("email verifier: %s", self.verifier.name)
        return self.verifier

    # -- discovery ---------------------------------------------------------------

    async def _db_call(self, fn, *args, **kwargs):
        """Run a blocking DB method off the event loop, one at a time (the single connection is
        not thread-safe). Used for the per-company writes/reads that run under concurrency."""
        async with self._db_lock:
            return await asyncio.to_thread(fn, *args, **kwargs)

    async def discover(self, campaign: CampaignConfig, progress: ProgressFn | None = None) -> list[DiscoveredCompany]:
        sources = []
        if campaign.overture_categories and campaign.geography.search_areas():
            sources.append(OvertureDiscovery(self.fetcher, self.settings))
        if campaign.osm_categories and campaign.geography.search_areas():
            sources.append(OSMDiscovery(self.fetcher, self.settings))
        if self.settings.enable_web_search_discovery and campaign.search_queries:
            sources.append(WebSearchDiscovery(self.fetcher, self.settings))
        if "kcci" in campaign.chamber_sources:
            sources.append(KCCIDirectory(self.fetcher, self.settings))
        if "ppra" in campaign.intent_sources:
            sources.append(self.ppra)
        if campaign.seed_csv:
            sources.append(CSVSeedDiscovery(campaign.seed_csv))
        if not sources:
            log.warning("no discovery sources configured (need osm_categories+cities or seed_csv)")
        per_source: list[list[DiscoveredCompany]] = []
        for src in sources:
            items: list[DiscoveredCompany] = []
            async for company in src.discover(campaign):
                items.append(company)
            per_source.append(items)
            await _emit(progress, "discover", sum(len(s) for s in per_source), 0, f"{src.name}: {len(items)}")
        # Round-robin across sources so a small max_companies cap still samples every source. A
        # dense source (Overture/OSM returns thousands) would otherwise exhaust the cap before a
        # single web-search or chamber result is ever processed - which was exactly the case that
        # made web-search discovery contribute nothing on a real run.
        return _round_robin(per_source)

    # -- single company ----------------------------------------------------------

    async def process_company(self, company: DiscoveredCompany, campaign: CampaignConfig,
                              classifier: BuyerClassifier, run_id: str, stats: RunStats,
                              seen_keys: set[str] | None = None) -> Lead | None:
        """Returns None when the company turns out to duplicate one already processed
        in this run (its website, found by search, belongs to an earlier company)."""
        website = company.website
        if not website and self._website_finder_budget > 0:
            self._website_finder_budget -= 1
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
        await self._db_call(self.db.upsert_company, key, campaign.campaign_id, company.name, domain=domain,
                            website=website, country=company.country, city=company.city, source=company.source,
                            source_url=company.source_url, raw=company.model_dump(mode="json"))

        provenance: dict[str, str] = {"company": f"{company.source}: {company.source_url or 'record'}"}
        if not website:
            stats.no_website += 1
            snapshot = SiteSnapshot(website="", final_url=None, reachable=False, https=False, error="no_website")
        else:
            crawler = SiteCrawler(self.fetcher, campaign.max_pages_per_site,
                                  deadline_s=self.settings.per_company_timeout_s)
            snapshot = await crawler.crawl(website)
            if snapshot.redirected_to and snapshot.redirected_to != domain:
                # The site moved: the lead belongs to the domain that actually answers.
                provenance["domain"] = f"{domain or website} redirects to {snapshot.redirected_to}"
                domain = snapshot.redirected_to
                new_key = company_key(domain, company.name, company.city)
                if seen_keys is not None and new_key in seen_keys and new_key != key:
                    # Two records that redirect to the same site are one company.
                    stats.duplicates += 1
                    log.info("skipping %s: redirects to %s, already processed", company.name, domain)
                    return None
                if seen_keys is not None:
                    seen_keys.discard(key)
                    seen_keys.add(new_key)
                key = new_key
            if not snapshot.reachable:
                stats.unreachable += 1
                if snapshot.integrity_reason:
                    stats.rejected_sites += 1
                    provenance["website_rejected"] = f"{snapshot.integrity_reason}: {snapshot.integrity_detail}"
            for kind, page in snapshot.pages.items():
                await self._db_call(self.db.save_page, key, page.url, kind, 200, page.title, page.text[:5000])

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
            tender_terms=(company.extra.get("intent") or {}).get("matched_terms") or None,
        )
        cls = classifier.classify(bundle)
        quality = assess_quality(snapshot, company.name, domain)
        signals = detect_signals(snapshot, self.defaults) if snapshot.reachable else Signals()
        # A site that does not belong to this company cannot supply its contact details:
        # its email, phone and staff names belong to somebody else.
        trust_site = snapshot.reachable and not quality.website_mismatch
        if snapshot.reachable and quality.website_mismatch:
            provenance["website_rejected"] = "website does not appear to belong to this company; its contact details were not used"
        if trust_site:
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
                evidence="from discovery source only" if not quality.website_mismatch
                         else "website looked like a different company; using the discovery record only",
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

        # Intent: tenders naming this organisation, plus RFQ/hiring phrases on its own pages.
        if self.settings.enable_intent_signals and cls.company_type != CompanyType.VENDOR:
            intents = []
            if company.extra.get("intent"):
                intents.append(dict(company.extra["intent"]))
            if trust_site:
                # Strict relevance (P2): a hiring/RFQ phrase on the company's own pages only
                # counts if it mentions what we sell. With no relevance keywords (offer blank,
                # no LLM) the gate is a no-op, preserving the old behaviour.
                for s in intent_from_pages(snapshot, self.defaults):
                    rel = relevant_terms(s.text, self._relevance_keywords)
                    if self._relevance_keywords and not rel:
                        stats.intent_dropped_irrelevant += 1
                        continue
                    sig = s.model_dump(mode="json")
                    if rel:
                        sig["relevance"] = rel
                    intents.append(sig)
            if company.source != "ppra" and ("ppra" in campaign.intent_sources or self.settings.enable_intent_signals):
                try:
                    intents += [s.model_dump(mode="json") for s in await self.ppra.signals_for(company.name, campaign)]
                except Exception as exc:  # noqa: BLE001 - intent is additive, never blocking
                    log.debug("ppra match failed for %s: %s", company.name, exc)
            for sig in intents:
                if sig.get("kind") == "tender" and self.llm and not sig.get("extracted"):
                    sig["extracted"] = await extract_requirement(self.llm, sig.get("text", ""))
            if intents:
                signals.intent = intents
                signals.buying.setdefault("intent", []).extend(f"{s['kind']}: {s['text'][:60]}" for s in intents[:2])
                provenance["intent"] = "; ".join(f"{s['source']} {s['kind']}" + (f" ({s['source_url']})" if s.get('source_url') else "") for s in intents[:3])

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

            # GTM intelligence: job-board postings, GitHub activity, press/RSS mentions.
            if self.settings.enable_job_board_signals and self._job_board_budget > 0:
                self._job_board_budget -= 1
                jb = await job_board_signals(self.fetcher, company.name, domain, self.defaults)
                if jb.postings:
                    signals.job_openings = [p.__dict__ for p in jb.postings]
                    growth = [p for p in jb.postings if p.growth_role]
                    label = "growth-role hiring" if growth else "hiring"
                    signals.buying.setdefault("job_openings", []).append(
                        f"{len(jb.postings)} open role(s) on {jb.board} ({label})")
                    provenance["job_openings"] = f"{jb.board}: {len(jb.postings)} posting(s), slug '{jb.slug}'"

            if self.settings.enable_github_signals and self._github_budget > 0:
                self._github_budget -= 1
                gh = await github_activity(self.fetcher, company.name, domain)
                if gh:
                    signals.github_activity = gh.__dict__
                    signals.buying.setdefault("github_activity", []).append(
                        f"{gh.public_repos} public repo(s), last pushed {gh.last_pushed_at}")
                    provenance["github_activity"] = f"github: org '{gh.org}', {gh.public_repos} repo(s)"

            if self.settings.enable_press_signals and self._press_budget > 0:
                self._press_budget -= 1
                press = await press_mentions(self.fetcher, snapshot.final_url or website, self.defaults)
                if press:
                    signals.press_mentions = [p.__dict__ for p in press]
                    signals.buying.setdefault("press_mention", []).extend(
                        f"{p.kind}: {p.title[:60]}" for p in press[:2])
                    provenance["press_mentions"] = f"rss: {len(press)} entr(y/ies), latest '{press[0].title[:60]}'"

        # Intent (CEO: qualify by NEED, not keywords). When the LLM is on, judge whether this
        # company plausibly needs the offer from its own text, and let that drive the type and
        # the score. A confident "not a buyer" demotes a keyword-only BUYER to UNKNOWN; a
        # confident buyer promotes an UNKNOWN. VENDOR (agency/competitor) is a hard reject and
        # is never promoted. Without the LLM this is skipped and the keyword path stands.
        if self.llm and cls.company_type != CompanyType.VENDOR:
            verdict = await judge_intent(self.llm, campaign.offer, _intent_evidence(company, bundle, signals))
            if verdict:
                provenance["intent_fit"] = apply_intent_verdict(cls, verdict)

        score = score_lead(ScoreInputs(company, cls, quality, contact, signals), campaign)
        ready = is_outreach_ready(cls, score, contact, campaign)
        suppressed = await self._db_call(self.db.is_suppressed, domain, contact.email)
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
            intent_signals=signals.intent,
            job_openings=signals.job_openings,
            github_activity=signals.github_activity,
            press_mentions=signals.press_mentions,
            provenance=provenance,
            linkedin_or_public_profile_url=contact.profile_url,
            pain_signal=pain,
            buying_signal=buying,
            personalization_hook=build_personalization_hook(company, cls, signals),
            intent_fit=cls.intent_buyer,
            intent_confidence=cls.intent_confidence,
            intent_reason=cls.intent_reason,
            research_brief=build_research_brief(company, cls, contact, signals, city=company.city,
                                                industry=company.category, description=description,
                                                quality=quality),
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
        previous = await self._db_call(self.db.lead_for_company, campaign.campaign_id, key)
        if previous:
            lead.lead_id = previous.lead_id
            lead.review_verdict, lead.reviewed_at = previous.review_verdict, previous.reviewed_at
            lead.sequence_status = previous.sequence_status if previous.sequence_status != SequenceStatus.NOT_QUEUED else lead.sequence_status
        await self._db_call(self.db.save_lead, lead, run_id, key)
        return lead

    async def _take_live(self, companies: list[DiscoveredCompany], limit: int | None,
                         progress: ProgressFn | None) -> tuple[list[DiscoveredCompany], int]:
        """Fill the run's company budget with domains that still resolve.

        The budget is spent before anything is fetched, so a dead domain costs a whole
        slot and yields nothing. On the first production run that was 60% of them - and
        discovery had found 3854 candidates behind a cap of 120, so the dead ones were
        being paid for while thousands of live ones went untouched.

        Screened in batches rather than all at once: we usually only need to look at a
        little more than `limit` before the budget is full, and resolving all 3854 would
        cost more than it saves.

        Companies with no website are kept as a tail - there is nothing to resolve yet,
        and WebsiteFinder may still turn one up during processing.
        """
        if not limit or limit <= 0:
            return companies, 0

        with_site = [c for c in companies if c.website]
        without_site = [c for c in companies if not c.website]

        # Screening only pays when there is a queue to promote from. With no more
        # candidates than slots, a dead domain's place cannot be refilled, so rejecting
        # it just shrinks the run - and a resolver wrong about one host would cost a
        # company for nothing. Also keeps small and offline runs off the network.
        if len(with_site) <= limit:
            return companies[:limit], 0
        live: list[DiscoveredCompany] = []
        dead = 0
        cursor = 0

        while len(live) < limit and cursor < len(with_site):
            batch = with_site[cursor:cursor + max(limit, 50)]
            cursor += len(batch)
            for company, alive in zip(batch, await asyncio.gather(
                    *(self.resolver.resolves(c.website) for c in batch))):
                if alive:
                    live.append(company)
                    if len(live) >= limit:
                        break
                else:
                    dead += 1
            await _emit(progress, "liveness", len(live), limit,
                        f"{len(live)} live, {dead} dead domains skipped")

        live.extend(without_site[: max(0, limit - len(live))])
        if dead:
            log.info("liveness: skipped %d dead domains to fill %d slots", dead, len(live))
        return live, dead

    # -- full run --------------------------------------------------------------------

    async def run(self, campaign: CampaignConfig, progress: ProgressFn | None = None) -> RunResult:
        run_id = new_id("run")
        stats = RunStats()
        self.db.upsert_campaign(campaign.campaign_id, campaign.name, campaign.model_dump(mode="json"))
        self.db.start_run(run_id, campaign.campaign_id)
        self._relevance_keywords = await self._build_relevance_keywords(campaign)
        stats.relevance_keywords = self._relevance_keywords
        # Feed the generated keywords into discovery itself, not just the relevance gate: a
        # deep copy (so the caller's config is untouched) whose intent_keywords carry the
        # offer's need-terms, so PPRA tender search/matching and the buyer classifier's
        # tender evidence all target what this campaign actually sells.
        if self._relevance_keywords:
            campaign = campaign.model_copy(deep=True)
            campaign.intent_keywords = self._relevance_keywords
        # Offer-driven discovery (E1 categories + E2 web-search queries). Derive from the offer
        # to fill map categories the user did not hand-pick and to produce web-search queries.
        # Explicit user map categories always win - deriving only fills the gap, never overrides.
        needs_categories = not campaign.osm_categories and not campaign.overture_categories
        if campaign.offer and (needs_categories or not campaign.search_queries):
            targets = await derive_discovery_targets(
                campaign.offer, campaign.target_industries, self.llm,
                cities=campaign.geography.cities, countries=campaign.geography.countries)
            if targets.osm_categories or targets.overture_categories or targets.search_queries:
                # Copy before mutating, unless the relevance step already made a private copy.
                if not self._relevance_keywords:
                    campaign = campaign.model_copy(deep=True)
                if needs_categories:
                    campaign.osm_categories = targets.osm_categories
                    campaign.overture_categories = targets.overture_categories
                    stats.discovery_sectors = targets.sectors
                if not campaign.search_queries:
                    campaign.search_queries = targets.search_queries
        log.info("run %s started for campaign %s; relevance keywords: %s; sectors: %s",
                 run_id, campaign.campaign_id, self._relevance_keywords[:12], stats.discovery_sectors)
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
            companies, stats.dead_websites = await self._take_live(
                companies, campaign.max_companies, progress)
            stats.after_dedupe = len(companies)
            await _emit(progress, "dedupe", len(companies), len(companies), f"{len(companies)} unique companies")

            classifier = BuyerClassifier(campaign, self.defaults)
            leads: list[Lead] = []
            sem = asyncio.Semaphore(self.settings.concurrency)
            # Claimed as each company is processed. Companies that already carry a website are
            # sorted first, so a search- or redirect-found domain can never steal the key of a
            # company that genuinely owns it.
            seen_keys: set[str] = set()

            async def worker(c: DiscoveredCompany) -> None:
                async with sem:
                    try:
                        lead = await self.process_company(c, campaign, classifier, run_id, stats, seen_keys)
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
