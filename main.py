#!/usr/bin/env python3
"""Entry point for MentorSmith.

Usage:
    python3 main.py
    python3 main.py --check     # start, verify the UI builds, then exit

The installed command is equivalent:

    mentorsmith
    mentorsmith --check

Both share ``mentorsmith.selfcheck``, so the flag means the same thing however
the app was started.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running straight from a checkout without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parent))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MentorSmith — a programming tutor")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Build the UI offscreen, report the environment, then exit.",
    )
    args = parser.parse_args(argv)

    if args.check:
        from mentorsmith.selfcheck import run_self_check

        return run_self_check()

    from mentorsmith.app import main as run_app

    return run_app([])


if __name__ == "__main__":
    sys.exit(main())