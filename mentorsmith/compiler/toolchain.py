"""Detect a C++ compiler, compile the learner's code, and run it.

Security posture
----------------
Learner code is *untrusted*. Two independent layers of containment are used,
and both are optional so the failure modes are explicit:

1. **Resource limits** (:func:`_limit_resources`) cap CPU time, address space,
   file size and process count for the child process only.
2. **Namespace isolation** via ``bwrap`` (bubblewrap), when enabled and
   installed, runs the binary with a private mount namespace, no network, and
   a read-only view of the system directories.

Neither layer is a complete sandbox, and this module does not claim one.
``bwrap`` relies on unprivileged user namespaces, which need kernel and
distribution support; where it is unavailable the app runs with resource
limits only and says so in the UI. Unprivileged user namespaces give far less
protection than a dedicated VM or a properly configured container, so treat
this as defence in depth rather than isolation you should rely on for
genuinely hostile code.

The compiler is always invoked as an argument vector -- never through a shell
-- so learner text cannot be interpreted as shell syntax.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from ..config import work_dir as default_work_dir

#: Argument vector tried in order when detecting a compiler.
CANDIDATE_COMPILERS = ("g++", "clang++", "c++")

DEFAULT_CXX_STANDARD = "c++17"
DEFAULT_WARNINGS = ("-Wall", "-Wextra")
MAX_OUTPUT_CHARS = 200_000


class CompilerNotFoundError(RuntimeError):
    """No usable C++ compiler was found on the system."""


def _truncate(text: str) -> str:
    """Bound captured output so a runaway program cannot exhaust memory."""
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    return text[:MAX_OUTPUT_CHARS] + f"\n... [output truncated at {MAX_OUTPUT_CHARS} characters]"


def _as_text(value: str | bytes | None) -> str:
    """Normalise a stream value to text.

    Subprocesses are created with ``text=True``, so ``communicate`` returns
    ``str``. The ``bytes`` branch keeps this usable if that ever changes.
    """
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _limit_resources(cpu_seconds: int, memory_bytes: int, max_file_bytes: int) -> None:
    """Apply POSIX resource limits to the child process.

    Installed via ``preexec_fn`` so it runs in the child after ``fork``. On a
    non-POSIX platform the import below fails and limits are skipped; the app
    still runs, and the UI reports that limits were unavailable.

    ``RLIMIT_NPROC`` is deliberately **not** set. It limits processes per
    *real UID*, not per process tree, so a value low enough to matter would
    also break ``fork`` for the learner's own unrelated programs. Empirically a
    limit of 64 made ``bwrap`` fail with EAGAIN on this machine, because the
    account already had more than 64 live processes.
    """
    try:
        import resource
    except ImportError:  # pragma: no cover - non-POSIX
        return

    def set_if_supported(what: int, soft: int, hard: int) -> None:
        try:
            cur_soft, cur_hard = resource.getrlimit(what)
            # Never try to raise a hard limit we do not already hold.
            new_hard = hard if cur_hard == resource.RLIM_INFINITY else min(hard, cur_hard)
            new_soft = min(soft, new_hard)
            resource.setrlimit(what, (new_soft, new_hard))
        except (ValueError, OSError):
            pass

    set_if_supported(resource.RLIMIT_CPU, cpu_seconds, cpu_seconds + 1)
    set_if_supported(resource.RLIMIT_AS, memory_bytes, memory_bytes)
    set_if_supported(resource.RLIMIT_FSIZE, max_file_bytes, max_file_bytes)
    set_if_supported(resource.RLIMIT_CORE, 0, 0)


@dataclass
class CompilerInfo:
    """Result of compiler detection."""

    available: bool
    path: str | None
    name: str | None
    version: str = ""
    bubblewrap: str | None = None

    @property
    def sandbox_available(self) -> bool:
        return self.bubblewrap is not None


@dataclass
class CommandResult:
    """Outcome of one compile or run invocation."""

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
        """stdout and stderr joined, for a single display panel."""
        parts = [part for part in (self.stdout, self.stderr) if part.strip()]
        return "\n".join(parts) if parts else "(no output)"


@dataclass
class RunSession:
    """A running program that the UI can poll and stop.

    Kept separate from :meth:`Toolchain.run` so the Run button can start work
    and the Stop button can terminate it without blocking the GUI thread.
    """

    process: subprocess.Popen
    command: list[str]
    started_at: float = field(default_factory=time.monotonic)

    def poll(self) -> CommandResult | None:
        """Return the result once the process has exited, else ``None``."""
        code = self.process.poll()
        if code is None:
            return None
        stdout, stderr = self.process.communicate()
        return CommandResult(
            ok=code == 0,
            command=list(self.command),
            stdout=_truncate(_as_text(stdout)),
            stderr=_truncate(_as_text(stderr)),
            exit_code=code,
            duration_s=time.monotonic() - self.started_at,
            timed_out=False,
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


class Toolchain:
    """Compiles and runs C++ for the learner, with containment."""

    def __init__(
        self,
        work_dir: Path | None = None,
        *,
        sandbox: bool = False,
        compile_timeout: int = 30,
        run_timeout: int = 5,
        memory_limit_bytes: int = 1024 * 1024 * 1024,
    ) -> None:
        self.work_dir = Path(work_dir) if work_dir else default_work_dir()
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox = sandbox
        self.compile_timeout = compile_timeout
        self.run_timeout = run_timeout
        self.memory_limit_bytes = memory_limit_bytes
        self._info: CompilerInfo | None = None
        # Live run sessions, so stop_all() can terminate them on app close.
        self._sessions: list[RunSession] = []

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    def detect(self, refresh: bool = False) -> CompilerInfo:
        """Find a C++ compiler and report what is available."""
        if self._info is not None and not refresh:
            return self._info

        path = None
        name = None
        version = ""
        for candidate in CANDIDATE_COMPILERS:
            found = shutil.which(candidate)
            if found:
                path, name = found, candidate
                version = self._probe_version(found)
                break

        bubblewrap = shutil.which("bwrap") if self.sandbox else None
        self._info = CompilerInfo(
            available=path is not None,
            path=path,
            name=name,
            version=version,
            bubblewrap=bubblewrap,
        )
        return self._info

    @staticmethod
    def _probe_version(compiler: str) -> str:
        try:
            proc = subprocess.run(
                [compiler, "--version"],
                capture_output=True,
                timeout=10,
                text=True,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        first = (proc.stdout or proc.stderr or "").strip().splitlines()
        return first[0].strip() if first else ""

    @property
    def compiler_path(self) -> str:
        """Absolute path to the compiler, raising a clear error if absent."""
        info = self.detect()
        if not info.available or info.path is None:
            raise CompilerNotFoundError(
                "No C++ compiler found.\n\n"
                "MentorSmith looked for: " + ", ".join(CANDIDATE_COMPILERS) + "\n\n"
                "On Fedora install one with:\n"
                "    sudo dnf install gcc\n\n"
                "Then restart the app."
            )
        return info.path

    def sandbox_status(self) -> tuple[bool, str]:
        """Return ``(active, explanation)`` describing current containment.

        Shown verbatim in the UI so the learner is never misled about how
        isolated their code is.
        """
        info = self.detect()
        if not self.sandbox:
            return False, (
                "Sandbox OFF. Only CPU, memory and file-size limits are applied. "
                "Your code runs as your own user with your own file access."
            )
        if not info.sandbox_available:
            return False, (
                "Sandbox REQUESTED but bubblewrap (bwrap) is not installed, so it is "
                "NOT active. Only resource limits apply. Install it with:\n"
                "    sudo dnf install bubblewrap"
            )
        return True, (
            "Sandbox ACTIVE via bubblewrap: private mount namespace, no network, "
            "read-only system directories, plus CPU/memory/file limits."
        )

    # ------------------------------------------------------------------
    # Compilation
    # ------------------------------------------------------------------
    def compile(
        self,
        source: str,
        filename: str = "main.cpp",
        extra_args: Sequence[str] = (),
    ) -> CommandResult:
        """Write ``source`` to the work directory and compile it."""
        compiler = self.compiler_path
        source_path = self.work_dir / filename
        binary_path = self.work_dir / "program"

        source_path.write_text(source, encoding="utf-8")
        # Remove any stale binary so a failed compile can never leave the old
        # executable behind and appear to succeed.
        binary_path.unlink(missing_ok=True)

        command = [
            compiler,
            f"-std={DEFAULT_CXX_STANDARD}",
            *DEFAULT_WARNINGS,
            "-O0",
            "-g",
            *extra_args,
            str(source_path),
            "-o",
            str(binary_path),
        ]

        started = time.monotonic()
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                timeout=self.compile_timeout,
                text=True,
                cwd=str(self.work_dir),
            )
        except subprocess.TimeoutExpired:
            return CommandResult(
                ok=False,
                command=command,
                stderr=(
                    f"Compilation exceeded {self.compile_timeout}s and was stopped. "
                    "This usually means a template has recursed indefinitely."
                ),
                timed_out=True,
                duration_s=time.monotonic() - started,
            )
        except OSError as exc:
            return CommandResult(
                ok=False, command=command, error=f"Could not run the compiler: {exc}"
            )

        duration = time.monotonic() - started
        return CommandResult(
            ok=proc.returncode == 0 and binary_path.exists(),
            command=command,
            stdout=_truncate(proc.stdout or ""),
            stderr=_truncate(proc.stderr or ""),
            exit_code=proc.returncode,
            duration_s=duration,
            error=(
                ""
                if proc.returncode == 0
                else f"Compilation failed with exit code {proc.returncode}."
            ),
        )

    def binary_path(self) -> Path:
        return self.work_dir / "program"

    # ------------------------------------------------------------------
    # Running
    # ------------------------------------------------------------------
    def _sandbox_argv(self, binary: Path) -> list[str] | None:
        """Build a ``bwrap`` command that isolates ``binary``, or ``None``.

        Only the system directories needed to load the binary's dynamic
        libraries are exposed, and all of them read-only. No host directory,
        no network, no writable persistent path.
        """
        info = self.detect()
        if not info.sandbox_available or info.bubblewrap is None:
            return None

        argv = [
            info.bubblewrap,
            "--unshare-user",
            "--unshare-pid",
            "--unshare-net",
            "--unshare-ipc",
            "--unshare-uts",
            "--new-session",
            "--die-with-parent",
            # Read-only system view needed by the dynamic loader.
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
            "--ro-bind", "/etc/ld.so.conf", "/etc/ld.so.conf",
            "--ro-bind", "/etc/ld.so.conf.d", "/etc/ld.so.conf.d",
        ]

        # /bin, /lib, /lib64 and /sbin are symlinks into /usr on current
        # Fedora. They must be recreated *inside* the namespace, otherwise the
        # ELF interpreter (/lib64/ld-linux-x86-64.so.2) is unreachable and the
        # program fails to start with "No such file or directory". On older
        # layouts they are real directories and are bound instead.
        for path_str in ("/bin", "/sbin", "/lib", "/lib64", "/lib32"):
            path = Path(path_str)
            if not path.exists():
                continue
            if path.is_symlink():
                argv += ["--symlink", os.readlink(path), path_str]
            else:
                argv += ["--ro-bind", path_str, path_str]

        argv += [
            # Private writable scratch space, discarded on exit.
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            # The program itself, read-only, run from an empty directory.
            "--ro-bind", str(binary), "/prog",
            "--chdir", "/tmp",
            "--", "/prog",
        ]
        return argv

    def start_run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str = "main.cpp",
    ) -> tuple[CommandResult, RunSession | None]:
        """Compile, then start the resulting program.

        Returns ``(compile_result, run_session)``. ``run_session`` is ``None``
        when compilation failed. Does not block: the UI polls the session.
        """
        compile_result = self.compile(source, filename=filename)
        if not compile_result.ok:
            return compile_result, None

        binary = self.binary_path()
        argv = self._sandbox_argv(binary) if self.sandbox else [str(binary)]
        started = time.monotonic()

        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.work_dir),
                text=True,
                # start_new_session puts the child in its own process group so
                # stop() can kill anything it spawned, not just the direct child.
                start_new_session=True,
                preexec_fn=lambda: _limit_resources(
                    self.run_timeout + 1, self.memory_limit_bytes, 10 * 1024 * 1024
                ),
            )
        except OSError as exc:
            compile_result.ok = False
            compile_result.error = f"Could not start the program: {exc}"
            return compile_result, None

        if stdin_data:
            try:
                process.stdin.write(stdin_data)
            except (BrokenPipeError, OSError):
                pass
        try:
            if process.stdin is not None:
                process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

        session = RunSession(process=process, command=argv)
        session.started_at = started
        self._sessions.append(session)
        return compile_result, session

    def forget(self, session: RunSession) -> None:
        """Drop a finished session from the live list."""
        if session in self._sessions:
            self._sessions.remove(session)

    def forget_run_sessions(self) -> None:
        """Drop every session that has already exited.

        Called when a compile/run finishes so the live list does not grow
        without bound over a long session.
        """
        self._sessions = [s for s in self._sessions if s.process.poll() is None]

    def run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str = "main.cpp",
    ) -> tuple[CommandResult, CommandResult | None]:
        """Compile and run to completion, blocking until the program finishes.

        Convenience wrapper around :meth:`start_run` for scripts and tests.
        """
        compile_result, session = self.start_run(
            source, stdin_data=stdin_data, filename=filename
        )
        if session is None:
            return compile_result, None

        try:
            run_result = session.process.communicate(timeout=self.run_timeout)
        except subprocess.TimeoutExpired:
            session.stop()
            try:
                stdout, stderr = session.process.communicate(timeout=5)
            except subprocess.TimeoutExpired:  # pragma: no cover - defensive
                stdout, stderr = "", ""
            return compile_result, CommandResult(
                ok=False,
                command=list(session.command),
                stdout=_truncate(_as_text(stdout)),
                stderr=(
                    _truncate(_as_text(stderr))
                    + f"\n[stopped: exceeded the {self.run_timeout}s runtime limit]"
                ),
                exit_code=session.process.returncode,
                duration_s=time.monotonic() - session.started_at,
                timed_out=True,
                error=f"Program exceeded the {self.run_timeout}s runtime limit and was stopped.",
            )

        stdout, stderr = run_result
        exit_code = session.process.returncode
        return compile_result, CommandResult(
            ok=exit_code == 0,
            command=list(session.command),
            stdout=_truncate(stdout or ""),
            stderr=_truncate(stderr or ""),
            exit_code=exit_code,
            duration_s=time.monotonic() - session.started_at,
            error="" if exit_code == 0 else f"Program exited with code {exit_code}.",
        )

    def stop(self) -> None:
        """Terminate every program this toolchain has started and is still tracking.

        Used on app close so nothing is left running.
        """
        while self._sessions:
            session = self._sessions.pop()
            session.stop()