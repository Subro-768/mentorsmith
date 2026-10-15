#!/usr/bin/env python3
"""Entry point for MentorSmith.

Usage:
    python3 main.py
    python3 main.py --check     # start, verify the UI builds, then exit
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running straight from a checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def _self_check() -> int:
    """Build the whole UI offscreen and report what is actually available.

    Useful for verifying an install on a machine with no display, and for
    confirming that a compiler was found.
    """
    os_environ = __import__("os").environ
    os_environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from mentorsmith.app import create_application
    from mentorsmith.compiler.toolchain import Toolchain
    from mentorsmith.core.curriculum import load_lessons
    from mentorsmith.ui.main_window import MainWindow

    app = create_application([])
    window = MainWindow()

    toolchain = Toolchain()
    info = toolchain.detect()
    active, sandbox_note = toolchain.sandbox_status()

    lessons = load_lessons()
    print(f"MentorSmith {__import__('mentorsmith').__version__}")
    print(f"  lessons loaded : {len(lessons)}")
    print(f"  pages built    : {window.stack.count()}")
    print(f"  compiler       : {info.name or 'NONE FOUND'} ({info.version or 'unknown'})")
    print(f"  sandbox        : {'ACTIVE' if active else 'INACTIVE'}")
    print(f"                   {sandbox_note}")
    print(f"  database       : {window.database.path}")

    window.close()
    del window
    del app
    print("Self-check completed: the window was constructed and closed cleanly.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="MentorSmith — a C++ learning tutor")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build the UI offscreen, report the environment, then exit.",
    )
    args = parser.parse_args()

    if args.check:
        return _self_check()

    from mentorsmith.app import main as run_app

    return run_app()


if __name__ == "__main__":
    sys.exit(main())