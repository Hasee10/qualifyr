"""Polite HTTP fetcher: per-host delay, retries with backoff, timeouts, robots.txt.
Static HTTP is the default path; a browser-backed Fetcher can implement the same
interface for JS-heavy sites later."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from gtm_engine.config.schema import EngineSettings

log = logging.getLogger(__name__)

_RETRYABLE = {408, 425, 429, 500, 502, 503, 504}
_META_CHARSET_RE = re.compile(rb"<meta[^>]+charset=[\"']?\s*([a-zA-Z0-9_-]+)", re.I)
_XML_DECL_RE = re.compile(rb"<\?xml[^>]+encoding=[\"']([a-zA-Z0-9_-]+)", re.I)


def decode_body(raw: bytes, content_type: str) -> str:
    """Header charset -> <meta charset> / XML declaration -> UTF-8 BOM -> utf-8 -> cp1252.
    Sites in Pakistan often omit the header and only declare the charset in HTML, which
    httpx alone would decode as UTF-8 and garble."""
    candidates: list[str] = []
    m = re.search(r"charset=([\w-]+)", content_type or "", re.I)
    if m:
        candidates.append(m.group(1))
    head = raw[:4096]
    for pat in (_META_CHARSET_RE, _XML_DECL_RE):
        mm = pat.search(head)
        if mm:
            candidates.append(mm.group(1).decode("ascii", "ignore"))
    if raw.startswith(b"\xef\xbb\xbf"):
        candidates.append("utf-8-sig")
    candidates += ["utf-8", "cp1252"]
    for enc in candidates:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    text: str
    content_type: str
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and 200 <= self.status_code < 300

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type or (self.ok and self.text.lstrip()[:15].lower().startswith(("<!doctype", "<html")))


class Fetcher(Protocol):
    async def get(self, url: str, **kwargs) -> FetchResult: ...
    async def close(self) -> None: ...


class HttpFetcher:
    def __init__(self, settings: EngineSettings):
        self.settings = settings
        self._client = httpx.AsyncClient(
            headers={
                "User-Agent": settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=httpx.Timeout(settings.request_timeout_s),
            follow_redirects=True,
            max_redirects=5,
        )
        self._last_hit: dict[str, float] = {}
        self._host_locks: dict[str, asyncio.Lock] = {}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._sem = asyncio.Semaphore(settings.concurrency)

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self) -> "HttpFetcher":
        return self

    async def __aexit__(self, *exc) -> None:
        await self.close()

    # -- politeness ---------------------------------------------------------

    def _lock_for(self, host: str) -> asyncio.Lock:
        if host not in self._host_locks:
            self._host_locks[host] = asyncio.Lock()
        return self._host_locks[host]

    async def _throttle(self, host: str, delay: float | None = None) -> None:
        delay = self.settings.per_host_delay_s if delay is None else delay
        last = self._last_hit.get(host, 0.0)
        wait = last + delay - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_hit[host] = time.monotonic()

    async def _allowed(self, url: str) -> bool:
        if not self.settings.respect_robots:
            return True
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            self._robots[base] = await self._load_robots(base)
        rp = self._robots[base]
        if rp is None:
            return True
        return rp.can_fetch(self.settings.user_agent, url)

    async def _load_robots(self, base: str) -> RobotFileParser | None:
        try:
            resp = await self._client.get(f"{base}/robots.txt")
        except httpx.HTTPError:
            return None
        if resp.status_code != 200 or "text" not in resp.headers.get("content-type", "text/plain"):
            return None
        rp = RobotFileParser()
        rp.parse(resp.text.splitlines())
        return rp

    # -- fetch --------------------------------------------------------------

    async def get(self, url: str, *, delay: float | None = None, api: bool = False,
                  headers: dict[str, str] | None = None) -> FetchResult:
        """`api=True` marks a programmatic endpoint (Overpass, search): robots.txt governs
        crawlers on websites, not API clients, so the check is skipped there."""
        host = urlparse(url).netloc.lower()
        if not api and not await self._allowed(url):
            log.info("robots.txt disallows %s", url)
            return FetchResult(url, url, 0, "", "", error="robots_disallowed")

        attempt = 0
        async with self._sem:
            while True:
                async with self._lock_for(host):
                    await self._throttle(host, delay)
                    try:
                        resp = await self._client.get(url, headers=headers)
                    except httpx.TimeoutException:
                        err = "timeout"
                        resp = None
                    except httpx.HTTPError as exc:
                        err = f"http_error:{type(exc).__name__}"
                        resp = None
                    else:
                        err = None
                if resp is not None and resp.status_code not in _RETRYABLE:
                    ctype = resp.headers.get("content-type", "")
                    textual = ("text" in ctype or "json" in ctype or "xml" in ctype
                               or (not ctype and resp.content[:64].lstrip().lower().startswith((b"<!doctype", b"<html", b"{"))))
                    body = decode_body(resp.content, ctype) if textual else ""
                    return FetchResult(url, str(resp.url), resp.status_code, body, ctype)
                attempt += 1
                if attempt > self.settings.max_retries:
                    status = resp.status_code if resp is not None else 0
                    return FetchResult(url, url, status, "", "", error=err or f"status_{status}")
                backoff = min(2.0 ** attempt, 20.0)
                log.debug("retry %s in %.1fs (%s)", url, backoff, err or resp.status_code)
                await asyncio.sleep(backoff)
