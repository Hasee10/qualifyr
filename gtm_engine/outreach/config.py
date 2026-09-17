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
    delay_between_sends_s: float = 45.0
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
    def credentials_present(self) -> bool:
        return bool(self.smtp_user and self.smtp_password)


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
