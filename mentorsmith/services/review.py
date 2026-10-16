"""AI code review, with every finding's origin stated.

Phase 5 draws a distinction this module is built around:

    confirmed  - the compiler, a test or a real tool said this. It is a fact.
    heuristic  - a pattern a reviewer tool flagged. Probably real, needs reading.
    speculative- the model *believes* there may be a problem. Unproven.

Mixing those three into one undifferentiated list of "AI findings" is how a
reviewer starts trusting a model that has never compiled anything. So a
:class:`Finding` cannot be created without a :class:`Origin`, the UI groups by
origin, and a finding that is not confirmed cannot be presented as a bug.

Deterministic checks run first and their results are **merged into the same
finding list** rather than being displayed separately, which is what Phase 5
asks for ("combine AI with compiler diagnostics, linters, static analysis, and
tests") while keeping the provenance visible.

What this module will not do:

* Apply a fix. The proposal is returned with a diff; a human applies it.
* Claim a speculative finding is a bug. ``Finding.is_defect`` is false for
  everything that is not confirmed.
* Run anything on a machine other than this one.
"""

from __future__ import annotations

import ast
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path


class Origin(str, Enum):
    """Where a finding came from. Never guessed, always set."""

    #: A compiler, test run or linter actually reported it.
    CONFIRMED = "confirmed"

    #: A static pattern match. Real signal, but needs a human to read it.
    HEURISTIC = "heuristic"

    #: The model suggested it. Unproven, and may simply be wrong.
    SPECULATIVE = "speculative"


class Importance(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        return {"high": 0, "medium": 1, "low": 2}[self.value]


class Category(str, Enum):
    CORRECTNESS = "correctness"
    ERROR_HANDLING = "error handling"
    RESOURCE_MANAGEMENT = "resource management"
    SECURITY = "security"
    MAINTAINABILITY = "maintainability"
    MISSING_TESTS = "missing tests"
    UNSAFE_OPERATION = "unsafe operation"


@dataclass
class Finding:
    """One observation about a file.

    [verified] is not a decoration: a reader uses it to decide whether to spend
    time. Everything unverified must say how to check it, in [verify].
    """

    file: str
    line: int | None
    title: str
    explanation: str
    importance: Importance
    category: Category
    origin: Origin
    #: What to change. Never applied automatically.
    suggested_fix: str = ""
    #: How to check whether this is real. Required unless confirmed.
    verification: str = ""
    #: A unified diff of the proposed change, when one could be produced.
    proposed_diff: str = ""

    @property
    def is_defect(self) -> bool:
        """Only a confirmed finding counts as a defect.

        A speculative suggestion is a hypothesis. Treating it as a defect is how
        a review tool starts lying to its user.
        """
        return self.origin is Origin.CONFIRMED

    @property
    def location(self) -> str:
        return f"{self.file}:{self.line}" if self.line else self.file

    def describe(self) -> str:
        marker = {
            Origin.CONFIRMED: "CONFIRMED",
            Origin.HEURISTIC: "HEURISTIC",
            Origin.SPECULATIVE: "SUGGESTION",
        }[self.origin]
        head = f"[{marker}] {self.importance.value.upper()} — {self.location}"
        body = [head, f"  {self.title}", f"  {self.explanation}"]
        if self.suggested_fix:
            body.append(f"  Fix: {self.suggested_fix}")
        if self.proposed_diff:
            body.append("  Proposed diff (not applied):")
            body += [f"    {line}" for line in self.proposed_diff.splitlines()]
        if self.origin is not Origin.CONFIRMED:
            body.append(f"  Verify by: {self.verification or 'reading the code'}")
        return "\n".join(body)

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line,
            "title": self.title,
            "explanation": self.explanation,
            "importance": self.importance.value,
            "category": self.category.value,
            "origin": self.origin.value,
            "suggested_fix": self.suggested_fix,
            "verification": self.verification,
            "proposed_diff": self.proposed_diff,
            "is_defect": self.is_defect,
        }


