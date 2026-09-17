"""Configuration schema. Everything that drives qualification and scoring lives here,
not in code, so an ICP change never requires a code change."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field, field_validator


class GeographyConfig(BaseModel):
    countries: list[str] = Field(default_factory=lambda: ["Pakistan"])
    cities: list[str] = Field(default_factory=list)

    @field_validator("countries", "cities")
    @classmethod
    def _strip(cls, values: list[str]) -> list[str]:
        return [v.strip() for v in values if v and v.strip()]


class ScoringWeights(BaseModel):
    """Maximum points per dimension. Must sum to 100."""

    icp_fit: int = 50
    company_quality: int = 15
    buyer_evidence: int = 15
    contact_quality: int = 10
    buying_signals: int = 10

    def total(self) -> int:
        return (
            self.icp_fit
            + self.company_quality
            + self.buyer_evidence
            + self.contact_quality
            + self.buying_signals
        )


class RoutingThresholds(BaseModel):
    high_priority: int = 80
    qualified: int = 70
    review: int = 50


class CampaignConfig(BaseModel):
    campaign_id: str
    name: str
    offer: str = Field(description="What we sell; used only for context and personalization.")
    target_industries: list[str] = Field(default_factory=list)
    geography: GeographyConfig = Field(default_factory=GeographyConfig)
    company_size: str | None = None
    target_roles: list[str] = Field(default_factory=list)
    # Terms that indicate an end-buyer company for this campaign (retailer, clinic, ...).
    buyer_keywords: list[str] = Field(default_factory=list)
    # Campaign-specific vendor terms; merged with the global default negative list.
    negative_keywords: list[str] = Field(default_factory=list)
    # Vendor categories the campaign explicitly wants anyway (rare; e.g. targeting agencies).
    allowed_vendor_keywords: list[str] = Field(default_factory=list)
    # OSM tag filters, e.g. ["shop=*", "shop=clothes", "amenity=clinic"].
    osm_categories: list[str] = Field(default_factory=list)
    # Overture category substrings, e.g. ["clothing", "shoe_store", "supermarket"].
    overture_categories: list[str] = Field(default_factory=list)
    # Optional seed list of companies/domains supplied by the user.
    seed_csv: Path | None = None
    min_score: int = 70
    max_companies: int = 150
    max_pages_per_site: int = 6
    allow_multiple_contacts_per_company: bool = False
    # Drop branches of national/international chains (OSM `brand` tag): decisions are not
    # made at the outlet and the only public contact is a customer-care mailbox.
    exclude_chains: bool = False
    weights: ScoringWeights = Field(default_factory=ScoringWeights)
    routing: RoutingThresholds = Field(default_factory=RoutingThresholds)

    @field_validator("weights")
    @classmethod
    def _weights_sum(cls, w: ScoringWeights) -> ScoringWeights:
        if w.total() != 100:
            raise ValueError(f"scoring weights must sum to 100, got {w.total()}")
        return w

    @field_validator(
        "target_industries", "target_roles", "buyer_keywords", "negative_keywords",
        "allowed_vendor_keywords", "osm_categories", "overture_categories",
    )
    @classmethod
    def _lower(cls, values: list[str]) -> list[str]:
        return [v.strip().lower() for v in values if v and v.strip()]


class DefaultRules(BaseModel):
    """Global rule sets shipped in config/defaults/*.yaml. Campaigns extend, never replace."""

    negative_keywords: list[str] = Field(default_factory=list)
    # Self-descriptions typical of service sellers ("our clients include", "hire us").
    vendor_phrases: list[str] = Field(default_factory=list)
    # Discovery categories (OSM tags) that describe sellers of services by definition.
    vendor_categories: list[str] = Field(default_factory=list)
    buyer_role_whitelist: list[str] = Field(default_factory=list)
    role_blacklist: list[str] = Field(default_factory=list)
    generic_email_prefixes: list[str] = Field(default_factory=list)
    buying_signal_keywords: dict[str, list[str]] = Field(default_factory=dict)
    pain_signal_keywords: dict[str, list[str]] = Field(default_factory=dict)
    technology_markers: dict[str, list[str]] = Field(default_factory=dict)
    geography_tiers: dict[str, list[str]] = Field(default_factory=dict)


class EngineSettings(BaseModel):
    """Runtime settings. Loaded from config/engine.yaml, overridable via env GTM_*."""

    db_path: Path = Path("data/gtm.sqlite")
    export_dir: Path = Path("data/exports")
    user_agent: str = "GTMLeadEngine/0.1 (+business research; contact via site form)"
    request_timeout_s: float = 15.0
    per_host_delay_s: float = 2.0
    max_retries: int = 2
    concurrency: int = 4
    respect_robots: bool = True
    # Render JS-only sites with headless Chromium when static HTTP returns an empty shell.
    # Needs the `browser` extra; off by default because no target site has needed it yet.
    enable_browser_fallback: bool = False
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    # Tried in order when the primary returns an error or rate-limits (shared public instances).
    overpass_mirrors: list[str] = Field(default_factory=lambda: [
        "https://overpass.kumi.systems/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ])
    overpass_timeout_s: int = 90
    enable_search_fallback: bool = True
    search_delay_s: float = 5.0
    dns_timeout_s: float = 5.0
    log_level: str = "INFO"
