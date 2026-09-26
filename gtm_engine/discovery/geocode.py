"""City -> bounding box via Nominatim (OpenStreetMap's geocoder). Free; usage policy asks
for an identifying User-Agent and at most one request per second. Results are cached on
disk because city boxes never change between runs."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlencode

from gtm_engine.scraping.fetcher import HttpFetcher

log = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
# Nominatim's usage policy caps the public instance at 1 request/second; 1.1s stays under it.
# Results are also cached to disk (see __init__), so a re-run and repeated cities cost nothing.
# Override for a self-hosted instance with a higher limit via GTM_NOMINATIM_DELAY_S.
NOMINATIM_DELAY_S = float(os.environ.get("GTM_NOMINATIM_DELAY_S", "1.1"))


@dataclass(frozen=True)
class BBox:
    south: float
    west: float
    north: float
    east: float

    def overpass(self) -> str:
        return f"{self.south},{self.west},{self.north},{self.east}"


class Geocoder:
    def __init__(self, fetcher: HttpFetcher, cache_path: Path | None = None):
        self.fetcher = fetcher
        self.cache_path = cache_path
        self._cache: dict[str, dict] = {}
        if cache_path and cache_path.exists():
            try:
                self._cache = json.loads(cache_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._cache = {}

    async def bbox(self, city: str, country: str | None) -> BBox | None:
        key = f"{city}|{country or ''}".lower()
        if key in self._cache:
            return BBox(**self._cache[key])
        params = {"q": f"{city}, {country}" if country else city, "format": "json", "limit": 1}
        result = await self.fetcher.get(f"{NOMINATIM_URL}?{urlencode(params)}", delay=NOMINATIM_DELAY_S, api=True)
        if not result.ok:
            log.warning("geocode: %s failed (%s %s)", city, result.status_code, result.error)
            return None
        try:
            hits = json.loads(result.text)
        except json.JSONDecodeError:
            return None
        if not hits or "boundingbox" not in hits[0]:
            log.warning("geocode: no result for %r", params["q"])
            return None
        south, north, west, east = (float(v) for v in hits[0]["boundingbox"])
        box = BBox(south=south, west=west, north=north, east=east)
        self._cache[key] = box.__dict__
        if self.cache_path:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=1), encoding="utf-8")
        log.info("geocode: %s -> %s", params["q"], box.overpass())
        return box
