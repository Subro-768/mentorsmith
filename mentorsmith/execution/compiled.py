"""Shared compile-then-run logic for statically compiled languages.

C++ and C differ in their tool flags and diagnostics, not in the shape of the
operation, so the sequence lives once here and each language supplies the
command lines.
"""

from __future__ import annotations

import subprocess
import time
from pathlib import Path

from .base import (
    LanguageAdapter,
    ProcessHandle,
    ProcessResult,
    RunSpec,
    start,
    truncate,
)


class CompiledAdapter(LanguageAdapter):
    """Compile to a native binary, then execute it."""

    kind = "compiled"
    compiles = True

    def compile(
        self,
        source: str,
        filename: str | None = None,
        extra_args: tuple[str, ...] = (),
    ) -> ProcessResult:
        """Write ``source`` to the work directory and build it.

        A stale binary is removed first, so a failed compile can never leave an
        old executable behind that appears to run.
        """
        compiler = self.tool_path
        source_file = self.source_path(filename)
        artifact = self.artifact_path()

        source_file.write_text(source, encoding="utf-8")
        artifact.unlink(missing_ok=True)

        argv = self.compile_argv(source_file, artifact)
        if argv is None:  # pragma: no cover - subclasses override this
            raise NotImplementedError(f"{self.language_id} has no compile command")
        argv = [*argv, *extra_args]

        started = time.monotonic()
        try:
            proc = subprocess.run(
                argv,
                capture_output=True,
                timeout=self.compile_timeout,
                text=True,
                cwd=str(self.work_dir),
            )
        except subprocess.TimeoutExpired:
            return ProcessResult(
                ok=False,
                command=argv,
                stderr=(
                    f"Compilation exceeded {self.compile_timeout}s and was stopped. "
                    "This usually means a template or macro has recursed indefinitely."
                ),
                timed_out=True,
                duration_s=time.monotonic() - started,
            )
        except OSError as exc:
            return ProcessResult(
                ok=False, command=argv, error=f"Could not run the compiler: {exc}"
            )

        ok = proc.returncode == 0 and artifact.exists()
        return ProcessResult(
            ok=ok,
            command=argv,
            stdout=truncate(proc.stdout or ""),
            stderr=truncate(proc.stderr or ""),
            exit_code=proc.returncode,
            duration_s=time.monotonic() - started,
            error="" if ok else f"Compilation failed with exit code {proc.returncode}.",
        )

    #: Set by the owning adapter; overridable per instance.
    compile_timeout: int = 30
    run_timeout: int = 5
    memory_limit_bytes: int = 1024 * 1024 * 1024

    def run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str | None = None,
    ) -> tuple[ProcessResult, ProcessResult | None]:
        compile_result = self.compile(source, filename)
        if not compile_result.ok:
            return compile_result, None

        artifact = self.artifact_path()
        spec = RunSpec(
            argv=self.run_argv(self.source_path(filename), artifact),
            cwd=self.work_dir,
            stdin_data=stdin_data,
            timeout=self.run_timeout,
            memory_limit_bytes=self.memory_limit_bytes,
            prefix=self.sandbox_argv(artifact) or [],
        )
        handle = start(spec)
        _feed_stdin(handle, stdin_data)
        self._track(handle)
        return compile_result, handle.wait(self.run_timeout)

    def start_run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str | None = None,
    ) -> tuple[ProcessResult, ProcessHandle | None]:
        compile_result = self.compile(source, filename)
        if not compile_result.ok:
            return compile_result, None

        artifact = self.artifact_path()
        spec = RunSpec(
            argv=self.run_argv(self.source_path(filename), artifact),
            cwd=self.work_dir,
            stdin_data=stdin_data,
            timeout=self.run_timeout,
            memory_limit_bytes=self.memory_limit_bytes,
            prefix=self.sandbox_argv(artifact) or [],
        )
        handle = start(spec)
        _feed_stdin(handle, stdin_data)
        self._track(handle)
        return compile_result, handle


def _feed_stdin(handle: ProcessHandle, data: str) -> None:
    """Write optional input and close stdin so programs awaiting input finish."""
    process = handle.process
    stdin = getattr(process, "stdin", None)
    if stdin is None:
        return
    try:
        if data:
            stdin.write(data)
        stdin.close()
    except (BrokenPipeError, OSError):
        pass