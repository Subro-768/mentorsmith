#!/usr/bin/env python3
"""Install MentorSmith as a per-user Linux application.

Everything lands under ``~/.local``, so nothing is written outside the user's
own home and no root access is needed.

Installed:

* ``~/.local/bin/mentorsmith``              a launcher script
* ``~/.local/share/applications/mentorsmith.desktop``
* ``~/.local/share/icons/mentorsmith/<size>x<size>/mentorsmith.png``

Usage::

    python3 tools/install_desktop.py            # install
    python3 tools/install_desktop.py --uninstall
    python3 tools/install_desktop.py --dry-run  # show what would happen

A per-user install is chosen deliberately over a system-wide one: it needs no
``sudo``, it survives a machine-wide package removal, and it is what a single
developer actually wants.

---

Two rules this installer follows, both learned by breaking the user's system.

**It writes only inside its own directory.** The icons go to
``~/.local/share/icons/mentorsmith/``, *not* into the shared ``hicolor`` tree.
An earlier version installed them into ``hicolor`` and wrote an ``index.theme``
there. ``hicolor`` belongs to whatever else installed icons on the machine - a
GNOME extension, another app - and an index listing only our directories makes
every icon in an unlisted directory invisible. Nothing on disk changes when that
happens, so nothing shows why. An ``Icon=`` absolute path needs no theme index
at all, so there is no reason to write one.

**It regenerates no shared caches.** ``gtk-update-icon-cache -f`` against the
user's ``hicolor`` rewrites a cache every other icon on the machine depends on.
``--refresh-caches`` opts back in for a machine that genuinely needs it.
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
#: A directory of our own, deliberately *not* the shared ``hicolor`` tree.
#:
#: hicolor belongs to everything on the machine that ships an icon. Writing an
#: index.theme there, or regenerating its cache, reaches outside this
#: application's footprint - which is how an installer that "only touches
#: ~/.local" ends up breaking somebody else's icons. The desktop entry
#: references the installed PNG by absolute path, so it does not need to sit in
#: an icon theme at all.
ICONS_ROOT = HOME / ".local" / "share" / "icons" / APP_NAME

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


def install(dry: bool = False, refresh_caches: bool = False) -> int:
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
        text = DESKTOP_FILE.read_text(encoding="utf-8")
        # The repository ships `Icon=mentorsmith`, a theme name. For a per-user
        # install that only works if the desktop environment rescans
        # ~/.local/share/icons, which on GNOME often needs a log-out. The
        # desktop entry specification also allows an absolute path, which needs
        # no theme cache at all, so the installed copy uses that.
        absolute_icon = ICONS_ROOT / "256x256" / f"{APP_NAME}.png"
        text = text.replace(
            f"Icon={APP_NAME}",
            f"Icon={absolute_icon}",
        )
        target.write_text(text, encoding="utf-8")
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
            directory = ICONS_ROOT / f"{size}x{size}"
            if dry:
                _say("copy", directory / f"{APP_NAME}.png", dry)
            else:
                directory.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, directory / f"{APP_NAME}.png")
            installed += 1
        print(f"  {'would install' if dry else 'installed'} {installed} icon size(s)")

    if dry:
        return 0

    # Shared caches are deliberately left alone unless asked for; see the
    # module docstring.
    if refresh_caches:
        _refresh_caches()

    print()
    print("Done. Try:")
    print(f"    {APP_NAME}")
    print("  or launch 'MentorSmith' from your application menu.")
    return 0


def _refresh_caches() -> None:
    """Rebuild the icon and desktop caches if the tools are installed."""
    for command, description in (
        # NOTE: the path is our own directory. Pointing this at hicolor
        # rebuilds a cache every other icon on the machine depends on, which is
        # not something an installer for one app should do.
        (["gtk-update-icon-cache", "-f", "-t", "~/.local/share/icons/mentorsmith"],
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


def uninstall(dry: bool = False, refresh_caches: bool = False) -> int:
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

    if not dry and refresh_caches:
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
    parser.add_argument(
        "--refresh-caches",
        action="store_true",
        help=(
            "Also regenerate the desktop and icon caches. Off by default: "
            "these caches are shared with every other per-user application."
        ),
    )
    args = parser.parse_args()

    if args.uninstall:
        return uninstall(dry=args.dry_run, refresh_caches=args.refresh_caches)
    return install(dry=args.dry_run, refresh_caches=args.refresh_caches)


if __name__ == "__main__":
    sys.exit(main())