@dataclass
class ReviewReport:
    """Everything one review pass found."""

    files_reviewed: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    reviewed_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )
    #: Set when the pass used a real compiler, e.g. "g++ -Wall -Wextra".
    tools_run: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    # -- summaries ------------------------------------------------------
    @property
    def confirmed(self) -> list[Finding]:
        return [f for f in self.findings if f.origin is Origin.CONFIRMED]

    @property
    def heuristic(self) -> list[Finding]:
        return [f for f in self.findings if f.origin is Origin.HEURISTIC]

    @property
    def speculative(self) -> list[Finding]:
        return [f for f in self.findings if f.origin is Origin.SPECULATIVE]

    @property
    def defects(self) -> list[Finding]:
        """Only confirmed findings. A suggestion is never counted as a bug."""
        return self.confirmed

    def sorted_findings(self) -> list[Finding]:
        order = {Origin.CONFIRMED: 0, Origin.HEURISTIC: 1, Origin.SPECULATIVE: 2}
        return sorted(
            self.findings,
            key=lambda f: (order[f.origin], f.importance.rank, f.file, f.line or 0),
        )

    def counts(self) -> dict[str, int]:
        return {
            "confirmed": len(self.confirmed),
            "heuristic": len(self.heuristic),
            "speculative": len(self.speculative),
        }

    def summary(self) -> str:
        parts = [f"Reviewed {len(self.files_reviewed)} file(s)."]
        counts = self.counts()
        if not self.findings:
            parts.append("No findings.")
        else:
            parts.append(
                f"{counts['confirmed']} confirmed, {counts['heuristic']} heuristic, "
                f"{counts['speculative']} suggestions."
            )
        if self.tools_run:
            parts.append("Tools: " + ", ".join(self.tools_run) + ".")
        return " ".join(parts)

    def describe(self) -> str:
        blocks = [self.summary(), ""]
        if self.errors:
            blocks.append("Review errors:")
            blocks += [f"  - {e}" for e in self.errors]
            blocks.append("")
        grouped: dict[Origin, list[Finding]] = {
            Origin.CONFIRMED: [],
            Origin.HEURISTIC: [],
            Origin.SPECULATIVE: [],
        }
        for finding in self.sorted_findings():
            grouped[finding.origin].append(finding)
        for origin in (Origin.CONFIRMED, Origin.HEURISTIC, Origin.SPECULATIVE):
            items = grouped[origin]
            if not items:
                continue
            blocks.append(
                f"=== {origin.value.upper()} "
                f"({'a tool reported these' if origin is Origin.CONFIRMED else 'real but unproven' if origin is Origin.HEURISTIC else 'unproven; verify before acting'}) ==="
            )
            blocks += [f.describe() for f in items]
            blocks.append("")
        return "\n".join(blocks)


# ======================================================================
# Deterministic checks. These produce confirmed/heuristic findings with
# no model involved, so the report is useful even with no API key.
# ======================================================================

#: Patterns that are almost always a real leak or lifetime bug in C++.
_CPP_RESOURCE_PATTERNS: tuple[tuple[re.Pattern[str], str, Category], ...] = (
    (re.compile(r"\bnew\s+\w"), "raw new without an obvious delete", Category.RESOURCE_MANAGEMENT),
    (re.compile(r"\bmalloc\s*\("), "malloc without an obvious free", Category.RESOURCE_MANAGEMENT),
    (re.compile(r"\bfopen\s*\("), "fopen without an obvious fclose", Category.RESOURCE_MANAGEMENT),
    (re.compile(r"\bsystem\s*\("), "system() runs a shell", Category.UNSAFE_OPERATION),
    (re.compile(r"\bpopen\s*\("), "popen() runs a shell", Category.UNSAFE_OPERATION),
    (re.compile(r"\bstrcpy\s*\("), "strcpy can overflow; snprintf is safer", Category.SECURITY),
    (re.compile(r"\bstrcat\s*\("), "strcat can overflow", Category.SECURITY),
    (re.compile(r"\bgets\s*\("), "gets cannot be used safely", Category.SECURITY),
    (re.compile(r"\batoi\s*\("), "atoi cannot report failure; use strtol", Category.ERROR_HANDLING),
)

_PY_BARE_EXCEPT = re.compile(r"except\s*:", re.MULTILINE)
_PY_PASS_IN_EXCEPT = re.compile(r"except[^:]*:\s*\n\s*pass\b")
_PY_EVAL = re.compile(r"\beval\s*\(")
_PY_SHELL_TRUE = re.compile(r"subprocess\.[A-Za-z_]+\([^)]*shell\s*=\s*True")
_PY_MUTABLE_DEFAULT = re.compile(
    r"def\s+\w+\([^)]*=\s*(\[\]|\{\}|set\(\))", re.MULTILINE
)
_PY_BROAD_EXCEPT = re.compile(r"except\s+(Exception|BaseException)\s*:")
_PY_TODO = re.compile(r"#\s*(TODO|FIXME|XXX|HACK)\b")


