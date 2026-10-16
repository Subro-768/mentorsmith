"""Executable evidence about what containment MentorSmith actually provides.

Phase 5 says: *"A subprocess timeout is not a complete sandbox. Never claim full
isolation unless actually implemented and verified."*

This module turns that from a promise into a measurement. Every check runs real
code and observes the real outcome. ``run_audit()`` returns a report whose
``verified`` field means *this was observed on this machine just now*, not
*this is documented somewhere*.

Each check states what it proves and, importantly, what it does **not** prove. A
check that passes is evidence for the narrow claim it makes and nothing more.
Checks that cannot run on this host report ``skipped`` with the reason rather
than quietly returning ``passed``, which is the failure mode this whole module
exists to prevent.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from ..execution import adapter


class Status(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Check:
    """One verified claim about containment."""

    name: str
    status: Status
    #: Exactly what passing this check demonstrates.
    proves: str
    #: What it does not demonstrate. Present on every check, deliberately.
    does_not_prove: str
    detail: str = ""
    evidence: str = ""

    def describe(self) -> str:
        head = {
            Status.PASSED: "PASS",
            Status.FAILED: "FAIL",
            Status.SKIPPED: "SKIP",
        }[self.status]
        lines = [f"[{head}] {self.name}", f"  Proves: {self.proves}",
                 f"  Does not prove: {self.does_not_prove}"]
        if self.detail:
            lines.append(f"  Detail: {self.detail}")
        if self.evidence:
            lines.append(f"  Evidence: {self.evidence}")
        return "\n".join(lines)


@dataclass
class AuditReport:
    """The result of one audit run."""

    checks: list[Check] = field(default_factory=list)
    ran_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )
    platform: str = ""

    @property
    def passed(self) -> list[Check]:
        return [c for c in self.checks if c.status is Status.PASSED]

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if c.status is Status.FAILED]

    @property
    def skipped(self) -> list[Check]:
        return [c for c in self.checks if c.status is Status.SKIPPED]

    @property
    def verdict(self) -> str:
        """One honest line. Never says "secure"."""
        if self.failed:
            return (
                f"{len(self.failed)} containment check(s) FAILED on this machine. "
                "Learner code is not held to the limits described."
            )
        if not self.passed:
            return "No containment check could be run here."
        return (
            f"{len(self.passed)} check(s) verified on this machine, "
            f"{len(self.skipped)} skipped. Limits are real but this is NOT a "
            "security boundary."
        )

    def summary(self) -> str:
        lines = [self.verdict, f"Platform: {self.platform or 'unknown'}", ""]
        lines += [check.describe() for check in self.checks]
        return "\n".join(lines)


# ======================================================================
# Individual checks
# ======================================================================

def check_timeouts() -> Check:
    """Does an infinite loop actually get stopped?"""
    not_sandbox = (
        "That a runaway program is stopped. It says nothing about a program that "
        "exits cleanly after doing damage."
    )
    if not shutil.which("python3"):
        return Check(
            "runtime timeout", Status.SKIPPED,
            "That a runaway program is stopped.",
            not_sandbox,
            detail="python3 is not installed",
        )

    with tempfile.TemporaryDirectory() as tmp:
        instance = adapter("python", Path(tmp) / "run", sandbox=False)
        instance.run_timeout = 2
        _build, result = instance.run("while True:\n    pass\n")
        stopped = bool(result and result.timed_out)
        return Check(
            "runtime timeout",
            Status.PASSED if stopped else Status.FAILED,
            "That a program which never finishes is killed and reported as a timeout.",
            not_sandbox,
            detail=result.error if result else "no result",
            evidence=f"timed_out={result.timed_out if result else None}, "
                     f"exit={result.exit_code if result else None}",
        )


def check_memory_limit() -> Check:
    """Is an unbounded allocation actually refused?"""
    not_sandbox = (
        "That memory usage is bounded. It says nothing about disk, network, or "
        "anything the program does within its limit."
    )
    if not shutil.which("python3"):
        return Check(
            "memory limit", Status.SKIPPED,
            "That an unbounded allocation is refused.",
            not_sandbox,
            detail="python3 is not installed",
        )

    with tempfile.TemporaryDirectory() as tmp:
        instance = adapter("python", Path(tmp) / "run", sandbox=False)
        _build, result = instance.run(
            "blocks = []\n"
            "while True:\n"
            "    blocks.append(bytearray(64 * 1024 * 1024))\n"
        )
        died = bool(result and (result.exit_code != 0 or result.timed_out))
        return Check(
            "memory limit",
            Status.PASSED if died else Status.FAILED,
            "That a program allocating without bound is stopped rather than "
            "consuming host memory indefinitely.",
            not_sandbox,
            detail=(result.first_error_line[:160] if result else "no result"),
            evidence=f"exit={result.exit_code if result else None}",
        )


def check_process_tree_kill() -> Check:
    """Does Stop kill children, or only the direct child?"""
    not_sandbox = (
        "That Stop works for programs that spawn children. A program that "
        "double-forks or is already reparented is a different question."
    )
    if not shutil.which("python3"):
        return Check(
            "process tree", Status.SKIPPED,
            "That stopping a program also stops what it started.",
            not_sandbox,
            detail="python3 is not installed",
        )

    with tempfile.TemporaryDirectory() as tmp:
        marker = Path(tmp) / "child.txt"
        instance = adapter("python", Path(tmp) / "run", sandbox=False)
        instance.run_timeout = 30

        source = (
            "import subprocess, sys, time\n"
            f"subprocess.Popen([sys.executable, '-c', "
            f"\"import time; time.sleep(20); open({str(marker)!r}, 'w').write('x')\"])\n"
            "time.sleep(20)\n"
        )
        compile_result, handle = instance.start_run(source)
        if handle is None:
            return Check(
                "process tree", Status.FAILED,
                "That stopping a program also stops what it started.",
                not_sandbox,
                detail="the program did not start",
            )

        import time as _time
        _time.sleep(1.5)
        handle.stop()

        # The child would create the marker if it outlived the stop.
        _time.sleep(3.0)
        survived = marker.exists()
        return Check(
            "process tree",
            Status.FAILED if survived else Status.PASSED,
            "That stopping a program also stops the children it started, so a "
            "background process does not outlive the run button.",
            not_sandbox,
            detail="child wrote its marker after the stop" if survived else
                   "no marker: the child was killed too",
        )


def check_filesystem_sandbox() -> Check:
    """Does the bubblewrap sandbox actually block the home directory?"""
    not_sandbox = (
        "Isolation of *any* kind. The sandbox is off by default, depends on "
        "unprivileged user namespaces being permitted, and is far weaker than a "
        "VM or a configured container."
    )
    if not shutil.which("bwrap"):
        return Check(
            "filesystem sandbox", Status.SKIPPED,
            "That a sandboxed binary cannot read the user's home directory.",
            not_sandbox,
            detail="bubblewrap is not installed, so the sandbox is not available",
        )
    if not shutil.which("gcc"):
        return Check(
            "filesystem sandbox", Status.SKIPPED,
            "That a sandboxed binary cannot read the user's home directory.",
            not_sandbox,
            detail="gcc is not installed",
        )

    home = str(Path.home())
    with tempfile.TemporaryDirectory() as tmp:
        instance = adapter("c", Path(tmp) / "run", sandbox=True)
        active, note = instance.sandbox_status()
        if not active:
            return Check(
                "filesystem sandbox", Status.SKIPPED,
                "That a sandboxed binary cannot read the user's home directory.",
                not_sandbox,
                detail=note,
            )
        source = (
            "#include <stdio.h>\n"
            "#include <dirent.h>\n"
            "int main(void) {\n"
            f'  DIR *d = opendir("{home}");\n'
            '  printf("%s\\n", d ? "HOME-READABLE" : "HOME-BLOCKED");\n'
            "  return 0;\n"
            "}\n"
        )
        _build, result = instance.run(source)
        blocked = bool(result and "HOME-BLOCKED" in result.stdout)
        return Check(
            "filesystem sandbox",
            Status.PASSED if blocked else Status.FAILED,
            "That with the sandbox enabled, a compiled program cannot list the "
            "user's home directory.",
            not_sandbox,
            detail=(result.first_error_line[:160] if result else "no result"),
            evidence=f"stdout={result.stdout.strip()[:60]!r}" if result else "no result",
        )


def check_no_shell_execution() -> Check:
    """Could lesson content become a shell command?"""
    not_sandbox = (
        "That no *other* code path uses a shell. It covers one construction."
    )
    from ..execution import compiled as compiled_module
    from ..execution import interpreted as interpreted_module

    offenders: list[str] = []
    for module in (compiled_module, interpreted_module):
        source = Path(module.__file__).read_text(encoding="utf-8")
        for marker in ("shell=True", "os.system(", "os.popen("):
            if marker in source:
                offenders.append(f"{module.__name__}: {marker}")

    if not offenders:
        # Also confirm the Python subprocess call has no shell keyword.
        import subprocess as _subprocess

        import inspect

        for module in (compiled_module, interpreted_module):
            text = inspect.getsource(module)
            if "shell=" in text:
                offenders.append(f"{module.__name__}: shell= passed")

    return Check(
        "no shell execution",
        Status.PASSED if not offenders else Status.FAILED,
        "That learner code is never passed through a shell, so a filename or "
        "lesson text containing shell metacharacters cannot become a command.",
        not_sandbox,
        detail="; ".join(offenders) if offenders else "no shell invocation found",
    )


def check_output_is_bounded() -> Check:
    """Can a program print forever and exhaust memory?"""
    not_sandbox = (
        "That output is bounded in general. It does not bound time or file writes."
    )
    from ..execution.base import MAX_OUTPUT_CHARS

    with tempfile.TemporaryDirectory() as tmp:
        if not shutil.which("python3"):
            return Check(
                "output bound", Status.SKIPPED,
                "That captured output is truncated rather than kept in full.",
                not_sandbox,
                detail="python3 is not installed",
            )
        instance = adapter("python", Path(tmp) / "run", sandbox=False)
        # Short timeout on purpose. This program produces a colossal amount of
        # output, and there is no value in pushing gigabytes through a pipe when
        # two seconds is enough to prove the cap holds.
        instance.run_timeout = 2
        _build, result = instance.run("while True:\n    print('x' * 1000)\n")
        length = len(result.stdout) if result else 0
        bounded = length <= MAX_OUTPUT_CHARS + 1000
        notified = bool(result and "discarded" in result.stdout)
        return Check(
            "output bound",
            Status.PASSED if bounded else Status.FAILED,
            "That a program printing without limit does not exhaust memory, "
            f"because captured output is capped at {MAX_OUTPUT_CHARS} characters "
            "while being read, not afterwards.",
            not_sandbox,
            detail=f"captured {length} characters"
                   + (", and the learner was told output was dropped"
                      if notified else ""),
            evidence=(
                f"MAX_OUTPUT_CHARS={MAX_OUTPUT_CHARS}, "
                f"discarded-notice-shown={notified}"
            ),
        )


def check_stale_binary_removed() -> Check:
    """Can a failed compile leave an old binary that appears to run?"""
    not_sandbox = (
        "Anything about the correctness of the learner's code. Only that a stale "
        "artifact is not presented as a fresh build."
    )
    if not shutil.which("g++"):
        return Check(
            "stale binary", Status.SKIPPED,
            "That a failed compile leaves no executable behind.",
            not_sandbox,
            detail="g++ is not installed",
        )
    with tempfile.TemporaryDirectory() as tmp:
        instance = adapter("cpp", Path(tmp) / "run", sandbox=False)
        instance.run('int main() { return 0; }\n')
        artifact = instance.artifact_path()
        existed = artifact.exists()

        broken = instance.compile("int main() { int x = ; }\n")
        still_there = artifact.exists()
        return Check(
            "stale binary",
            Status.PASSED if (existed and not still_there) else Status.FAILED,
            "That a failed compile removes the previous executable, so old output "
            "is never presented as the result of new code.",
            not_sandbox,
            detail=(
                "artifact removed after a failed compile"
                if not still_there
                else "the old executable is still present"
            ),
        )


#: Identifiers whose value must never be a hard-coded literal.
_SECRET_NAME = re.compile(
    r"\b(api[_-]?key|secret|token|password|passwd|credential|bearer)\b",
    re.IGNORECASE,
)

#: Values that are obviously not real keys.
_PLACEHOLDERS = {"", "none", "changeme", "your-key-here", "xxx", "...", "todo"}

#: Assignment of a secret-ish name to something that is not an environment read.
_SECRET_ASSIGNMENT = re.compile(
    r"""^\s*(?:self\.)?(?P<name>[A-Za-z_]*(?:api[_-]?key|secret|token|password|credential)[A-Za-z_]*)
        \s*(?::\s*[^=]+)?=\s*
        (?P<value>.+)$""",
    re.IGNORECASE | re.VERBOSE,
)


def check_no_credentials_in_code() -> Check:
    """Is any credential hard-coded in shipped source?

    Scans the **shipped package only** (``mentorsmith/``). Tests are excluded on
    purpose: a test that does ``monkeypatch.setenv("MENTORSMITH_API_KEY",
    "sk-test")`` is doing the right thing, and flagging it would make this check
    cry wolf on every run and get ignored.

    The question asked is *"is a secret assigned a literal?"*, not *"does the
    env-var name appear?"* — the name legitimately appears in defaults, help
    text and assertions.
    """
    not_sandbox = (
        "That no secret is hard-coded. It cannot see a key held in an "
        "environment variable, a shell history, a config file outside this "
        "package, or a value read at runtime from elsewhere."
    )
    package_root = Path(__file__).resolve().parent.parent
    this_file = Path(__file__).resolve()

    offenders: list[str] = []
    for path in sorted(package_root.rglob("*.py")):
        if path.resolve() == this_file:
            continue          # this checker mentions the patterns by necessity
        if "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            match = _SECRET_ASSIGNMENT.match(line)
            if not match:
                continue

            value = match.group("value").strip()
            # Reading from the environment is the only legitimate source.
            if any(marker in value for marker in ("environ", "getenv", "self.", "config.")):
                continue
            # Concatenation or a call means the value is computed, not literal.
            if value[0] not in "\"'":
                continue
            literal = value.strip("\"'").strip()
            if literal.lower() in _PLACEHOLDERS:
                continue
            # A variable holding only the env-var *name* is not a key.
            if literal.isupper() and "KEY" in literal and "_" in literal:
                continue
            offenders.append(
                f"{path.relative_to(package_root)}:{lineno}: "
                f"{match.group('name')} = {literal[:24]!r}"
            )

    return Check(
        "no credentials in source",
        Status.PASSED if not offenders else Status.FAILED,
        "That no file in the shipped mentorsmith package hard-codes a value for a "
        "secret-ish name instead of reading it from the environment.",
        not_sandbox,
        detail="; ".join(offenders[:5]) if offenders
        else "every secret-ish assignment is an environment read",
    )


def check_language_isolation() -> Check:
    """Can a C++ lesson completion mark a Python lesson complete?"""
    not_sandbox = (
        "That the database is correct in general. Only that progress is scoped "
        "by language."
    )
    import tempfile as _tempfile

    from ..core.db import Database

    with _tempfile.TemporaryDirectory() as tmp:
        database = Database(str(Path(tmp) / "audit.db"))
        database.connect()
        database.mark_lesson_complete("01-program-structure", "cpp")
        leaked = database.is_lesson_complete("01-program-structure", "python")
        return Check(
            "language isolation",
            Status.FAILED if leaked else Status.PASSED,
            "That completing a C++ lesson does not mark the same lesson id in "
            "another language complete.",
            not_sandbox,
            detail="progress leaked across languages" if leaked
                   else "progress stayed in its own track",
        )


ALL_CHECKS = (
    check_timeouts,
    check_memory_limit,
    check_process_tree_kill,
    check_output_is_bounded,
    check_stale_binary_removed,
    check_no_shell_execution,
    check_filesystem_sandbox,
    check_no_credentials_in_code,
    check_language_isolation,
)


def run_audit(checks=None) -> AuditReport:
    """Run every check and report honestly, including what was skipped."""
    import platform

    report = AuditReport(platform=f"{platform.system()} {platform.release()}")
    for check in checks or ALL_CHECKS:
        try:
            report.checks.append(check())
        except Exception as error:  # a broken check must not abort the audit
            report.checks.append(
                Check(
                    name=getattr(check, "__name__", "unnamed check"),
                    status=Status.FAILED,
                    proves="nothing",
                    does_not_prove="anything; the check itself errored",
                    detail=f"{type(error).__name__}: {error}",
                )
            )
    return report