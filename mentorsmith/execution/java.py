"""Java execution adapter.

Java is a two-step language:
  1. javac compiles Main.java -> Main.class (bytecode)
  2. java -cp <dir> Main runs the bytecode in the JVM

All exercises enforce public class Main so the class name always
matches the filename, which is a hard javac requirement.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from .base import RunSpec, ToolInfo, find_tool, start, truncate
from .compiled import CompiledAdapter, ProcessResult, _feed_stdin


class JavaAdapter(CompiledAdapter):
    """Compile Java with javac and run with java."""

    language_id = "java"
    display_name = "Java"
    kind = "compiled"
    extensions = (".java",)
    tool_candidates = ("javac",)
    install_hint = "sudo dnf install java-latest-openjdk-devel"
    compiles = True

    # The source file MUST be named Main.java (class name = filename rule).
    _source_name = "Main.java"

    # ------------------------------------------------------------------ #
    # Path helpers
    # ------------------------------------------------------------------ #

    def source_path(self, filename: str | None = None) -> Path:
        # Ignore whatever filename the caller passes; always Main.java.
        return self.work_dir / self._source_name

    def artifact_path(self) -> Path:
        # javac writes Main.class into work_dir; we store the dir itself
        # as the "artifact" and pass it to java -cp.
        return self.work_dir

    # ------------------------------------------------------------------ #
    # Compilation
    # ------------------------------------------------------------------ #

    def _java_runtime_version(self) -> str | None:
        """Find the major version of the installed java runtime so javac targets it."""
        import re
        import subprocess

        try:
            java_cmd = shutil.which("java") or "java"
            proc = subprocess.run([java_cmd, "-version"], capture_output=True, text=True, timeout=5)
            out = proc.stderr or proc.stdout or ""
            match = re.search(r'version "(\d+)', out)
            if match:
                return match.group(1)
        except Exception:
            pass
        return None

    def compile_argv(self, source: Path, artifact: Path) -> list[str]:
        cmd = [self.tool_path, "-encoding", "UTF-8"]
        release = self._java_runtime_version()
        if release:
            cmd.extend(["--release", release])
        cmd.append(str(source))
        return cmd

    def compile(self, source: str, filename: str | None = None) -> ProcessResult:
        """Write Main.java and run javac on it."""
        src = self.source_path()
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(source, encoding="utf-8")

        # Clear any stale Main.class
        main_class = self.work_dir / "Main.class"
        main_class.unlink(missing_ok=True)

        spec = RunSpec(
            argv=self.compile_argv(src, self.artifact_path()),
            cwd=self.work_dir,
            stdin_data="",
            timeout=self.compile_timeout,
            limit_memory=False,
        )
        handle = start(spec)
        result = handle.wait(self.compile_timeout)
        return result

    # ------------------------------------------------------------------ #
    # Running
    # ------------------------------------------------------------------ #

    def run_argv(self, source: Path, artifact: Path) -> list[str]:
        java_cmd = shutil.which("java") or "java"
        return [java_cmd, "-cp", str(artifact), "Main"]

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

        spec = RunSpec(
            argv=self.run_argv(self.source_path(), self.artifact_path()),
            cwd=self.work_dir,
            stdin_data=stdin_data,
            timeout=self.run_timeout,
            limit_memory=False,
        )
        handle = start(spec)
        _feed_stdin(handle, stdin_data)
        self._track(handle)
        return compile_result, handle.wait(self.run_timeout)

    def sandbox_status(self) -> tuple[bool, str]:
        return False, (
            "Java runs in the JVM which provides its own memory isolation. "
            "Additional OS-level sandboxing is not applied."
        )
