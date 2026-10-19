"""Shared execution plumbing for every language MentorSmith can run.

Phase 4 adds Python, C and JavaScript alongside C++. The parts that are the
same for all of them live here exactly once:

* locating a tool and telling the user, clearly, how to install it
* running a child process with CPU/memory/file-size limits and a timeout
* capturing stdout and stderr separately and bounding how much is kept
* killing a process tree on request

What stays language-specific is the command line and the diagnostics. That
lives in each adapter. The split is deliberate: *"Do not abstract away
meaningful language differences"* — so there is no pretend-universal "compiler"
interface, only a shared runner plus per-language behaviour.

Security posture is unchanged from Phase 1 and is documented in
:mod:`mentorsmith.compiler.toolchain`, which this package was factored out of.
A subprocess timeout alone is not a sandbox, and nothing here claims otherwise.
"""

from __future__ import annotations

import os
import selectors
import shutil
import signal
import subprocess
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


class ToolMissingError(RuntimeError):
    """A required compiler or interpreter was not found.

    The message always names the tool and the install command. MentorSmith
    never installs software on the user's behalf.
    """

    def __init__(self, tool: str, install_hint: str, tried: tuple[str, ...] = ()) -> None:
        self.tool = tool
        self.install_hint = install_hint
        self.tried = tried
        detail = f"\n\nLooked for: {', '.join(tried)}" if tried else ""
        super().__init__(
            f"{tool} was not found on this system.{detail}\n\n"
            f"Install it with:\n    {install_hint}\n\n"
            "MentorSmith does not install software for you. Restart the app "
            "after installing."
        )


@dataclass
class ProcessResult:
    """Outcome of one run."""

    ok: bool = False
    command: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_s: float = 0.0
    timed_out: bool = False
    killed: bool = False
    error: str = ""

    @property
    def combined_output(self) -> str:
        parts = [part for part in (self.stdout, self.stderr) if part.strip()]
        return "\n".join(parts) if parts else "(no output)"

    @property
    def first_error_line(self) -> str:
        """Most useful line for a diagnosis, preferring compiler errors."""
        for line in (self.stderr or "").splitlines():
            if "error" in line.lower():
                return line.strip()[:240]
        for line in ((self.stderr or "") + "\n" + (self.stdout or "")).splitlines():
            if line.strip():
                return line.strip()[:240]
        return ""


#: Never buffer more than this from a runaway program. Applied *while reading*,
#: so a program printing without limit cannot exhaust memory.
MAX_OUTPUT_CHARS = 200_000

#: Granularity of a single read from the child's pipe.
READ_CHUNK_CHARS = 64 * 1024


