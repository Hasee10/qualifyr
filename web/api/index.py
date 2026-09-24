"""Vercel Python entrypoint. Wraps the FastAPI app defined in the repo-root gtm_engine
package — no endpoint logic lives here. Requires Project Settings -> "Include files
outside the root directory" so this function can import gtm_engine (Root Directory is
set to web/)."""

import sys
from pathlib import Path

# Root Directory is web/, so the repo root (containing gtm_engine/) is two levels up
# from this file (web/api/index.py) — not on sys.path by default.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from gtm_engine.api.main import app as _app  # noqa: E402


async def app(scope, receive, send):
    """Strip the /api prefix that vercel.json's rewrite adds, so gtm_engine's routes
    (defined as /health, /campaigns, ...) keep matching unmodified.

    The rewrite still hands us the *original* request path, so /api/health arrives here
    as /api/health even though it was routed via /api/index. Note the rewrite target is
    "/api/index", not "/api/index.py": Vercel addresses functions by their extensionless
    route, and a destination that does not resolve is silently ignored, which drops the
    request through to Next.js and yields a 500 that looks nothing like a Python error.
    """
    if scope["type"] == "http" and scope["path"].startswith("/api"):
        scope = dict(scope)
        scope["path"] = scope["path"][len("/api"):] or "/"
    await _app(scope, receive, send)
