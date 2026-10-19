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

from .base import RunSpec, start
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

    #: Heap ceiling for learner code, in megabytes.
    #:
    #: The OS-level cap (``RLIMIT_AS``) cannot be used here: the JVM reserves
    #: far more virtual address space than it ever touches, so a hard address
    #: limit kills the JVM itself rather than the program - the same reason
    #: Node.js needs ``--max-old-space-size``. That makes the cap below the
    #: *only* thing standing between a runaway exercise and an exhausted
    #: machine, so it is set explicitly rather than left to the JVM's default
    #: of a quarter of physical RAM.
    #:
    #: 2 GiB is comfortably above anything a teaching exercise needs, and was
    #: chosen the same way Node's was: large enough not to interfere, small
    #: enough that sixteen of them would not swap the machine.
    max_heap_megabytes = 2048

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
        """Find the major version of the installed java runtime.

        javac targets the *runtime*, not itself: a newer javac emitting
        bytecode an older `java` cannot load fails at run time with an error
        the learner cannot act on.

        Java 8 and earlier version themselves "1.8.0_402", so the leading
        component is a 1 and not the major version. Passing that through gives
        `javac --release 1`, which is not a valid release at all - so the
        second component is used instead.
        """
        import re
        import subprocess

        try:
            java_cmd = shutil.which("java") or "java"
            proc = subprocess.run([java_cmd, "-version"], capture_output=True, text=True, timeout=5)
            out = proc.stderr or proc.stdout or ""
            match = re.search(r'version "([\d._]+)', out)
            if not match:
                return None
            parts = match.group(1).split(".")
            if parts[0] == "1" and len(parts) > 1:
                return parts[1]          # 1.8.0_402 -> 8
            return parts[0]              # 21.0.2   -> 21
        except Exception:
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
        return [java_cmd, f"-Xmx{self.max_heap_megabytes}m", "-cp", str(artifact), "Main"]

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
        """Honest about what is and is not contained.

        This used to claim the JVM "provides its own memory isolation", which
        is not true - the JVM applies no heap ceiling of its own beyond
        defaulting to a quarter of physical RAM. What actually bounds learner
        code here is ``-Xmx``; OS-level sandboxing is genuinely not applied.
        """
        return False, (
            f"No OS-level sandbox. Memory is bounded by the JVM heap cap "
            f"(-Xmx{self.max_heap_megabytes}m); file, network and process "
            f"access are not restricted, so code runs as you with your "
            f"permissions."
        )
