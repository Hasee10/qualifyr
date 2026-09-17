from __future__ import annotations

import os
from pathlib import Path

import yaml

from gtm_engine.config.schema import CampaignConfig, DefaultRules, EngineSettings

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
DEFAULTS_DIR = CONFIG_DIR / "defaults"


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def load_campaign(path: str | Path) -> CampaignConfig:
    path = Path(path)
    data = _read_yaml(path)
    if not data:
        raise FileNotFoundError(f"campaign config not found or empty: {path}")
    if data.get("seed_csv"):
        seed = Path(data["seed_csv"])
        if not seed.is_absolute():
            seed = (path.parent / seed).resolve()
        data["seed_csv"] = seed
    return CampaignConfig.model_validate(data)


def load_defaults(defaults_dir: Path = DEFAULTS_DIR) -> DefaultRules:
    merged: dict = {}
    for file in sorted(defaults_dir.glob("*.yaml")):
        merged.update(_read_yaml(file))
    return DefaultRules.model_validate(merged)


def load_settings(path: Path | None = None) -> EngineSettings:
    data = _read_yaml(path or CONFIG_DIR / "engine.yaml")
    # Environment overrides: GTM_DB_PATH, GTM_CONCURRENCY, ...
    for key in EngineSettings.model_fields:
        env_val = os.environ.get(f"GTM_{key.upper()}")
        if env_val is not None:
            data[key] = env_val
    settings = EngineSettings.model_validate(data)
    for attr in ("db_path", "export_dir"):
        p = getattr(settings, attr)
        if not p.is_absolute():
            setattr(settings, attr, PROJECT_ROOT / p)
    return settings
