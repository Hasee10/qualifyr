"""Daily per-user usage limits for metered APIs.

Default limits are conservative for free-tier sustainability.
Override per resource via GTM_DAILY_LIMIT_{RESOURCE} env vars.
"""

from __future__ import annotations

import os

from gtm_engine.storage.database import Database

DEFAULT_LIMITS: dict[str, int] = {
    "brave": 50,
    "groq": 200,
    "hunter": 10,
    "places": 20,
}


def _limit(resource: str) -> int:
    env = os.environ.get(f"GTM_DAILY_LIMIT_{resource.upper()}")
    if env and env.isdigit():
        return int(env)
    return DEFAULT_LIMITS.get(resource, 100)


def check_usage(db: Database, user_id: str | None, resource: str) -> bool:
    """Check if the user is under the daily limit and increment. Returns True if allowed."""
    if not user_id:
        return True
    return db.check_and_increment_usage(user_id, resource, _limit(resource))


def get_all_usage(db: Database, user_id: str) -> dict[str, dict]:
    """Current usage for all resources, with limits."""
    rows = db.get_usage(user_id)
    usage_map = {r["resource"]: r["daily_count"] for r in rows}
    return {
        resource: {"count": usage_map.get(resource, 0), "limit": _limit(resource)}
        for resource in DEFAULT_LIMITS
    }
