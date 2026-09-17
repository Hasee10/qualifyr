"""Overture Maps Places: a bulk, openly licensed business dataset (Meta/Microsoft-derived)
published as parquet on public S3. Queried in place with DuckDB, no key, no download.
Roughly 40x OSM's coverage for Pakistani cities, with websites and emails."""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

from gtm_engine.config.schema import CampaignConfig, EngineSettings
from gtm_engine.discovery.geocode import BBox, Geocoder
from gtm_engine.models import DiscoveredCompany
from gtm_engine.scraping.fetcher import HttpFetcher

log = logging.getLogger(__name__)

S3_ROOT = "s3://overturemaps-us-west-2/release"
COLUMNS = ["id", "name", "category", "website", "email", "phone", "address", "city", "brand", "lat", "lon"]


def build_sql(release: str, bbox: BBox, categories: list[str], limit: int | None) -> tuple[str, list[str]]:
    cat_clause = ""
    params: list[str] = []
    if categories:
        cat_clause = "AND (" + " OR ".join("lower(categories.primary) LIKE ?" for _ in categories) + ")"
        params = [f"%{c.lower()}%" for c in categories]
    sql = f"""
        SELECT id, names.primary AS name, categories.primary AS category,
               CASE WHEN length(websites)>0 THEN websites[1] END AS website,
               CASE WHEN length(emails)>0   THEN emails[1]   END AS email,
               CASE WHEN length(phones)>0   THEN phones[1]   END AS phone,
               addresses[1].freeform AS address, addresses[1].locality AS city,
               brand.names.primary AS brand, bbox.ymin AS lat, bbox.xmin AS lon
        FROM read_parquet('{S3_ROOT}/{release}/theme=places/type=place/*', hive_partitioning=1)
        WHERE bbox.xmin BETWEEN {bbox.west} AND {bbox.east}
          AND bbox.ymin BETWEEN {bbox.south} AND {bbox.north}
          AND names.primary IS NOT NULL
          {cat_clause}
        {f'LIMIT {int(limit)}' if limit else ''}
    """
    return sql, params


def row_to_company(row: dict, city: str, country: str) -> DiscoveredCompany | None:
    name = (row.get("name") or "").strip()
    if not name:
        return None
    return DiscoveredCompany(
        name=name,
        website=row.get("website") or None,
        country=country,
        city=city,
        address=row.get("address") or None,
        phone=row.get("phone") or None,
        email=(row.get("email") or "").lower() or None,
        category=f"overture={row['category']}" if row.get("category") else None,
        source="overture",
        source_url=f"https://explore.overturemaps.org/#{row['id']}" if row.get("id") else None,
        extra={"brand": row.get("brand"), "lat": row.get("lat"), "lon": row.get("lon"),
               "addr_city": row.get("city")},
    )


class OvertureDiscovery:
    name = "overture"

    def __init__(self, fetcher: HttpFetcher, settings: EngineSettings, geocoder: Geocoder | None = None,
                 per_city_limit: int | None = None):
        self.settings = settings
        self.geocoder = geocoder or Geocoder(fetcher, settings.db_path.parent / "geocode_cache.json")
        self.per_city_limit = per_city_limit

    def _query(self, bbox: BBox, categories: list[str]) -> list[dict]:
        try:
            import duckdb
        except ImportError:
            log.warning("overture: duckdb not installed (pip install -e '.[overture]'); skipping")
            return []
        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
        release = con.execute(
            "SELECT max(regexp_extract(file, 'release/([^/]+)/', 1)) "
            f"FROM glob('{S3_ROOT}/*/theme=places/type=place/*')"
        ).fetchone()[0]
        sql, params = build_sql(release, bbox, categories, self.per_city_limit)
        rows = con.execute(sql, params).fetchall()
        con.close()
        return [dict(zip(COLUMNS, r)) for r in rows]

    async def discover(self, campaign: CampaignConfig) -> AsyncIterator[DiscoveredCompany]:
        if not campaign.overture_categories:
            log.info("overture: campaign has no overture_categories; skipping")
            return
        country = campaign.geography.countries[0] if campaign.geography.countries else ""
        for city in campaign.geography.cities:
            bbox = await self.geocoder.bbox(city, country)
            if bbox is None:
                continue
            rows = await asyncio.to_thread(self._query, bbox, campaign.overture_categories)
            log.info("overture: %s -> %d places", city, len(rows))
            for row in rows:
                company = row_to_company(row, city, country)
                if company:
                    yield company
