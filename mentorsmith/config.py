"""Filesystem locations and machine-local, non-secret settings.

Nothing here ever holds an API key. Credentials are read from environment
variables by :mod:`mentorsmith.providers` and are deliberately kept out of
the database and out of version control.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

APP_DIR_NAME = "mentorsmith"

#: Directory holding the lesson Markdown that ships with the source tree.
PACKAGE_ROOT = Path(__file__).resolve().parent
LESSONS_DIR = PACKAGE_ROOT / "lessons"


def data_dir() -> Path:
    """Return the per-user data directory, creating it if needed.

    Honours ``XDG_DATA_HOME`` so the database can live on removable media if
    the user prefers.
    """
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    path = Path(base) / APP_DIR_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    """Location of the SQLite database."""
    return data_dir() / "progress.db"


def work_dir() -> Path:
    """Dedicated directory for compiling and running the learner's C++.

    Kept separate from the source tree so generated binaries and objects can
    never collide with application files.
    """
    path = data_dir() / "workdir"
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_path() -> Path:
    """Location of the non-secret settings file."""
    return data_dir() / "settings.json"


def default_settings() -> dict:
    """Settings the app starts with on a fresh machine."""
    return {
        # Provider configuration. 'base_url' is left blank so no particular
        # vendor is assumed; the user must opt in to one.
        "provider_base_url": "",
        "provider_model": "",
        "provider_kind": "openai_compatible",
        "provider_timeout": 60,
        # Tutor behaviour
        "assistance_level": "guided",
        # Toolchain
        "sandbox_enabled": False,
    }


def load_settings() -> dict:
    """Read settings from disk, falling back to defaults.

    Corrupt or partial files are merged over the defaults rather than
    crashing the app on startup.
    """
    settings = default_settings()
    path = settings_path()
    if not path.exists():
        return settings
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return settings
    if isinstance(stored, dict):
        settings.update({k: v for k, v in stored.items() if k in settings})
    return settings


def save_settings(settings: dict) -> None:
    """Persist settings, keeping only known keys."""
    merged = default_settings()
    merged.update({k: v for k, v in settings.items() if k in merged})
    path = settings_path()
    path.write_text(json.dumps(merged, indent=2, sort_keys=True), encoding="utf-8")


def is_truthy(value: object) -> bool:
    """Parse a permissive boolean used for environment-variable switches."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}