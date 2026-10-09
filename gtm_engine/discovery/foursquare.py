"""Foursquare Open Source Places: a bulk, openly licensed (Apache 2.0) business dataset
queried in place with DuckDB, no key, no download - same pattern as Overture.

Foursquare moved its primary access behind a signup-gated "Places Portal" (Iceberg
catalog), but a legacy public S3 bucket with no signup still serves a frozen snapshot of
the same dataset. It is not live-updating like Overture's monthly releases, but it is free,
keyless, and - unlike OSM/Overture in this market - carries native email/phone/website
fields plus a `date_closed` signal neither of the other two sources has."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from gtm_engine.config.schema import CampaignConfig, EngineSettings
from gtm_engine.discovery.geocode import BBox, Geocoder
from gtm_engine.models import DiscoveredCompany
from gtm_engine.scraping.fetcher import HttpFetcher

log = logging.getLogger(__name__)

S3_ROOT = "s3://fsq-os-places-us-east-1/release"
COLUMNS = ["id", "name", "category", "website", "email", "phone", "address", "country", "lat", "lon"]


def build_sql(release: str, bbox: BBox, categories: list[str], limit: int | None) -> tuple[str, list[str]]:
    cat_clause = ""
    params: list[str] = []
    if categories:
        cat_clause = "AND (" + " OR ".join(
            "EXISTS (SELECT 1 FROM unnest(fsq_category_labels) AS l WHERE lower(l) LIKE ?)"
            for _ in categories
        ) + ")"
        params = [f"%{c.lower()}%" for c in categories]
    sql = f"""
        SELECT fsq_place_id AS id, name, fsq_category_labels AS category,
               website, email, tel AS phone, address, country,
               latitude AS lat, longitude AS lon
        FROM read_parquet('{S3_ROOT}/dt={release}/places/parquet/*', hive_partitioning=1)
        WHERE latitude BETWEEN {bbox.south} AND {bbox.north}
          AND longitude BETWEEN {bbox.west} AND {bbox.east}
          AND name IS NOT NULL
          AND date_closed IS NULL
          {cat_clause}
        {f'LIMIT {int(limit)}' if limit else ''}
    """
    return sql, params


def row_to_company(row: dict, city: str, country: str) -> DiscoveredCompany | None:
    name = (row.get("name") or "").strip()
    if not name:
        return None
    category = row.get("category") or []
    primary_category = category[0] if category else None
    return DiscoveredCompany(
        name=name,
        website=row.get("website") or None,
        country=country,
        city=city,
        address=row.get("address") or None,
        phone=row.get("phone") or None,
        email=(row.get("email") or "").lower() or None,
        category=f"foursquare={primary_category}" if primary_category else None,
        source="foursquare",
        source_url=f"https://foursquare.com/v/{row['id']}" if row.get("id") else None,
        extra={"lat": row.get("lat"), "lon": row.get("lon")},
    )


class FoursquareDiscovery:
    name = "foursquare"

    def __init__(self, fetcher: HttpFetcher, settings: EngineSettings, geocoder: Geocoder | None = None,
                 per_city_limit: int | None = None):
        self.settings = settings
        self.geocoder = geocoder or Geocoder(fetcher, settings.db_path.parent / "geocode_cache.json")
        self.per_city_limit = per_city_limit

    def _query(self, bbox: BBox, categories: list[str]) -> list[dict]:
        try:
            import duckdb
        except ImportError:
            log.warning("foursquare: duckdb not installed (pip install -e '.[overture]'); skipping")
            return []
        con = duckdb.connect()
        # Legacy public snapshot: anonymous S3 access, no credentials.
        con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-east-1'; "
                    "SET s3_access_key_id=''; SET s3_secret_access_key='';")
        release = con.execute(
            "SELECT max(regexp_extract(file, 'dt=([^/]+)/', 1)) "
            f"FROM glob('{S3_ROOT}/*/places/parquet/*')"
        ).fetchone()[0]
        if not release:
            log.warning(
                "foursquare: no release found under %s - the legacy keyless S3 snapshot appears "
                "discontinued upstream (see docs/API_KEYS.md); skipping", S3_ROOT)
            con.close()
            return []
        sql, params = build_sql(release, bbox, categories, self.per_city_limit)
        rows = con.execute(sql, params).fetchall()
        con.close()
        return [dict(zip(COLUMNS, r)) for r in rows]

    async def discover(self, campaign: CampaignConfig) -> AsyncIterator[DiscoveredCompany]:
        if not campaign.foursquare_categories:
            log.info("foursquare: campaign has no foursquare_categories; skipping")
            return
        countries = campaign.geography.countries or [""]
        for area in campaign.geography.search_areas():
            bbox, country = None, countries[0]
            for c in countries:
                bbox = await self.geocoder.bbox(area, c or None)
                if bbox is not None:
                    country = c
                    break
            if bbox is None:
                log.warning("foursquare: could not geocode %s; skipping", area)
                continue
            rows = await asyncio.to_thread(self._query, bbox, campaign.foursquare_categories)
            log.info("foursquare: %s -> %d places", area, len(rows))
            for row in rows:
                company = row_to_company(row, area, country or "")
                if company:
                    yield company
