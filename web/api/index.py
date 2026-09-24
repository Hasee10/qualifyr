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
    (defined as /health, /campaigns, ...) keep matching unmodified."""
    if scope["type"] == "http" and scope["path"].startswith("/api"):
        scope = dict(scope)
        scope["path"] = scope["path"][len("/api"):] or "/"
    await _app(scope, receive, send)
