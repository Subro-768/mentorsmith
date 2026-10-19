"""Filesystem locations, non-secret settings, and stored credentials.

Two files, deliberately separated by sensitivity:

* ``settings.json``  - ordinary preferences. Safe to read, diff or paste.
* ``secrets.json``   - the API key, created ``0600`` and never merged into
  ``settings.json``.

The separation exists because a key typed into the app has to live somewhere.
Originally credentials came from the environment alone and nothing here held
one; in-app entry was added on request, and the way to keep it honest is to make
it a distinct, permission-restricted file rather than a field in a file people
routinely open and share.

Nothing here ever *logs* a key, and :func:`describe` equivalents in the provider
are written to stay secret-free.
"""

from __future__ import annotations

import json
import os
import shutil
from functools import lru_cache
from pathlib import Path

APP_DIR_NAME = "mentorsmith"

#: Directory holding the lesson Markdown that ships with the source tree.
PACKAGE_ROOT = Path(__file__).resolve().parent
LESSONS_DIR = PACKAGE_ROOT / "lessons"


def lessons_dir(language: str = "cpp") -> Path:
    """Lessons for one language, e.g. ``lessons/cpp``.

    Kept per language from Phase 4 onwards. The C++ lessons were moved here
    unchanged when the other language tracks were added.
    """
    return LESSONS_DIR / language


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


def secrets_path() -> Path:
    """Location of the credentials file.

    Kept apart from :func:`settings_path` so that sharing, diffing or backing
    up the settings file cannot leak a key by accident.
    """
    return data_dir() / "secrets.json"


def _permissions_warning(path: Path) -> str | None:
    """Return a warning if ``path`` is readable by others, else None."""
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        return None
    if mode & 0o077:
        return (
            f"{path} is mode {mode:04o}; other users on this machine can read "
            f"your API key. Run: chmod 600 {path}"
        )
    return None


def load_api_key() -> str:
    """Return the stored API key, or "" if there is none.

    Reading is deliberately forgiving: a corrupt file, one written by a future
    version, or one the user cannot read must not stop the app from starting.
    The environment variable remains the fallback, so a key set either way
    works.
    """
    path = secrets_path()
    if not path.exists():
        return ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    if isinstance(data, dict):
        value = data.get("api_key", "")
        if isinstance(value, str):
            return value.strip()
    return ""


def save_api_key(value: str) -> None:
    """Store (or, with an empty value, remove) the API key.

    Written with ``0600`` before any content is written, because the default
    umask on some systems would otherwise leave it group- or world-readable for
    the window between creation and chmod.
    """
    path = secrets_path()
    value = (value or "").strip()

    if not value:
        if path.exists():
            path.unlink()
        return

    # O_CREAT only applies the mode to a *new* file, and O_TRUNC leaves an
    # existing file's mode alone. So the mode is set explicitly afterwards,
    # and the directory is tightened too - a 0600 file inside a world-readable
    # directory still leaks its name and size.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"api_key": value}, handle, indent=2)
    os.chmod(path, 0o600)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        # A shared data directory is legitimate (XDG_DATA_HOME); not fatal.
        pass


def clear_api_key() -> bool:
    """Delete the stored key. Returns True if a file was removed."""
    path = secrets_path()
    if not path.exists():
        return False
    path.unlink()
    return True


@lru_cache(maxsize=1)
def sandbox_available() -> bool:
    """Whether bubblewrap is installed on this machine.

    Cached: it is a PATH scan, and the answer cannot change while the app
    is running.
    """
    return shutil.which("bwrap") is not None


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
        # Toolchain.
        #
        # The sandbox is ON by default wherever bubblewrap is installed.
        # Learner code is code the learner did not write, and running it
        # with the user's own file access means a stray `rm -rf` or a
        # mistake in a path can do real damage. Where bubblewrap is not
        # installed the setting cannot take effect anyway, so it stays off
        # rather than promising containment that is not there.
        #
        # The user can turn it off, and their choice is remembered: the
        # default only applies to a setting that has never been set.
        "sandbox_enabled": sandbox_available(),
        # Appearance — "dark_orange" | "dark_purple" | "light"
        "theme": "dark_orange",
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