def as_text(value: "str | bytes | None") -> str:
    """Normalise a stream value to text (processes use ``text=True``)."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def truncate(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... [truncated at {MAX_OUTPUT_CHARS} characters]"


def limit_resources(cpu_seconds: int, memory_bytes: int, max_file_bytes: int) -> None:
    """Apply POSIX resource limits in the child, via ``preexec_fn``.

    ``RLIMIT_NPROC`` is deliberately not set. It limits processes per *real
    UID*, not per process tree, so a value low enough to matter also breaks
    ``fork`` for the learner's own unrelated programs. In Phase 1 testing a
    limit of 64 made ``bwrap`` fail with ``EAGAIN`` on an account that already
    had more than 64 live processes.
    """
    try:
        import resource
    except ImportError:  # pragma: no cover - non-POSIX
        return

    def set_if_supported(what: int, soft: int, hard: int) -> None:
        try:
            current_soft, current_hard = resource.getrlimit(what)
            new_hard = (
                hard if current_hard == resource.RLIM_INFINITY else min(hard, current_hard)
            )
            resource.setrlimit(what, (min(soft, new_hard), new_hard))
        except (ValueError, OSError):
            pass

    set_if_supported(resource.RLIMIT_CPU, cpu_seconds, cpu_seconds + 1)
    if memory_bytes > 0:
        set_if_supported(resource.RLIMIT_AS, memory_bytes, memory_bytes)
    set_if_supported(resource.RLIMIT_FSIZE, max_file_bytes, max_file_bytes)
    set_if_supported(resource.RLIMIT_CORE, 0, 0)


@dataclass
class RunSpec:
    """Everything needed to start one child process."""

    argv: list[str]
    cwd: Path | None = None
    stdin_data: str = ""
    timeout: int = 5
    memory_limit_bytes: int = 1024 * 1024 * 1024
    #: Extra argv prefix applied at spawn time, used for sandbox wrappers.
    prefix: list[str] = field(default_factory=list)
    limit_memory: bool = True


class ProcessHandle:
    """A running process the UI can poll and stop.

    Output is read with a **hard cap applied while reading**, not afterwards.
    This matters more than it looks: a program printing in a tight loop can emit
    gigabytes within the time it is allowed to run, and reading all of it into
    memory first is how the tutor exhausts the machine's RAM and gets itself
    OOM-killed. That is not hypothetical — it happened during development.
    Discarded output is counted so the result can say how much was dropped
    rather than silently losing it.
    """

    def __init__(self, process: subprocess.Popen, argv: list[str]) -> None:
        self.process = process
        self.command = argv
        self.started_at = time.monotonic()
        self._drained = False
        self._stdout = ""
        self._stderr = ""
        self._dropped = 0

    # -- bounded reading ------------------------------------------------
    def _drain(self, deadline: float | None) -> bool:
        """Read what is available, keeping at most the cap. ``True`` if timed out.

        Non-blocking throughout, so this cannot hang on a program that has
        exited while a grandchild still holds the pipe open.
        """
        if self._drained:
            return False

        streams: dict[str, dict] = {}
        selector = selectors.DefaultSelector()
        try:
            for name, stream in (("stdout", self.process.stdout),
                                 ("stderr", self.process.stderr)):
                if stream is None or stream.closed:
                    continue
                os.set_blocking(stream.fileno(), False)
                streams[name] = {"chunks": [], "kept": 0}
                selector.register(stream, selectors.EVENT_READ, name)

            open_streams = set(streams)
            timed_out = False

            while open_streams:
                if deadline is None:
                    wait_for = 0.05
                else:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        timed_out = True
                        break
                    wait_for = min(remaining, 0.25)

                for key, _ in selector.select(timeout=wait_for):
                    name = key.data
                    try:
                        chunk = key.fileobj.read(READ_CHUNK_CHARS)
                    except (BlockingIOError, InterruptedError):
                        continue
                    except (ValueError, OSError):
                        open_streams.discard(name)
                        continue
                    if not chunk:
                        selector.unregister(key.fileobj)
                        open_streams.discard(name)
                        continue

                    bucket = streams[name]
                    room = MAX_OUTPUT_CHARS - bucket["kept"]
                    if room > 0:
                        kept = chunk[:room]
                        bucket["chunks"].append(kept)
                        bucket["kept"] += len(kept)
                        if len(kept) < len(chunk):
                            self._dropped += len(chunk) - len(kept)
                    else:
                        # Past the cap: count it, keep none of it.
                        self._dropped += len(chunk)

            for name, bucket in streams.items():
                joined = "".join(bucket["chunks"])
                if name == "stdout":
                    self._stdout = joined
                else:
                    self._stderr = joined
            self._drained = True
            return timed_out
        finally:
            selector.close()

    def _finish_drain(self, grace: float = 1.0) -> None:
        """Pick up anything still buffered, then close the pipes."""
        self._drain(deadline=time.monotonic() + grace)
        for stream in (self.process.stdout, self.process.stderr):
            if stream is not None and not stream.closed:
                try:
                    stream.close()
                except OSError:
                    pass

    # -- public ---------------------------------------------------------
    def poll(self) -> ProcessResult | None:
        """Result once the process has exited, else ``None``."""
        code = self.process.poll()
        if code is None:
            return None
        self._finish_drain()
        return self._result(timed_out=False, code=code, timeout=None)

    def wait(self, timeout: float) -> ProcessResult:
        """Block until the process finishes or ``timeout`` elapses.

        The cap is applied as output is read, so a chatty program cannot exhaust
        memory before the timeout ever has a chance to fire.
        """
        timed_out = self._drain(time.monotonic() + timeout)

        if timed_out:
            self.stop()
            # Give the killed process a moment to release its pipes.
            self._drain(time.monotonic() + 1.0)
        self._finish_drain()

        code = self.process.returncode
        if code is None:
            try:
                code = self.process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                code = -1

        return self._result(timed_out=timed_out, code=code, timeout=timeout)

    def _result(self, *, timed_out: bool, code: int | None, timeout: float | None) -> ProcessResult:
        stdout = self._stdout
        stderr = self._stderr

        if self._dropped:
            # Prepended, not appended: `truncate()` clips at MAX_OUTPUT_CHARS, so
            # a trailing notice would be cut away exactly when it matters most.
            note = (
                f"[{self._dropped} characters of output were discarded after the "
                f"first {MAX_OUTPUT_CHARS}; the program produced more output than "
                "is stored]\n\n"
            )
            stdout = note + stdout

        duration = time.monotonic() - self.started_at

        if timed_out and timeout is not None:
            return ProcessResult(
                ok=False,
                command=list(self.command),
                stdout=truncate(as_text(stdout)),
                stderr=(
                    truncate(as_text(stderr))
                    + f"\n[stopped: exceeded the {timeout:g}s runtime limit]"
                ),
                exit_code=code,
                duration_s=duration,
                timed_out=True,
                error=f"Program exceeded the {timeout:g}s runtime limit and was stopped.",
            )
        return ProcessResult(
            ok=code == 0,
            command=list(self.command),
            stdout=truncate(as_text(stdout)),
            stderr=truncate(as_text(stderr)),
            exit_code=code,
            duration_s=duration,
            error="" if code == 0 else f"Program exited with code {code}.",
        )

    def stop(self) -> None:
        """Terminate the whole process group, escalating if needed."""
        if self.process.poll() is not None:
            return
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(os.getpgid(self.process.pid), sig)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    self.process.send_signal(sig)
                except (ProcessLookupError, OSError):
                    return
            try:
                self.process.wait(timeout=2.0)
                return
            except subprocess.TimeoutExpired:
                continue


def start(spec: RunSpec) -> ProcessHandle:
    """Spawn the process described by ``spec``.

    ``start_new_session=True`` puts the child in its own process group so
    :meth:`ProcessHandle.stop` can kill anything it spawned, not just the
    direct child. Learner code is never passed through a shell.
    """
    argv = [*spec.prefix, *spec.argv]
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(spec.cwd) if spec.cwd else None,
            text=True,
            start_new_session=True,
            preexec_fn=lambda: limit_resources(
                int(spec.timeout) + 1,
                spec.memory_limit_bytes if spec.limit_memory else -1,
                10 * 1024 * 1024,
            ),
        )
    except OSError as exc:
        return ProcessHandle(_FailedProcess(exc), argv)
    return ProcessHandle(process, argv)


class _FailedProcess:
    """Stands in for a process that could not be spawned."""

    def __init__(self, error: OSError) -> None:
        self._error = error
        self.returncode = None
        self.stdin = None

    def poll(self):
        return 126

    def communicate(self, timeout=None):
        return "", f"Could not start the program: {self._error}"

    def wait(self, timeout=None):
        return 126


def find_tool(candidates: tuple[str, ...]) -> str | None:
    """First candidate found on ``PATH``."""
    for candidate in candidates:
        found = shutil.which(candidate)
        if found:
            return found
    return None


def tool_version(path: str) -> str:
    """Best-effort one-line version string."""
    try:
        proc = subprocess.run([path, "--version"], capture_output=True, timeout=10, text=True)
    except (OSError, subprocess.SubprocessError):
        return ""
    lines = (proc.stdout or proc.stderr or "").strip().splitlines()
    return lines[0].strip() if lines else ""


@dataclass
class ToolInfo:
    """What was found on this machine for one language."""

    language: str
    available: bool = False
    tool_name: str | None = None
    tool_path: str | None = None
    version: str = ""
    install_hint: str = ""

    def describe(self) -> str:
        if not self.available:
            return f"{self.language}: not installed — {self.install_hint}"
        return f"{self.language}: {self.tool_name} ({self.version or 'version unknown'})"


class LanguageAdapter(ABC):
    """Per-language execution behaviour.

    Compiled languages implement :meth:`compile_argv`; interpreted ones return
    ``None`` from it and set :attr:`compiles` to False.
    """

    #: Stable identifier used in the database and the sync contract.
    language_id: str = ""
    display_name: str = ""
    #: ``compiled`` or ``interpreted``.
    kind: str = "compiled"
    #: Extensions tried for the source file, first is used.
    extensions: tuple[str, ...] = ()
    #: Candidates looked for on PATH, in order.
    tool_candidates: tuple[str, ...] = ()
    #: Distribution-appropriate install command, shown to the user.
    install_hint: str = ""
    compiles: bool = True

    def __init__(self, work_dir: Path, *, sandbox: bool = False) -> None:
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox = sandbox
        self._tool: str | None = None
        # Live process handles, so stop() can terminate them on app close.
        self._handles: list[ProcessHandle] = []

    # ------------------------------------------------------------------
    def stop(self) -> None:
        """Terminate every program this adapter has started and is tracking."""
        while self._handles:
            self._handles.pop().stop()

    def forget_run_sessions(self) -> None:
        """Drop handles that have already exited, so the list cannot grow forever."""
        self._handles = [h for h in self._handles if h.process.poll() is None]

    def _track(self, handle: ProcessHandle) -> ProcessHandle:
        self._handles.append(handle)
        return handle

    # -- detection ----------------------------------------------------
    @property
    def tool_path(self) -> str:
        """Absolute path to the tool, raising a clear error when absent."""
        if self._tool is None:
            found = find_tool(self.tool_candidates)
            if not found:
                raise ToolMissingError(
                    self.display_name or self.language_id,
                    self.install_hint,
                    self.tool_candidates,
                )
            self._tool = found
        return self._tool

    def detect(self, refresh: bool = False) -> ToolInfo:
        if refresh:
            self._tool = None
        found = find_tool(self.tool_candidates)
        return ToolInfo(
            language=self.language_id,
            available=found is not None,
            tool_name=self.tool_candidates[0] if found else None,
            tool_path=found,
            version=tool_version(found) if found else "",
            install_hint=self.install_hint,
        )

    @property
    def available(self) -> bool:
        return find_tool(self.tool_candidates) is not None

    # -- source files -------------------------------------------------
    @property
    def extension(self) -> str:
        return self.extensions[0] if self.extensions else ".txt"

    def source_path(self, filename: str | None = None) -> Path:
        return self.work_dir / (filename or f"main{self.extension}")

    def artifact_path(self) -> Path:
        """Where the compiled binary goes (interpreters ignore this)."""
        return self.work_dir / "program"

    # -- commands -----------------------------------------------------
    def compile_argv(self, source: Path, artifact: Path) -> list[str] | None:
        """Command to build ``source``, or ``None`` for interpreted languages."""
        return None

    def run_argv(self, source: Path, artifact: Path) -> list[str]:
        """Command to execute the learner's program."""
        raise NotImplementedError

    def sandbox_argv(self, artifact: Path) -> list[str] | None:
        """Wrapper command that isolates execution, or ``None`` if unsupported.

        Sandbox support is opt-in and reported honestly; an adapter that cannot
        isolate returns ``None`` and the caller says so.
        """
        return None

    def standard_flags(self) -> list[str]:
        """Flags applied to every compile, e.g. warnings and optimisation."""
        return []

    def std_version_flag(self) -> str | None:
        """Language-standard flag such as ``-std=c++17``. ``None`` to omit."""
        return None

    @abstractmethod
    def run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str | None = None,
    ) -> tuple[ProcessResult, ProcessResult | None]:
        """Compile (if needed) then run. Returns ``(build_result, run_result)``."""

    def sandbox_status(self) -> tuple[bool, str]:
        """``(active, explanation)`` describing the containment actually in force.

        User-facing: the app must never claim isolation it does not have.
        Interpreted languages have no binary to isolate, so the base
        implementation says so plainly rather than implying a sandbox.
        """
        if self.kind == "interpreted":
            return False, (
                f"{self.display_name} has no compiled binary, so there is nothing to "
                "sandbox. Resource limits (CPU, memory, file size) and the runtime "
                "timeout still apply."
            )
        return False, "No sandbox is active."

    def start_run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str | None = None,
    ) -> tuple[ProcessResult, ProcessHandle | None]:
        """Non-blocking variant so the UI can offer a working Stop button."""
        raise NotImplementedError("This adapter does not support stoppable runs")