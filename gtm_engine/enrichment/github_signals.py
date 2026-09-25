"""GitHub org activity: recent pushes/releases across a company's public repos are a
proxy for an active, staffed engineering function - relevant both as a buying signal
(they have a technical team and a budget) and for personalization. Public REST API,
keyless at 60 req/hr per IP, or 5000 req/hr with GTM_HUNTER_API_KEY's sibling
GTM_GITHUB_TOKEN (see docs/API_KEYS.md). Opportunistic like the other external
signals: a miss (no org, rate-limited, private repos only) is silent."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

from gtm_engine.scraping.fetcher import Fetcher

REPOS_URL = "https://api.github.com/orgs/{org}/repos?type=public&sort=pushed&direction=desc&per_page=5"

_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def _headers() -> dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GTM_GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _org_slug(company_name: str, domain: str | None) -> str | None:
    slug = _SLUG_RE.sub("", (domain.split(".")[0] if domain else company_name.lower()))
    return slug or None


@dataclass
class GithubActivity:
    org: str
    url: str
    public_repos: int
    last_pushed_at: str | None
    stars_total: int


async def github_activity(fetcher: Fetcher, company_name: str, domain: str | None) -> GithubActivity | None:
    slug = _org_slug(company_name, domain)
    if not slug:
        return None
    result = await fetcher.get(REPOS_URL.format(org=slug), api=True, headers=_headers())
    if not result.ok:
        return None
    try:
        repos = json.loads(result.text)
    except json.JSONDecodeError:
        return None
    if not isinstance(repos, list) or not repos:
        return None
    pushed = [r.get("pushed_at") for r in repos if r.get("pushed_at")]
    if not pushed:
        return None
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    return GithubActivity(org=slug, url=f"https://github.com/{slug}", public_repos=len(repos),
                           last_pushed_at=max(pushed), stars_total=stars)
