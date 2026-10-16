"""Backwards-compatible entry point for C++ execution.

Phase 1 shipped :class:`Toolchain` here. Phase 4 factored the process, limit
and sandbox logic into :mod:`mentorsmith.execution` so Python, C and JavaScript
could share it, and moved the C++ specifics into
:class:`mentorsmith.execution.cpp.CppAdapter`.

This module remains so existing imports and saved settings keep working. New
code should use :mod:`mentorsmith.execution` instead.

.. deprecated::
   Prefer ``mentorsmith.execution.adapter("cpp", work_dir)``.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..execution.base import ProcessHandle, ProcessResult, ToolMissingError
from ..execution.cpp import CppAdapter
from ..execution.cpp import DEFAULT_CXX_STANDARD, DEFAULT_WARNINGS

#: The result type used across Phase 1 and Phase 2.
CommandResult = ProcessResult
RunSession = ProcessHandle
CompilerNotFoundError = ToolMissingError

MAX_OUTPUT_CHARS = 200_000

CANDIDATE_COMPILERS = CppAdapter.tool_candidates


@dataclass
class CompilerInfo:
    """Phase 1 compiler-detection result.

    Field names are preserved verbatim because the UI and the Phase 1 tests
    read ``.name``, ``.path``, ``.version`` and ``.bubblewrap``.
    """

    available: bool = False
    path: str | None = None
    name: str | None = None
    version: str = ""
    bubblewrap: str | None = None

    @property
    def sandbox_available(self) -> bool:
        return self.bubblewrap is not None


class Toolchain(CppAdapter):
    """C++ compile-and-run toolchain.

    A thin subclass of :class:`~mentorsmith.execution.cpp.CppAdapter` that
    keeps the Phase 1 constructor signature, so
    ``Toolchain(work_dir=..., sandbox=..., compile_timeout=..., run_timeout=...)``
    and every attribute the UI and tests already use still work.
    """

    def __init__(
        self,
        work_dir: Path | None = None,
        *,
        sandbox: bool = False,
        compile_timeout: int = 30,
        run_timeout: int = 5,
        memory_limit_bytes: int = 1024 * 1024 * 1024,
    ) -> None:
        from ..config import work_dir as default_work_dir

        super().__init__(work_dir or default_work_dir(), sandbox=sandbox)
        self.compile_timeout = compile_timeout
        self.run_timeout = run_timeout
        self.memory_limit_bytes = memory_limit_bytes

    @property
    def compiler_path(self) -> str:
        """Absolute path to the compiler, raising a clear error if absent."""
        return self.tool_path

    def compile(
        self,
        source: str,
        filename: str = "main.cpp",
        extra_args: tuple[str, ...] = (),
    ) -> ProcessResult:
        return super().compile(source, filename, extra_args)

    def run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str = "main.cpp",
    ) -> tuple[ProcessResult, ProcessResult | None]:
        return super().run(source, stdin_data=stdin_data, filename=filename)

    def start_run(
        self,
        source: str,
        *,
        stdin_data: str = "",
        filename: str = "main.cpp",
    ) -> tuple[ProcessResult, ProcessHandle | None]:
        return super().start_run(source, stdin_data=stdin_data, filename=filename)

    def detect(self, refresh: bool = False) -> CompilerInfo:
        """Compiler availability, with the Phase 1 field names."""
        info = super().detect(refresh=refresh)
        return CompilerInfo(
            available=info.available,
            path=info.tool_path,
            name=info.tool_name,
            version=info.version,
            bubblewrap=shutil.which("bwrap") if self.sandbox else None,
        )

    def sandbox_status(self) -> tuple[bool, str]:
        """``(active, explanation)`` describing the containment actually in force.

        Wording is user-facing: the app never claims isolation it does not
        have.
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

    def forget(self, session: ProcessHandle) -> None:
        """Kept for API compatibility; handles are not tracked centrally."""
        return None

    def forget_run_sessions(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def binary_path(self) -> Path:
        return self.artifact_path()


__all__ = [
    "Toolchain",
    "CommandResult",
    "RunSession",
    "CompilerInfo",
    "CompilerNotFoundError",
    "CANDIDATE_COMPILERS",
    "DEFAULT_CXX_STANDARD",
    "DEFAULT_WARNINGS",
    "MAX_OUTPUT_CHARS",
]