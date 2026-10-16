#!/usr/bin/env python3
"""Run the execution security audit and print the evidence.

Every check executes real code and observes the real result. Checks that cannot
run on this host are reported as SKIPPED with the reason, never as passed.

Usage::

    python3 tools/security_audit.py            # human-readable report
    python3 tools/security_audit.py --json     # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mentorsmith.services.security_audit import run_audit  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    args = parser.parse_args()

    report = run_audit()

    if args.json:
        print(json.dumps({
            "ran_at": report.ran_at,
            "platform": report.platform,
            "verdict": report.verdict,
            "checks": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "proves": c.proves,
                    "does_not_prove": c.does_not_prove,
                    "detail": c.detail,
                    "evidence": c.evidence,
                }
                for c in report.checks
            ],
        }, indent=2))
        # Non-zero only on a real failure, not on a skip.
        return 1 if report.failed else 0

    print("MentorSmith execution security audit")
    print("=" * 70)
    print(f"Verdict: {report.verdict}")
    print(f"Platform: {report.platform}")
    print(f"Ran at:  {report.ran_at}")
    print("=" * 70)
    for check in report.checks:
        print()
        print(check.describe())
    print()
    print("=" * 70)
    print(
        "A timeout and resource limits are not a sandbox. Even with bubblewrap "
        "enabled, containment relies on unprivileged user namespaces and is far "
        "weaker than a VM or a configured container. Do not run genuinely hostile "
        "code here."
    )
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())