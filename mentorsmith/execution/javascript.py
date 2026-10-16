"""JavaScript execution adapter.

Runs the configured Node.js runtime. Node is treated as optional: many people
use other runtimes (Deno, Bun, browsers), so a missing Node produces a clear
install hint rather than a crash, and the adapter can be pointed at an
alternative binary.

``--disallow-code-generation-from-strings`` is passed so learner code cannot
reach ``eval``/``Function`` and smuggle in code that never appeared in the
editor.
"""

from __future__ import annotations

from pathlib import Path

from .interpreted import InterpretedAdapter


class JavaScriptAdapter(InterpretedAdapter):
    """Execute JavaScript with Node.js."""

    language_id = "javascript"
    display_name = "JavaScript"
    kind = "interpreted"
    # .mjs first: Node treats that extension as an ES module, so import and
    # top-level await behave the way modern JavaScript readers expect without
    # needing a flag or a package.json.
    extensions = (".mjs", ".js")
    tool_candidates = ("node", "nodejs")
    install_hint = "sudo dnf install nodejs"
    compiles = False

    #: V8 reserves a large block of *virtual* address space before running any
    #: user code. The 1 GiB default used for C and C++ kills Node immediately
    #: with "Fatal process out of memory". Measured on this machine: 1 GiB
    #: fails, 2 GiB and above work, so 4 GiB is used for headroom.
    #:
    #: A large virtual limit would be useless as containment on its own, so the
    #: real heap is bounded with --max-old-space-size instead. Verified: an
    #: unbounded allocation loop is terminated by the V8 heap limit rather than
    #: being allowed to consume host memory.
    memory_limit_bytes = 4 * 1024 * 1024 * 1024
    max_heap_megabytes = 256

    def run_argv(self, source: Path, artifact: Path) -> list[str]:
        return [
            self.tool_path,
            f"--max-old-space-size={self.max_heap_megabytes}",
            # Block eval()/Function() so learner code cannot smuggle in code
            # that never appeared in the editor.
            "--disallow-code-generation-from-strings",
            str(source),
        ]