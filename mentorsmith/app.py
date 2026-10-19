"""Application bootstrap.

Kept separate from ``main.py`` so the whole UI can be constructed in a test or
a headless smoke check without running the event loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from . import APP_NAME, ORG_NAME, __version__

#: Directory holding the rendered logo PNGs. Generated from ``assets/logo.svg``
#: by ``tools/build_icons.py``.
ICON_DIR = Path(__file__).resolve().parent / "assets" / "icons"

#: Largest first. Qt picks by requested size, so handing it the full set lets
#: the panel use 32px while the window titlebar and task switcher use 256.
ICON_SIZES = (512, 256, 128, 64, 48, 32, 24, 16)


def app_icon() -> QIcon:
    """The MentorSmith icon, or a themed fallback if the PNGs are missing.

    Never raises. A missing or corrupt icon file is a cosmetic problem and must
    not stop the application starting — so this falls back to a generic system
    icon and, failing even that, returns an empty QIcon.
    """
    icon = QIcon()
    for size in ICON_SIZES:
        path = ICON_DIR / f"mentorsmith-{size}.png"
        if path.exists():
            icon.addFile(str(path))
    if not icon.isNull():
        return icon

    # The rendered PNGs are missing (a source checkout that skipped
    # tools/build_icons.py, for example). A generic editor icon is a poor but
    # harmless stand-in; better than a blank window title.
    for name in ("accessories-text-editor", "text-editor", "application-x-executable"):
        themed = QIcon.fromTheme(name)
        if not themed.isNull():
            return themed
    return QIcon()


def create_application(argv: list[str] | None = None) -> QApplication:
    """Return a configured ``QApplication``.

    High-DPI scaling is left at Qt 6's default, which is correct for the
    version-independent behaviour it provides.
    """
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    # Desktop file association, so the .desktop entry can launch this app.
    app.setDesktopFileName("mentorsmith")
    app.setWindowIcon(app_icon())
    return app


def build_window(app: QApplication | None = None):
    """Construct the main window without starting the event loop.

    Returns ``(app, window)`` so callers can drive or shut it down.
    """
    from .ui.main_window import MainWindow

    app = app or create_application()
    window = MainWindow()
    return app, window


def main(argv: list[str] | None = None) -> int:
    """Run the application. Returns the process exit code."""
    app, window = build_window(create_application(argv))
    window.show()
    return app.exec()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())