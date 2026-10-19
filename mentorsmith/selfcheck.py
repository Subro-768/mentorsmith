"""The ``--check`` self-diagnosis.

Builds the whole UI offscreen, reports what was actually found, and exits.

This lives in the package rather than in ``main.py`` because both entry points
need it. It used to exist only in ``main.py``, so the *installed* command -
``mentorsmith --check`` - silently ignored the flag and launched the full GUI
instead. With no display that sits in the event loop forever, which looks
exactly like a hang: the command neither produced its report nor returned.

Everything printed here is measured, not asserted. A missing compiler shows up
as missing.
"""

from __future__ import annotations

import os
from pathlib import Path


def run_self_check() -> int:
    """Construct the window offscreen, print the environment, return an exit code."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    import mentorsmith
    from mentorsmith.app import create_application
    from mentorsmith.core.curriculum_registry import summaries, total_counts
    from mentorsmith.core.workspaces import WorkspaceManager
    from mentorsmith.execution import detect_all
    from mentorsmith.services.git_tools import GitRepository
    from mentorsmith.ui.main_window import MainWindow

    app = create_application([])
    window = MainWindow()

    try:
        counts = total_counts()
        print(f"MentorSmith {mentorsmith.__version__}")
        print(f"  languages       : {counts['languages']}")
        print(f"  pages built     : {window.stack.count()}")
        print(f"  database        : {window.database.path}")
        print()
        print("  curriculum:")
        for entry in summaries():
            print(
                f"    {entry['label']:11} {entry['lessons']:2} lessons, "
                f"{entry['concepts']:2} concepts, "
                f"{entry['exercises']:2} exercises"
            )
        print()
        print("  toolchains:")
        for _language, info in detect_all().items():
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

        found = GitRepository(Path.cwd()).discover()
        print(
            "    git here     : "
            + (str(found.path) if found else "not a repository (tools still work)")
        )
        workspaces = WorkspaceManager(
            Path.home() / ".local/share/mentorsmith/workspaces"
        )
        print(f"    workspaces   : {len(workspaces.list_ids())}")
    finally:
        # The window holds a database handle and a Qt session; letting it fall
        # out of scope during interpreter shutdown produces warnings that bury
        # the report this function exists to print.
        window.close()
        del window
        del app

    print("\nSelf-check completed: the window was constructed and closed cleanly.")
    return 0


def wants_self_check(argv: list[str] | None) -> bool:
    """True when ``argv`` asks for the self-check.

    Checked by hand rather than with :mod:`argparse` so that an unknown flag
    still reaches argparse and produces a real error message, instead of being
    swallowed because the first argument happened to be ``--check``.
    """
    return "--check" in (argv or [])