def review_python_file(path: Path, relative_to: Path | None = None) -> list[Finding]:
    """Pattern-based Python review. Heuristic findings, never confirmed."""
    name = str(path.relative_to(relative_to)) if relative_to else str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    lines = text.splitlines()
    findings: list[Finding] = []

    def add(line_no: int, title: str, why: str, fix: str,
            category: Category, importance: Importance) -> None:
        findings.append(
            Finding(
                file=name,
                line=line_no,
                title=title,
                explanation=why,
                importance=importance,
                category=category,
                origin=Origin.HEURISTIC,
                suggested_fix=fix,
                verification="Read the code and confirm the pattern applies.",
            )
        )

    for index, line in enumerate(lines, start=1):
        if _PY_BARE_EXCEPT.search(line) and not _PY_BROAD_EXCEPT.search(line):
            add(
                index,
                "bare except",
                "A bare `except:` also catches KeyboardInterrupt and SystemExit, "
                "so the program becomes hard to stop and real errors are hidden.",
                "except (SpecificError, OtherError):",
                Category.ERROR_HANDLING,
                Importance.HIGH,
            )
        if _PY_EVAL.search(line):
            add(
                index,
                "eval()",
                "eval executes arbitrary code from a string. If any part of the "
                "string came from a learner or a model, this is code execution.",
                "Parse the value with ast.literal_eval, or use json.loads.",
                Category.SECURITY,
                Importance.HIGH,
            )
        if _PY_SHELL_TRUE.search(line):
            add(
                index,
                "shell=True",
                "The command string is interpreted by a shell, so any part of it "
                "that came from data can become another command.",
                "Pass an argument list and leave shell=False.",
                Category.SECURITY,
                Importance.HIGH,
            )
        if _PY_TODO.search(line):
            add(
                index,
                "unfinished work",
                f"Unfinished marker in the code: {line.strip()}",
                "Resolve it or track it in an issue.",
                Category.MAINTAINABILITY,
                Importance.LOW,
            )

    if _PY_PASS_IN_EXCEPT.search(text):
        add(
            0,
            "exception swallowed",
            "An except block does nothing, so a failure disappears with no "
            "record. This is the most common reason a script becomes "
            "impossible to debug.",
            "Log the error, re-raise, or return an explicit failure value.",
            Category.ERROR_HANDLING,
            Importance.HIGH,
        )

    for match in _PY_MUTABLE_DEFAULT.finditer(text):
        line_no = text[: match.start()].count("\n") + 1
        add(
            line_no,
            "mutable default argument",
            "A list, dict or set default is created once when the function is "
            "defined and then shared by every call, so results accumulate "
            "across calls.",
            "Use `None` as the default and build the value inside the function.",
            Category.CORRECTNESS,
            Importance.HIGH,
        )

    # A syntax error is not a heuristic: nothing can be true about code that
    # does not parse, so it is reported as confirmed.
    try:
        ast.parse(text)
    except SyntaxError as error:
        findings.append(
            Finding(
                file=name,
                line=error.lineno,
                title=f"syntax error: {error.msg}",
                explanation=(
                    "Python's own parser rejected this file, so it cannot run at "
                    "all. This is a confirmed defect, not a suggestion."
                ),
                importance=Importance.HIGH,
                category=Category.CORRECTNESS,
                origin=Origin.CONFIRMED,
                suggested_fix=f"See line {error.lineno}: {error.text or ''}".strip(),
                verification="Reproduced by parsing the file.",
            )
        )
    return findings


