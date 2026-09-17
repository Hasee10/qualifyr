"""Durable send ledger, committed to the repo by CI. The SQLite DB can be lost between
GitHub runners; this file cannot, so it is the final guard against sending Email 1
twice to the same address."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from gtm_engine.models import utcnow


class Ledger:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict = {"sent": {}, "stopped": {}}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                self.data = {"sent": loaded.get("sent", {}), "stopped": loaded.get("stopped", {})}
            except json.JSONDecodeError:
                pass

    # -- queries ------------------------------------------------------------

    def has_sent(self, email: str, step: str) -> bool:
        return step in self.data["sent"].get(email.lower(), {})

    def steps_sent(self, email: str) -> dict[str, dict]:
        return self.data["sent"].get(email.lower(), {})

    def is_stopped(self, email: str) -> bool:
        return email.lower() in self.data["stopped"]

    def sent_on(self, day_prefix: str) -> int:
        return sum(
            1 for steps in self.data["sent"].values()
            for rec in steps.values() if rec.get("at", "").startswith(day_prefix)
        )

    # -- mutations -----------------------------------------------------------

    def record_sent(self, email: str, step: str, message_id: str | None, lead_id: str,
                    at: datetime | None = None) -> None:
        rec = self.data["sent"].setdefault(email.lower(), {})
        rec[step] = {"at": (at or utcnow()).isoformat(), "message_id": message_id, "lead_id": lead_id}
        self.save()

    def record_stop(self, email: str, reason: str) -> None:
        self.data["stopped"][email.lower()] = {"reason": reason, "at": utcnow().isoformat()}
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=1, sort_keys=True), encoding="utf-8")
