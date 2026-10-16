"""C execution adapter (GCC or Clang).

The same toolchain family as C++, with the differences that matter:

* compiled as C, not C++ (``-x c`` so a ``.c`` file is never mistaken for C++)
* no C++ standard flag; ``-std=c11`` instead
* implicit declarations and format mismatches are warnings that become real
  bugs, so the warning set is kept on
"""

from __future__ import annotations

from pathlib import Path

from .cpp import CppAdapter

DEFAULT_C_STANDARD = "c11"

#: Flags that turn common latent C bugs into build failures.
C_EXTRA_FLAGS = ("-Werror=implicit-function-declaration", "-Werror=return-type")


class CAdapter(CppAdapter):
    """Compile C with gcc or clang and run the binary."""

    language_id = "c"
    display_name = "C"
    kind = "compiled"
    extensions = (".c",)
    tool_candidates = ("gcc", "clang")
    install_hint = "sudo dnf install gcc"
    compiles = True

    def std_version_flag(self) -> str | None:
        return f"-std={DEFAULT_C_STANDARD}"

    def standard_flags(self) -> list[str]:
        return ["-Wall", "-Wextra", *C_EXTRA_FLAGS]

    def compile_argv(self, source: Path, artifact: Path) -> list[str]:
        # -x c forces C mode even if the file is renamed to something else.
        return [
            self.tool_path,
            "-x", "c",
            self.std_version_flag(),
            *self.standard_flags(),
            "-O0",
            "-g",
            str(source),
            "-o",
            str(artifact),
        ]