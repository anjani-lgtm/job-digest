"""Configuration loader — reads .env and JSON config files."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from job_digest.models import Preferences, Profile

_ROOT = Path(__file__).resolve().parent.parent.parent  # project root


def load_config() -> None:
    """Load .env file into environment."""
    load_dotenv(_ROOT / ".env")


def get_profile(path: Path | None = None) -> Profile:
    path = path or _ROOT / "config" / "profile.json"
    return Profile.model_validate(json.loads(path.read_text()))


def get_preferences(path: Path | None = None) -> Preferences:
    path = path or _ROOT / "config" / "preferences.json"
    return Preferences.model_validate(json.loads(path.read_text()))


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_list(key: str) -> list[str]:
    """Comma-separated env var → list of non-empty strings."""
    raw = os.environ.get(key, "")
    return [s.strip() for s in raw.split(",") if s.strip()]