def review_cpp_file(path: Path, relative_to: Path | None = None) -> list[Finding]:
    """Pattern-based C/C++ review, plus a real compile when possible."""
    name = str(path.relative_to(relative_to)) if relative_to else str(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    findings: list[Finding] = []
    for index, line in enumerate(text.splitlines(), start=1):
        for pattern, title, category in _CPP_RESOURCE_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        file=name,
                        line=index,
                        title=title,
                        explanation=(
                            f"`{pattern.pattern.strip(chr(92) + 'b')}` matches here. "
                            "Whether it is a real leak or overflow depends on the "
                            "surrounding code, so this is a lead, not a confirmed bug."
                        ),
                        importance=(
                            Importance.HIGH
                            if category in (Category.SECURITY, Category.UNSAFE_OPERATION)
                            else Importance.MEDIUM
                        ),
                        category=category,
                        origin=Origin.HEURISTIC,
                        suggested_fix=(
                            "Use RAII: std::vector, std::string, std::fstream."
                            if category is Category.RESOURCE_MANAGEMENT
                            else "Replace with a bounded alternative."
                        ),
                        verification=(
                            "Compile with -Wall -Wextra and run under valgrind or "
                            "ASan to confirm before changing anything."
                        ),
                    )
                )
    return findings


def compile_and_review(
    path: Path, *, compiler: str = "g++", standard: str = "c++17",
    relative_to: Path | None = None, timeout: int = 30,
) -> tuple[list[Finding], str | None]:
    """Compile for real and turn diagnostics into confirmed findings.

    Returns the findings and the exact command that ran, so the report can
    state its own evidence.
    """
    name = str(path.relative_to(relative_to)) if relative_to else str(path)
    command = [compiler, f"-std={standard}", "-Wall", "-Wextra", "-fsyntax-only", str(path)]

    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        return ([], f"{compiler} is not installed, so nothing was compiled")
    except subprocess.TimeoutExpired:
        return ([], f"compilation exceeded {timeout}s and was stopped")

    findings: list[Finding] = []
    for raw in completed.stderr.splitlines():
        line = raw.strip()
        if not line:
            continue
        # gcc: path:line:col: error: message
        match = re.match(r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s*(?P<kind>\w+):\s*(?P<msg>.+)$", line)
        if not match:
            continue
        message = match.group("msg")
        kind = match.group("kind")
        findings.append(
            Finding(
                file=name,
                line=int(match.group("line")),
                title=f"{kind}: {message}",
                explanation=(
                    f"The compiler reported this at line {match.group('line')}, "
                    f"column {match.group('col')}. It is a confirmed defect: the "
                    "compiler itself produced the diagnostic."
                ),
                importance=Importance.HIGH if kind in ("error", "fatal error") else Importance.MEDIUM,
                category=Category.CORRECTNESS,
                origin=Origin.CONFIRMED,
                suggested_fix=message,
                verification=f"Reproduced with: {' '.join(command)}",
            )
        )
    return findings, " ".join(command)


def static_review(
    files: list[Path], *, relative_to: Path | None = None, compile_cpp: bool = True
) -> ReviewReport:
    """Run every deterministic check. No model, no network, no API key."""
    report = ReviewReport()

    for path in files:
        if path.suffix == ".py":
            report.findings.extend(review_python_file(path, relative_to))
        elif path.suffix in (".cpp", ".cc", ".cxx", ".h", ".hpp", ".c", ".h"):
            report.findings.extend(review_cpp_file(path, relative_to))
            if compile_cpp:
                findings, command = compile_and_review(path, relative_to=relative_to)
                report.findings.extend(findings)
                if command:
                    report.tools_run.append(f"{path.name}: {command}")
                elif command:
                    report.errors.append(f"{path.name}: {command}")
        else:
            continue
        report.files_reviewed.append(
            str(path.relative_to(relative_to)) if relative_to else str(path)
        )

    # A file with no test next to it is a legitimate observation, but only a
    # suggestion: absence of a test is not a defect.
    if relative_to is not None:
        reviewed = {Path(f.file) for f in report.findings}
        for path in files:
            name = str(path.relative_to(relative_to))
            has_test = any(
                (path.parent / f"test_{path.stem}.py").exists()
                or (path.parent / f"{path.stem}_test.py").exists()
                or (path.parent.parent / "tests" / f"test_{path.stem}.py").exists()
                for _ in (0,)
            )
            if not has_test:
                report.findings.append(
                    Finding(
                        file=name,
                        line=None,
                        title="no test file found next to this module",
                        explanation=(
                            "No `test_<name>.py` was found beside it or in tests/. "
                            "This may be fine for a small helper, but it means a "
                            "regression here would not be caught."
                        ),
                        importance=Importance.LOW,
                        category=Category.MISSING_TESTS,
                        origin=Origin.SPECULATIVE,
                        suggested_fix="Add a test module and cover the boundaries.",
                        verification="Search the tests directory for this module.",
                    )
                )
    return report


# ======================================================================
# The AI part.
# ======================================================================

_REVIEW_SYSTEM = (
    "You are a careful C++/Python code reviewer assisting a learning tool. "
    "Report only genuine, specific concerns. Do not restate what the code does. "
    "Do not invent problems to seem thorough; 'nothing to report' is a valid "
    "answer. For each concern give: the file, the line if you can, what is "
    "wrong, why it matters, and a concrete fix."
)


def build_review_prompt(files: list[Path], relative_to: Path | None = None) -> str:
    """Assemble the review request from real file contents."""
    parts = [
        "Review the following code. Report correctness problems first, then "
        "error handling, resource management, unsafe operations, "
        "maintainability, and missing tests.",
        "",
    ]
    for path in files:
        name = str(path.relative_to(relative_to)) if relative_to else str(path)
        try:
            body = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            parts.append(f"--- {name} --- (could not read: {error})")
            continue
        if len(body) > 40_000:
            body = body[:40_000] + "\n... [truncated] ..."
        parts.append(f"--- {name} ---")
        parts.append(body)
        parts.append("")
    return "\n".join(parts)


def parse_review_response(text: str) -> list[Finding]:
    """Turn model text into findings.

    **Every finding produced here is `SPECULATIVE`.** There is no way for the
    parser to mark something confirmed, because the model has not compiled
    anything. A parse failure yields an explanatory note rather than an
    exception, so a chatty reply degrades gracefully.
    """
    findings: list[Finding] = []
    if not text or not text.strip():
        return findings

    # Expected blocks look like:
    #   file: path/to/x.py
    #   line: 42
    #   importance: high
    #   category: correctness
    #   issue: ...
    #   fix: ...
    #   verify: ...
    current: dict[str, str] = {}

    def flush() -> None:
        issue = current.get("issue", "").strip()
        if not issue:
            current.clear()
            return
        raw_importance = current.get("importance", "medium").strip().lower()
        importance = (
            Importance.HIGH if raw_importance in ("high", "critical")
            else Importance.LOW if raw_importance == "low"
            else Importance.MEDIUM
        )
        raw_category = current.get("category", "maintainability").strip().lower()
        category = next(
            (c for c in Category if c.value.replace(" ", "_") == raw_category), None
        ) or Category.MAINTAINABILITY

        line_text = current.get("line", "").strip()
        line_no = None
        if line_text.isdigit():
            line_no = int(line_text)

        findings.append(
            Finding(
                file=current.get("file", "(file not named)").strip(),
                line=line_no,
                title=issue.splitlines()[0][:120],
                explanation="\n".join(issue.splitlines()[1:]).strip() or issue,
                importance=importance,
                category=category,
                # Not negotiable: unverified model output is always speculative.
                origin=Origin.SPECULATIVE,
                suggested_fix=current.get("fix", "").strip(),
                verification=current.get("verify", "").strip()
                or "Confirm this by reading the code, or by compiling and running it.",
            )
        )
        current.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        key, separator, value = line.partition(":")
        key = key.strip().lower()
        if separator and key in (
            "file", "line", "importance", "category", "issue", "fix", "verify"
        ):
            if key == "issue" and "issue" in current:
                # Flush the *previous* finding only when one has actually
                # started. Without this guard the first `issue:` line threw away
                # the file, line and importance collected just above it, and
                # every finding came back as "(file not named)".
                flush()
            current[key] = value.strip()
        elif current:
            # A continuation line. `.get` because `file:` or `fix:` may have
            # arrived before any `issue:`, and a chatty reply should never
            # raise here.
            current["issue"] = current.get("issue", "") + "\n" + line
    flush()
    return findings


def merge_reports(
    static: ReviewReport, ai_findings: list[Finding], *, ai_errors: list[str] | None = None
) -> ReviewReport:
    """Combine deterministic and AI findings into one list, keeping origins."""
    report = ReviewReport(
        files_reviewed=list(static.files_reviewed),
        findings=list(static.findings) + list(ai_findings),
        tools_run=list(static.tools_run),
        errors=list(static.errors) + list(ai_errors or []),
    )
    return report