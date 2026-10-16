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
    from mentorsmith.core.curriculum_registry import summaries, total_counts
    from mentorsmith.execution import detect_all
    from mentorsmith.ui.main_window import MainWindow

    app = create_application([])
    window = MainWindow()

    counts = total_counts()
    print(f"MentorSmith {__import__('mentorsmith').__version__}")
    print(f"  languages       : {counts['languages']}")
    print(f"  pages built     : {window.stack.count()}")
    print(f"  database        : {window.database.path}")
    print()
    print("  curriculum:")
    for entry in summaries():
        print(
            f"    {entry['label']:11} {entry['lessons']:2} lessons, "
            f"{entry['concepts']:2} concepts, {entry['exercises']:2} exercises"
        )
    print()
    print("  toolchains:")
    for language, info in detect_all().items():
        print(f"    {info.describe()}")
    print()
    sandbox_note = window.lesson_view.status_label.text()
    print(f"  C++ containment: {sandbox_note}")
    print()
    print("  developer tools:")
    tab_labels = [
        window.developer_view.tabs.tabText(i)
        for i in range(window.developer_view.tabs.count())
    ]
    print(f"    tabs         : {len(tab_labels)} ({', '.join(tab_labels)})")

    from pathlib import Path as _Path

    from mentorsmith.core.workspaces import WorkspaceManager
    from mentorsmith.services.git_tools import GitRepository

    found = GitRepository(_Path.cwd()).discover()
    print(
        "    git here     : "
        + (str(found.path) if found else "not a repository (tools still work)")
    )
    workspaces = WorkspaceManager(
        _Path.home() / ".local/share/mentorsmith/workspaces"
    )
    print(f"    workspaces   : {len(workspaces.list_ids())}")

    window.close()
    del window
    del app
    print("\nSelf-check completed: the window was constructed and closed cleanly.")
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