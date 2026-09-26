"""Bearer-token auth for the API, backed by Supabase Auth.

Until now the API had none - `main.py` said so in its first line, and once it was deployed
to Vercel that meant every lead, contact email and export was readable by anyone with the
URL, and `POST /campaigns/{id}/run` would spend crawl credit for them. CORS did not help:
it is a browser policy, and `curl` ignores it.

This project's Supabase issues **ES256** tokens signed with a rotating key published at
`/auth/v1/.well-known/jwks.json`, so there is no shared secret to distribute - we fetch the
public key and verify locally. Local verification matters on serverless: a round-trip to
Supabase on every request would add latency to every cold start.

Multi-tenant. The token's `sub` (see `current_user_id`) is the account id, and campaigns
carry an `owner_id`; routes scope campaigns and their leads to that owner (see
`require_campaign_access` / `require_lead_access` in `api/main.py`). A campaign created
before multi-tenancy has a NULL owner and stays visible to everyone (legacy/shared), as do
the file-based example campaigns. When auth is disabled or bypassed (local operator, tests)
`current_user_id` is None, which means "no scoping" - the caller sees everything, exactly as
before multi-tenancy.
"""

from __future__ import annotations

import logging
import os

import jwt
from fastapi import HTTPException, Request
from jwt import PyJWKClient

log = logging.getLogger(__name__)

# Only endpoint reachable without a token. Deliberately short: anything not named here is
# protected, so a route added later is safe by default rather than open by default.
#
# /docs and /openapi.json are absent for a different reason - main.py does not register
# them at all unless auth is disabled. FastAPI builds those in its own setup(), outside
# these dependencies, so listing them here would have done nothing.
PUBLIC_PATHS = frozenset({"/health"})

_ALGORITHMS = ["ES256"]
_jwk_client: PyJWKClient | None = None


def _project_url() -> str:
    url = os.environ.get("GTM_SUPABASE_URL", "").strip().rstrip("/")
    if not url:
        raise HTTPException(
            500,
            "GTM_SUPABASE_URL is not set, so no request can be authenticated. Refusing to "
            "serve rather than fall open - an unset variable must never reopen the API.",
        )
    return url


def jwk_client() -> PyJWKClient:
    """Cached JWKS client. Keys are cached in-process, so a warm function never refetches."""
    global _jwk_client
    if _jwk_client is None:
        _jwk_client = PyJWKClient(
            f"{_project_url()}/auth/v1/.well-known/jwks.json",
            cache_keys=True,
            lifespan=3600,
        )
    return _jwk_client


def auth_disabled() -> bool:
    """Explicit local-dev escape hatch.

    Deliberately an opt-*out*: a missing or misspelled variable leaves auth on. The inverse
    - treating "unconfigured" as "allow" - is precisely the failure this module exists to
    fix, and it would fail silently in production.
    """
    return os.environ.get("GTM_AUTH_DISABLED", "").strip().lower() in {"1", "true", "yes"}


def verify_request(request: Request) -> dict | None:
    """Reject anything without a valid, unexpired Supabase access token.

    Registered as an app-wide dependency, so it sees every route including ones that do not
    exist yet.
    """
    if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
        return None

    if auth_disabled():
        log.warning("GTM_AUTH_DISABLED is set: serving %s unauthenticated", request.url.path)
        return None

    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        # WWW-Authenticate is what tells a client this is "log in", not "you cannot".
        raise HTTPException(401, "missing bearer token", headers={"WWW-Authenticate": "Bearer"})

    try:
        signing_key = jwk_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALGORITHMS,
            audience="authenticated",
            issuer=f"{_project_url()}/auth/v1",
        )
        # Stash the verified user so route handlers can scope data to it without re-decoding.
        request.state.user = payload
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "token expired", headers={"WWW-Authenticate": "Bearer"})
    except jwt.PyJWTError as exc:
        # Do not echo the reason back: it tells an attacker which part of a forged token
        # to fix next. The detail goes to the log instead.
        log.info("rejected token on %s: %s", request.url.path, exc)
        raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})


def current_user_id(request: Request) -> str | None:
    """The signed-in user's id (the token's `sub`), or None when auth is disabled or bypassed
    (local operator, tests). None means 'no scoping' — the caller sees everything, which keeps
    single-operator and test behaviour exactly as before multi-tenancy."""
    user = getattr(request.state, "user", None)
    return user.get("sub") if isinstance(user, dict) else None
