"""Outreach configuration: settings (limits, windows, delays) and the 3-step templates."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from gtm_engine.config.loader import CONFIG_DIR

OUTREACH_DIR = CONFIG_DIR / "outreach"


class OutreachSettings(BaseModel):
    sender_name: str = "Your Name"
    reply_to: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    imap_host: str = "imap.gmail.com"
    daily_limit: int = 40
    delay_between_sends_s: float = 45.0   # used only when jitter is disabled
    # Random spacing between sends; humans do not email every 45.0 s exactly.
    jitter_min_s: float = 30.0
    jitter_max_s: float = 120.0
    # Warm-up: a fresh mailbox starts small and grows to daily_limit. Day 1 = first send.
    warmup_enabled: bool = True
    warmup_start_per_day: int = 5
    warmup_step_per_day: int = 2
    # Guard: pause the mailbox for the day when bounces get out of hand.
    max_bounce_rate: float = 0.10
    min_sends_for_bounce_rate: int = 5
    send_window_start_hour: int = 9
    send_window_end_hour: int = 18
    timezone: str = "Asia/Karachi"
    skip_weekends: bool = True
    followup_1_after_days: int = 3
    followup_2_after_days: int = 4
    require_approval: bool = True

    @property
    def smtp_user(self) -> str | None:
        return os.environ.get("GTM_SMTP_USER") or None

    @property
    def smtp_password(self) -> str | None:
        return os.environ.get("GTM_SMTP_PASSWORD") or None

    @property
    def oauth_present(self) -> bool:
        from gtm_engine.outreach.gmail_oauth import credentials_from_env
        return bool(self.smtp_user and credentials_from_env())

    @property
    def credentials_present(self) -> bool:
        """OAuth2 (preferred) or App Password."""
        return bool(self.smtp_user and (self.smtp_password or self.oauth_present))

    @property
    def auth_mode(self) -> str:
        if self.oauth_present:
            return "oauth2"
        if self.smtp_user and self.smtp_password:
            return "app_password"
        return "none"

    def effective_daily_cap(self, days_active: int | None) -> int:
        """Warm-up ramp: day 1 -> warmup_start_per_day, +step each day, capped at daily_limit."""
        if not self.warmup_enabled or days_active is None:
            return self.daily_limit
        return min(self.daily_limit, self.warmup_start_per_day + self.warmup_step_per_day * max(days_active - 1, 0))


class EmailTemplate(BaseModel):
    subject: str
    body: str


class Templates(BaseModel):
    email_1: EmailTemplate
    followup_1: EmailTemplate
    followup_2: EmailTemplate
    footer: str = ""
    fallbacks: dict[str, str] = Field(default_factory=dict)

    def for_step(self, step: str) -> EmailTemplate:
        return getattr(self, step)


def _read(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_outreach_settings(path: Path | None = None) -> OutreachSettings:
    data = _read(path or OUTREACH_DIR / "settings.yaml")
    for key in OutreachSettings.model_fields:
        env = os.environ.get(f"GTM_OUTREACH_{key.upper()}")
        if env is not None:
            data[key] = env
    return OutreachSettings.model_validate(data)


def load_templates(path: Path | None = None) -> Templates:
    return Templates.model_validate(_read(path or OUTREACH_DIR / "templates.yaml"))
