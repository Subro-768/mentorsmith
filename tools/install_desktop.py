#!/usr/bin/env python3
"""Install MentorSmith as a per-user Linux application.

Everything lands under ``~/.local``, so nothing is written outside the user's
own home and no root access is needed.

Installed:

* ``~/.local/bin/mentorsmith``              a launcher script
* ``~/.local/share/applications/mentorsmith.desktop``
* ``~/.local/share/icons/hicolor/<size>x<size>/apps/mentorsmith.png``

Then refreshes the desktop and icon caches when the tools for them are present.

Usage::

    python3 tools/install_desktop.py            # install
    python3 tools/install_desktop.py --uninstall
    python3 tools/install_desktop.py --dry-run  # show what would happen

A per-user install is chosen deliberately over a system-wide one: it needs no
``sudo``, it survives a machine-wide package removal, and it is what a single
developer actually wants.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

APP_NAME = "mentorsmith"
DESKTOP_FILE = ROOT / "mentorsmith.desktop"
ICON_SRC = ROOT / "mentorsmith" / "assets" / "icons"

HOME = Path.home()
BIN_DIR = HOME / ".local" / "bin"
APPS_DIR = HOME / ".local" / "share" / "applications"
ICONS_ROOT = HOME / ".local" / "share" / "icons" / "hicolor"

#: Sizes to install, matching the icon theme's directory naming.
ICON_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

LAUNCHER = """#!/usr/bin/env python3
\"\"\"MentorSmith launcher.

Points at the checkout it was installed from, so editing the source and
re-running takes effect with no reinstall.
\"\"\"
import sys

sys.path.insert(0, {repo!r})

from mentorsmith.app import main

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
"""


def _say(do: str, path: Path, dry: bool) -> None:
    prefix = "would " if dry else ""
    print(f"  {prefix}{do} {path}")


def install(dry: bool = False) -> int:
    if not DESKTOP_FILE.exists():
        print(f"missing {DESKTOP_FILE}; run from a source checkout", file=sys.stderr)
        return 1

    print(f"Installing MentorSmith into {HOME / '.local'}")

    # -- launcher ------------------------------------------------------
    BIN_DIR.mkdir(parents=True, exist_ok=True)
    launcher = BIN_DIR / APP_NAME
    if dry:
        _say("write", launcher, dry)
    else:
        launcher.write_text(LAUNCHER.format(repo=str(ROOT)), encoding="utf-8")
        launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        _say("wrote executable", launcher, dry)

    # -- desktop entry -------------------------------------------------
    APPS_DIR.mkdir(parents=True, exist_ok=True)
    target = APPS_DIR / f"{APP_NAME}.desktop"
    if dry:
        _say("copy", target, dry)
    else:
        shutil.copy2(DESKTOP_FILE, target)
        target.chmod(target.stat().st_mode | stat.S_IXUSR)
        _say("installed", target, dry)

    # -- icons ---------------------------------------------------------
    if not ICON_SRC.exists():
        print(f"  ! no rendered icons in {ICON_SRC}; run tools/build_icons.py",
              file=sys.stderr)
    else:
        installed = 0
        for size in ICON_SIZES:
            source = ICON_SRC / f"{APP_NAME}-{size}.png"
            if not source.exists():
                continue
            directory = ICONS_ROOT / f"{size}x{size}" / "apps"
            if dry:
                _say("copy", directory / f"{APP_NAME}.png", dry)
            else:
                directory.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, directory / f"{APP_NAME}.png")
            installed += 1
        print(f"  {'would install' if dry else 'installed'} {installed} icon size(s)")

    if dry:
        return 0

    # -- refresh caches -------------------------------------------------
    _refresh_caches()

    print()
    print("Done. Try:")
    print(f"    {APP_NAME}")
    print("  or launch 'MentorSmith' from your application menu.")
    return 0


def _refresh_caches() -> None:
    """Rebuild the icon and desktop caches if the tools are installed."""
    for command, description in (
        (["gtk-update-icon-cache", "-f", "-t", "~/.local/share/icons/hicolor"],
         "icon cache"),
        (["update-desktop-database", str(APPS_DIR)], "desktop database"),
    ):
        if not shutil.which(command[0]):
            print(f"  - skipped {description} ({command[0]} not installed)")
            continue
        expanded = [part.replace("~", str(HOME)) for part in command]
        try:
            subprocess.run(expanded, capture_output=True, timeout=30, check=False)
            print(f"  refreshed {description}")
        except (OSError, subprocess.SubprocessError) as error:
            print(f"  - could not refresh {description}: {error}")

    # Icon themes only pick up new directories on XDG_DATA_DIRS change; warn if
    # this is the first install so the user knows a log-out may be needed.
    if str(HOME / ".local" / "share") not in os.environ.get("XDG_DATA_DIRS", ""):
        print(
            "  note: if the icon does not appear in the menu straight away, "
            "log out and back in so the desktop environment rescans "
            "~/.local/share."
        )


def uninstall(dry: bool = False) -> int:
    print(f"Removing MentorSmith from {HOME / '.local'}")
    launcher = BIN_DIR / APP_NAME
    desktop = APPS_DIR / f"{APP_NAME}.desktop"
    for path in (launcher, desktop):
        if not path.exists():
            continue
        if dry:
            _say("remove", path, dry)
        else:
            path.unlink()
            _say("removed", path, dry)

    removed = 0
    for size in ICON_SIZES:
        path = ICONS_ROOT / f"{size}x{size}" / "apps" / f"{APP_NAME}.png"
        if not path.exists():
            continue
        if dry:
            _say("remove", path, dry)
        else:
            path.unlink()
        removed += 1
    print(f"  {'would remove' if dry else 'removed'} {removed} icon(s)")

    if not dry:
        _refresh_caches()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # These are orthogonal, not mutually exclusive: --uninstall says *what* to
    # do and --dry-run says *whether to do it*. Being able to preview an
    # uninstall matters more than the tidiness of an exclusive group.
    parser.add_argument(
        "--uninstall", action="store_true", help="Remove the install."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without changing anything.",
    )
    args = parser.parse_args()

    if args.uninstall:
        return uninstall(dry=args.dry_run)
    return install(dry=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())