"""Python execution adapter.

Runs the configured interpreter with ``-I`` (isolated mode). Isolated mode
ignores the user's environment variables and the current directory on
``sys.path``, which stops a stray ``PYTHONSTARTUP`` or a module in the working
directory from changing behaviour — important when the code being run is
untrusted.

There is no build step. The "compile" result says so plainly rather than
pretending a compiler ran.
"""

from __future__ import annotations

from pathlib import Path

from .interpreted import InterpretedAdapter


class PythonAdapter(InterpretedAdapter):
    """Execute Python with the configured interpreter."""

    language_id = "python"
    display_name = "Python"
    kind = "interpreted"
    extensions = (".py",)
    tool_candidates = ("python3", "python")
    install_hint = "sudo dnf install python3"
    compiles = False

    def run_argv(self, source: Path, artifact: Path) -> list[str]:
        # -I: isolated mode - ignore env vars and the working directory on
        # sys.path. -B: do not write .pyc files into the work directory.
        return [self.tool_path, "-I", "-B", str(source)]