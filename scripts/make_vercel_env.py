"""Generate .env.vercel — a bulk-import file for Vercel's Environment Variables screen.

Vercel accepts a pasted/dragged .env there and creates every variable at once, which
beats ~18 hand-typed form fills (and makes the 2 KB service-account private key a
non-event).

Reads .env plus sheets-api-key.json; writes .env.vercel. Both are gitignored.
Run:  .venv\\Scripts\\python.exe scripts\\make_vercel_env.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# What the Vercel-hosted API function actually reads. Deliberately excludes the crawl-only
# keys (Brave/Hunter) — those are consumed by the GitHub Actions jobs, and shipping a
# secret to a host that never uses it is pure downside.
VERCEL_KEYS = [
    "GTM_DATABASE_URL",
    "GTM_GITHUB_TOKEN",
    "GTM_GITHUB_REPO",
    "GTM_GITHUB_REF",
    "GTM_SHEETS_SPREADSHEET_ID",
    "GTM_GROQ_API_KEY",
    "GTM_GMAIL_CLIENT_ID",
    "GTM_GMAIL_CLIENT_SECRET",
    "GTM_GMAIL_REFRESH_TOKEN",
    "GTM_SMTP_USER",
    "GTM_SMTP_PASSWORD",
]


def read_env(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        out[key.strip()] = value.strip()
    return out


def main() -> None:
    env = read_env(ROOT / ".env")
    lines: list[str] = []
    missing: list[str] = []

    for key in VERCEL_KEYS:
        value = env.get(key, "")
        if not value:
            missing.append(key)
            continue
        # Supabase hands out :5432 (session pooler) by default, which holds a connection
        # per client — fine for a long-lived process, fatal for serverless, where every
        # cold function grabs one and the project's limit is gone. :6543 is the
        # transaction pooler. Rewritten only for Vercel; local .env keeps :5432.
        if key == "GTM_DATABASE_URL":
            value = value.replace(".supabase.com:5432/", ".supabase.com:6543/")
        lines.append(f"{key}={value}")

    # The whole service account, collapsed to one line (\n inside the private key is
    # preserved by json.dumps as the two-character escape, which is what Google expects).
    creds = ROOT / "sheets-api-key.json"
    if creds.exists():
        compact = json.dumps(json.loads(creds.read_text(encoding="utf-8")), separators=(",", ":"))
        lines.append(f"GTM_SHEETS_CREDENTIALS_JSON={compact}")
    else:
        missing.append("GTM_SHEETS_CREDENTIALS_JSON (sheets-api-key.json not found)")

    out = ROOT / ".env.vercel"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"wrote {out} ({len(lines)} variables)")
    for key in VERCEL_KEYS:
        if key in env and env[key]:
            print(f"  ok      {key}")
    for key in missing:
        print(f"  MISSING {key}")
    if missing:
        print("\nMissing values are left out entirely rather than written blank —")
        print("an empty env var on Vercel reads as 'configured' and silently breaks things.")
    print("\nNEXT_PUBLIC_API_URL is not included: set it in Vercel to")
    print("https://<your-deployment>.vercel.app/api once you know the URL.")


if __name__ == "__main__":
    main()
