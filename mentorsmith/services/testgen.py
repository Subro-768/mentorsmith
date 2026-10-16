"""AI-assisted test generation, with a review gate before anything runs.

Phase 5 requires three things this module is built around:

* **Review before execution.** :class:`ProposedTest` is inert. It holds source
  text that has never been executed. :meth:`ProposedTest.execute` is the only
  thing that runs it, and it requires an explicit flag.
* **Proposed is not executed.** The report keeps them separate and says which is
  which in every summary.
* **A passing generated suite proves nothing about completeness.** This is stated
  in the generated output itself, not just in the docs, because that is where
  someone reading a green run will look.

Coverage that is asked for, and why each matters:

``normal``      the ordinary path. Without it a function may not work at all.
``boundary``    zero, one, empty, largest valid. Off-by-one lives here.
``invalid``     wrong type, negative where positive is required. Validation
                code that is never exercised tends not to exist.
``expected_failure``  the case that *must* raise. Often the most valuable test
                in the file and the one most often missing.
``prior_bug``   a mistake that already happened, pinned so it cannot recur.

There is no path in this module that writes into the tutor's own source tree.
Tests land in a learner workspace, or nowhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class CaseKind(str, Enum):
    NORMAL = "normal"
    BOUNDARY = "boundary"
    INVALID = "invalid"
    EXPECTED_FAILURE = "expected_failure"
    PRIOR_BUG = "prior_bug"

    @property
    def label(self) -> str:
        return {
            CaseKind.NORMAL: "normal case",
            CaseKind.BOUNDARY: "boundary",
            CaseKind.INVALID: "invalid input",
            CaseKind.EXPECTED_FAILURE: "expected failure",
            CaseKind.PRIOR_BUG: "regression (prior bug)",
        }[self]


class Language(str, Enum):
    PYTHON = "python"
    CPP = "cpp"


@dataclass
class ProposedTest:
    """Generated test source that has **not** been executed."""

    kind: CaseKind
    name: str
    source: str
    language: Language
    #: Why the model thinks this case matters.
    rationale: str = ""
    executed: bool = False
    passed: bool | None = None
    output: str = ""
    #: Where the test was written, once it has been. Empty until then.
    saved_to: str = ""

    @property
    def is_regression(self) -> bool:
        return self.kind is CaseKind.PRIOR_BUG

    def describe(self) -> str:
        status = (
            "PROPOSED (never run)"
            if not self.executed
            else "EXECUTED: passed" if self.passed else "EXECUTED: failed"
        )
        lines = [f"[{status}] {self.kind.label} — {self.name}"]
        if self.rationale:
            lines.append(f"  Why: {self.rationale}")
        return "\n".join(lines)

    def execute(
        self,
        *,
        work_dir: Path,
        timeout: int = 60,
        confirmed: bool = False,
        source_under_test: str = "",
        extra_args: list[str] | None = None,
    ) -> bool:
        """Run the test. Requires ``confirmed=True``.

        Runs in ``work_dir`` with the same resource limits and process-group
        isolation as learner code, because generated code is still code.
        """
        if not confirmed:
            raise PermissionError(
                "Refusing to run a generated test without confirmation. Show the "
                "source to the learner first and pass confirmed=True."
            )
        if self.executed:
            return bool(self.passed)

        from ..execution.base import RunSpec, start

        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        if self.language is Language.PYTHON:
            if source_under_test:
                (work_dir / "module_under_test.py").write_text(source_under_test, encoding="utf-8")
            (work_dir / "test_generated.py").write_text(self.source, encoding="utf-8")
            argv = ["python3", "-I", "-B", str(work_dir / "test_generated.py")]
        else:
            if source_under_test:
                (work_dir / "main.cpp").write_text(source_under_test, encoding="utf-8")
            (work_dir / "test_generated.cpp").write_text(self.source, encoding="utf-8")
            artifact = work_dir / "test_generated"
            argv = [
                "g++", "-std=c++17", "-Wall", "-Wextra",
                str(work_dir / "test_generated.cpp"),
                *(extra_args or []),
                "-o", str(artifact),
            ]

        handle = start(RunSpec(argv=argv, cwd=work_dir, timeout=timeout))
        result = handle.wait(timeout)
        handle.stop()

        self.executed = True
        self.passed = result.ok
        self.output = result.combined_output
        return bool(result.ok)


@dataclass
class TestGenReport:
    """Proposed and executed tests, kept explicitly apart."""

    target: str
    language: Language
    proposed: list[ProposedTest] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )
    errors: list[str] = field(default_factory=list)

    @property
    def executed(self) -> list[ProposedTest]:
        return [t for t in self.proposed if t.executed]

    @property
    def unexecuted(self) -> list[ProposedTest]:
        return [t for t in self.proposed if not t.executed]

    @property
    def failing(self) -> list[ProposedTest]:
        return [t for t in self.proposed if t.executed and not t.passed]

    def coverage_gaps(self) -> list[str]:
        """Which kinds of case were never proposed, including by the model.

        A generated suite with no `expected_failure` case has usually not
        checked the code's error handling at all.
        """
        present = {t.kind for t in self.proposed}
        missing = [kind for kind in CaseKind if kind not in present]
        return [f"no {kind.label} was proposed" for kind in missing]

    def summary(self) -> str:
        proposed = len(self.proposed)
        if proposed == 0:
            return f"No tests were proposed for {self.target}."
        parts = [
            f"{proposed} test(s) proposed for {self.target} "
            f"({len(self.unexecuted)} not yet run).",
        ]
        if self.executed:
            failed = len(self.failing)
            parts.append(
                f"{len(self.executed)} executed, "
                + (f"{failed} failed." if failed else "all passed.")
            )
        gaps = self.coverage_gaps()
        if gaps:
            parts.append("Still uncovered: " + "; ".join(gaps) + ".")
        parts.append(
            "A passing generated suite does not prove the code is correct. It "
            "only proves these specific cases behave as written."
        )
        return " ".join(parts)

    def describe(self) -> str:
        blocks = [self.summary(), ""]
        for title, group in (
            ("PROPOSED — REVIEW BEFORE RUNNING", self.unexecuted),
            ("EXECUTED", self.executed),
        ):
            if not group:
                continue
            blocks.append(f"=== {title} ===")
            blocks += [t.describe() for t in group]
            blocks.append("")
        if self.failing:
            blocks.append("=== FAILURES ===")
            for test in self.failing:
                blocks.append(f"{test.name}: {test.output[:500]}")
            blocks.append("")
        return "\n".join(blocks)


# ======================================================================
# Prompting and parsing
# ======================================================================

_GEN_SYSTEM = (
    "You write tests that find real bugs. Propose cases a careless developer "
    "would forget: the boundary, the invalid input, the thing that must raise, "
    "and the mistake that was already made once. Do not write filler tests that "
    "only restate the obvious. If the code has no error handling, say so rather "
    "than writing a test that passes anyway."
)

_KIND_HINTS = {
    CaseKind.NORMAL: "the ordinary successful path",
    CaseKind.BOUNDARY: "zero, one, empty, and the largest valid value",
    CaseKind.INVALID: "the wrong type, or a value outside the valid range",
    CaseKind.EXPECTED_FAILURE: "the case that must raise an error",
    CaseKind.PRIOR_BUG: "a mistake that was actually made before",
}


def build_testgen_prompt(
    source: str,
    *,
    target: str = "the module below",
    language: Language = Language.PYTHON,
    prior_bugs: list[str] | None = None,
    max_chars: int = 30_000,
) -> str:
    """Ask for cases in a form that can be parsed back out reliably."""
    kinds = "\n".join(f"- {kind.value}: {hint}" for kind, hint in _KIND_HINTS.items())
    bugs = ""
    if prior_bugs:
        bugs = (
            "\nBugs already found in this code, which the tests should catch if "
            "they ever come back:\n"
            + "\n".join(f"- {b}" for b in prior_bugs)
            + "\n"
        )
    body = source[:max_chars]
    return (
        f"Propose tests for {target}.\n\n"
        f"Cover these kinds of case:\n{kinds}\n"
        f"{bugs}\n"
        "For each case output exactly:\n"
        "```\n"
        "kind: normal\n"
        "name: short_snake_case_name\n"
        "why: one sentence on what could break here\n"
        "code:\n"
        "<the test function, or the full test file if it is C++>\n"
        "```\n\n"
        "--- source ---\n"
        f"{body}\n"
    )


_KIND_RE = re.compile(r"kind\s*:\s*([a-z_]+)", re.IGNORECASE)


def _extract_code_block(text: str) -> str:
    """Pull the fenced block that follows a ``code:`` marker."""
    lines = text.splitlines()
    collecting = False
    fence: list[str] = []
    depth_fence = ""
    for line in lines:
        stripped = line.strip()
        if not collecting:
            if stripped.lower().startswith("code:"):
                collecting = True
                remainder = stripped[5:].strip()
                if remainder:
                    fence = [remainder]
                    if remainder.count("```") == 1:
                        return "\n".join(fence)
                    depth_fence = "```"
            continue
        if depth_fence:
            if stripped == depth_fence:
                return "\n".join(fence)
            fence.append(line)
            continue
        if stripped.startswith("```"):
            if not fence:
                depth_fence = "```"
                continue
            return "\n".join(fence)
        if stripped.startswith("kind:") and fence:
            return "\n".join(fence)
        fence.append(line)
    return "\n".join(fence).rstrip("`").rstrip()


def parse_testgen_response(
    text: str, *, language: Language = Language.PYTHON, target: str = ""
) -> TestGenReport:
    """Parse model output into *proposed* tests. Nothing here executes anything."""
    report = TestGenReport(target=target or "the target", language=language)

    if not text or not text.strip():
        report.errors.append("The model returned nothing.")
        return report

    blocks = re.split(r"```", text)
    # With triple-backtick splitting, proposal bodies land on odd indices.
    chunks: list[str] = []
    for index in range(1, len(blocks), 2):
        chunks.append(blocks[index])

    for chunk in chunks:
        if "kind:" not in chunk.lower() and "name:" not in chunk.lower():
            continue
        kind_match = _KIND_RE.search(chunk)
        raw_kind = (kind_match.group(1).lower() if kind_match else CaseKind.NORMAL.value)
        try:
            kind = CaseKind(raw_kind)
        except ValueError:
            report.errors.append(
                f"Unrecognised test kind '{raw_kind}'; treated as a normal case."
            )
            kind = CaseKind.NORMAL

        name = ""
        why = ""
        for line in chunk.splitlines():
            lowered = line.strip().lower()
            if lowered.startswith("name:") and not name:
                name = line.split(":", 1)[1].strip().strip("`")
            elif lowered.startswith("why:") and not why:
                why = line.split(":", 1)[1].strip()

        code = _extract_code_block(chunk)
        if not code.strip():
            report.errors.append(f"A proposed test '{name or raw_kind}' had no code.")
            continue

        report.proposed.append(
            ProposedTest(
                kind=kind,
                name=name or f"{kind.value}_case",
                source=code.strip("\n"),
                language=language,
                rationale=why,
            )
        )

    if not report.proposed:
        report.errors.append("No test blocks were found in the response.")
    return report


def save_proposed_tests(
    report: TestGenReport, workspace, *, only_kind: CaseKind | None = None
) -> list[Path]:
    """Write proposed tests into a learner workspace. Never into the app source.

    Returns the paths written. Writing is optional; a test that has not been
    run is still worth keeping to look at.
    """
    written: list[Path] = []
    for test in report.proposed:
        if only_kind is not None and test.kind is not only_kind:
            continue
        if report.language is Language.PYTHON:
            filename = f"test_generated_{test.name}.py"
            path = workspace.write_test(filename, test.source + "\n")
        else:
            filename = f"test_{test.name}.cpp"
            path = workspace.write_test(filename, test.source + "\n")
        test.saved_to = str(path)
        written.append(path)
    return written