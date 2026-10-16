"""C++ execution adapter (GCC or Clang).

Kept behaviourally identical to the Phase 1 toolchain so existing behaviour and
tests keep working; the logic was factored into :mod:`mentorsmith.execution`
when Phase 4 added other languages.
"""

from __future__ import annotations

import os
from pathlib import Path

from .compiled import CompiledAdapter

DEFAULT_CXX_STANDARD = "c++17"
DEFAULT_WARNINGS = ("-Wall", "-Wextra")


class CppAdapter(CompiledAdapter):
    """Build C++ with g++ or clang++ and run the binary."""

    language_id = "cpp"
    display_name = "C++"
    kind = "compiled"
    extensions = (".cpp", ".cc", ".cxx")
    tool_candidates = ("g++", "clang++", "c++")
    install_hint = "sudo dnf install gcc"
    compiles = True

    def standard_flags(self) -> list[str]:
        return list(DEFAULT_WARNINGS)

    def std_version_flag(self) -> str | None:
        return f"-std={DEFAULT_CXX_STANDARD}"

    def compile_argv(self, source: Path, artifact: Path) -> list[str]:
        return [
            self.tool_path,
            self.std_version_flag(),
            *self.standard_flags(),
            "-O0",
            "-g",
            str(source),
            "-o",
            str(artifact),
        ]

    def run_argv(self, source: Path, artifact: Path) -> list[str]:
        return [str(artifact)]

    def sandbox_status(self) -> tuple[bool, str]:
        """``(active, explanation)`` describing the containment actually in force.

        Wording is user-facing. The app never claims isolation it does not have.
        """
        import shutil

        if not self.sandbox:
            return False, (
                "Sandbox OFF. Only CPU, memory and file-size limits are applied. "
                "Your code runs as your own user with your own file access."
            )
        if not shutil.which("bwrap"):
            return False, (
                "Sandbox REQUESTED but bubblewrap (bwrap) is not installed, so it is "
                "NOT active. Only resource limits apply. Install it with:\n"
                "    sudo dnf install bubblewrap"
            )
        return True, (
            "Sandbox ACTIVE via bubblewrap: private mount namespace, no network, "
            "read-only system directories, plus CPU/memory/file limits."
        )

    def sandbox_argv(self, artifact: Path) -> list[str] | None:
        """Isolate the binary with bubblewrap when it is installed.

        Only the directories the dynamic loader needs are exposed, all
        read-only. No host directory, no network, no writable persistent path.
        """
        import shutil

        bwrap = shutil.which("bwrap")
        if not self.sandbox or not bwrap:
            return None

        argv = [
            bwrap,
            "--unshare-user",
            "--unshare-pid",
            "--unshare-net",
            "--unshare-ipc",
            "--unshare-uts",
            "--new-session",
            "--die-with-parent",
            "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/etc/ld.so.cache", "/etc/ld.so.cache",
            "--ro-bind", "/etc/ld.so.conf", "/etc/ld.so.conf",
            "--ro-bind", "/etc/ld.so.conf.d", "/etc/ld.so.conf.d",
        ]

        # /bin, /lib, /lib64 and /sbin are symlinks into /usr on current
        # Fedora. They must be recreated *inside* the namespace, otherwise the
        # ELF interpreter (/lib64/ld-linux-x86-64.so.2) is unreachable and the
        # program fails with "No such file or directory".
        for path_str in ("/bin", "/sbin", "/lib", "/lib64", "/lib32"):
            path = Path(path_str)
            if not path.exists():
                continue
            if path.is_symlink():
                argv += ["--symlink", os.readlink(path), path_str]
            else:
                argv += ["--ro-bind", path_str, path_str]

        argv += [
            "--proc", "/proc",
            "--dev", "/dev",
            "--tmpfs", "/tmp",
            "--ro-bind", str(artifact), "/prog",
            "--chdir", "/tmp",
            "--", "/prog",
        ]
        return argv