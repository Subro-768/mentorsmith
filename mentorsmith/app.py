"""Application bootstrap.

Kept separate from ``main.py`` so the whole UI can be constructed in a test or
a headless smoke check without running the event loop.
"""

from __future__ import annotations

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from . import APP_NAME, ORG_NAME, __version__


def create_application(argv: list[str] | None = None) -> QApplication:
    """Return a configured ``QApplication``.

    High-DPI scaling is left at Qt 6's default, which is correct for the
    version-independent behaviour it provides.
    """
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon.fromTheme("accessories-text-editor"))
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