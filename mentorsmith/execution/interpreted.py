"""Interpreted-language adapter base (Python, JavaScript).

Interpreted languages have no build step, so the "compile" result is a
synthetic success explaining that nothing was built. That is reported honestly
rather than faked: the UI shows the real command that was run.
"""

from __future__ import annotations

from .base import (
    LanguageAdapter,
    ProcessHandle,
    ProcessResult,
    RunSpec,
    start,
)
from .compiled import _feed_stdin


class InterpretedAdapter(LanguageAdapter):
    """Write the source and execute it with an interpreter."""

    kind = "interpreted"
    compiles = False

    compile_timeout: int = 30
    run_timeout: int = 5
    memory_limit_bytes: int = 1024 * 1024 * 1024

    def compile(self, source: str, filename: str | None = None) -> ProcessResult:
        """Write the source. Returns a synthetic result: nothing is built."""
        path = self.source_path(filename)
        path.write_text(source, encoding="utf-8")
        return ProcessResult(
            ok=True,
            command=[],
            stdout=(
                f"No build step for {self.display_name}; "
                f"the source was written to {path.name}."
            ),
        )

    def run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str | None = None,
    ) -> tuple[ProcessResult, ProcessResult | None]:
        compile_result = self.compile(source, filename)
        spec = RunSpec(
            argv=self.run_argv(self.source_path(filename), self.artifact_path()),
            cwd=self.work_dir,
            stdin_data=stdin_data,
            timeout=self.run_timeout,
            memory_limit_bytes=self.memory_limit_bytes,
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
        spec = RunSpec(
            argv=self.run_argv(self.source_path(filename), self.artifact_path()),
            cwd=self.work_dir,
            stdin_data=stdin_data,
            timeout=self.run_timeout,
            memory_limit_bytes=self.memory_limit_bytes,
        )
        handle = start(spec)
        _feed_stdin(handle, stdin_data)
        self._track(handle)
        return compile_result, handle