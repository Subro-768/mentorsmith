"""Compiler detection, compilation and execution — including real failures."""

from __future__ import annotations

from pathlib import Path

import pytest

from mentorsmith.compiler.toolchain import (
    CompilerNotFoundError,
    Toolchain,
)

# Small, valid programs used throughout.
HELLO = '#include <iostream>\nint main(){ std::cout << "hi\\n"; return 0; }\n'
BROKEN = 'int main() { int x = "not an int"; }\n'
INFINITE = "int main(){ for(;;){} }\n"
EXIT_THREE = "int main(){ return 3; }\n"
USES_STDIN = (
    "#include <iostream>\n"
    "int main(){ std::string s; std::getline(std::cin, s);"
    ' std::cout << "got:" << s << "\\n"; return 0; }\n'
)
# Asks for 1 GiB, which must be refused when the address-space limit is lower.
LEAKS_MEMORY = "int main(){ char* p = new char[1024*1024*1024]; p[0]=1; return 0; }\n"


# ----------------------------------------------------------------------
# Detection
# ----------------------------------------------------------------------
def test_detect_reports_a_compiler_on_this_machine(compiler_available: bool) -> None:
    info = Toolchain().detect()
    assert info.available is compiler_available
    if info.available:
        assert info.name in {"g++", "clang++", "c++"}
        assert info.path


def test_compiler_path_raises_when_absent(toolchain: Toolchain, monkeypatch) -> None:
    monkeypatch.setattr(
        "mentorsmith.compiler.toolchain.shutil.which", lambda _name: None
    )
    with pytest.raises(CompilerNotFoundError) as excinfo:
        toolchain.compiler_path
    message = str(excinfo.value)
    # The error must tell the user what to do, not just that it failed.
    assert "dnf install" in message
    assert "g++" in message


def test_sandbox_status_is_honest_when_disabled(toolchain: Toolchain) -> None:
    active, note = toolchain.sandbox_status()
    assert active is False
    assert "Sandbox OFF" in note


def test_sandbox_status_reports_missing_bubblewrap(toolchain: Toolchain) -> None:
    toolchain.sandbox = True
    toolchain.detect(refresh=True)
    active, note = toolchain.sandbox_status()
    if active:
        assert "ACTIVE" in note
    else:
        # Must say the sandbox is NOT active rather than implying it is.
        assert "NOT active" in note or "Sandbox OFF" in note
        assert "bubblewrap" in note


# ----------------------------------------------------------------------
# Successful compilation
# ----------------------------------------------------------------------
@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_compile_and_run_success(toolchain: Toolchain) -> None:
    compile_result, run_result = toolchain.run(HELLO)
    assert compile_result.ok, compile_result.stderr
    assert compile_result.exit_code == 0
    assert run_result is not None
    assert run_result.ok
    assert run_result.stdout == "hi\n"
    assert run_result.exit_code == 0


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_warnings_do_not_fail_the_build(toolchain: Toolchain) -> None:
    source = (
        "int main(){ int unused = 5; return 0; }\n"
    )
    compile_result, run_result = toolchain.run(source)
    assert compile_result.ok, compile_result.stderr
    # -Wall should have complained; the build must still succeed.
    assert "unused" in compile_result.stderr
    assert run_result is not None and run_result.ok


# ----------------------------------------------------------------------
# Failed compilation
# ----------------------------------------------------------------------
@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_failed_compilation_reports_real_diagnostics(toolchain: Toolchain) -> None:
    compile_result, run_result = toolchain.run(BROKEN)
    assert not compile_result.ok
    assert run_result is None, "a program that failed to compile must not be run"
    assert compile_result.exit_code != 0
    assert "error:" in compile_result.stderr
    assert "main.cpp" in compile_result.stderr


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_failed_compile_removes_stale_binary(toolchain: Toolchain) -> None:
    """A stale executable must never be run after a failed compile."""
    compile_result, _ = toolchain.run(HELLO)
    assert compile_result.ok
    assert toolchain.binary_path().exists()

    compile_result, run_result = toolchain.run(BROKEN)
    assert not compile_result.ok
    assert not toolchain.binary_path().exists()
    assert run_result is None


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_compile_writes_into_the_work_directory(toolchain: Toolchain) -> None:
    toolchain.run(HELLO)
    source_file = toolchain.work_dir / "main.cpp"
    assert source_file.exists()
    assert "int main" in source_file.read_text()


# ----------------------------------------------------------------------
# Runtime behaviour
# ----------------------------------------------------------------------
@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_nonzero_exit_code_is_reported(toolchain: Toolchain) -> None:
    compile_result, run_result = toolchain.run(EXIT_THREE)
    assert compile_result.ok
    assert run_result is not None
    assert not run_result.ok
    assert run_result.exit_code == 3


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_runtime_timeout_stops_the_program(toolchain: Toolchain) -> None:
    toolchain.run_timeout = 2
    compile_result, run_result = toolchain.run(INFINITE)
    assert compile_result.ok
    assert run_result is not None
    assert run_result.timed_out
    assert "runtime limit" in run_result.error


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_stdout_and_stderr_are_kept_separate(toolchain: Toolchain) -> None:
    source = (
        "#include <cstdio>\n"
        'int main(){ std::fprintf(stderr, "ERR\\n"); std::printf("OUT\\n"); return 0; }\n'
    )
    _compile, run_result = toolchain.run(source)
    assert run_result is not None
    assert run_result.stdout == "OUT\n"
    assert run_result.stderr == "ERR\n"


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_stdin_is_delivered(toolchain: Toolchain) -> None:
    _compile, run_result = toolchain.run(USES_STDIN, stdin_data="hello there\n")
    assert run_result is not None
    assert "got:hello there" in run_result.stdout


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_start_run_returns_a_pollable_session(toolchain: Toolchain) -> None:
    compile_result, session = toolchain.start_run(HELLO)
    assert compile_result.ok
    assert session is not None
    result = session.poll()          # likely still running
    if result is None:
        session.process.wait(timeout=10)
        result = session.poll()
    assert result is not None
    assert result.stdout == "hi\n"


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_stop_terminates_a_hanging_program(toolchain: Toolchain) -> None:
    """The Stop button must actually work on an infinite loop."""
    compile_result, session = toolchain.start_run(INFINITE)
    assert compile_result.ok and session is not None
    session.stop()
    assert session.process.poll() is not None, "program kept running after stop()"


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_memory_limit_prevents_unbounded_allocation(toolchain: Toolchain) -> None:
    """A runaway allocation must be refused, not exhaust host memory."""
    toolchain.memory_limit_bytes = 128 * 1024 * 1024
    _compile, run_result = toolchain.run(LEAKS_MEMORY)
    assert run_result is not None
    assert not run_result.ok, "an unbounded allocation should have been rejected"


# ----------------------------------------------------------------------
# Sandbox isolation
# ----------------------------------------------------------------------
PROBE_HOST_FILESYSTEM = r"""
#include <cstdio>
#include <fstream>
int main() {
    std::ifstream home("/home/subro/Documents");
    std::printf("read:%s\n", home ? "VISIBLE" : "blocked");
    std::ofstream out("/home/subro/Documents/mentorsmith_sandbox_probe.txt");
    std::printf("write:%s\n", out ? "ALLOWED" : "blocked");
    return 0;
}
"""


@pytest.mark.skipif(
    not (Toolchain().detect().available and __import__("shutil").which("bwrap")),
    reason="needs a C++ compiler and bubblewrap",
)
def test_sandbox_blocks_host_filesystem_access(toolchain: Toolchain, monkeypatch) -> None:
    """When the sandbox is active, learner code must not see the host FS."""
    import shutil

    if not shutil.which("bwrap"):
        pytest.skip("bubblewrap not installed")

    monkeypatch.setenv("HOME", "/home/subro")
    toolchain.sandbox = True
    toolchain.detect(refresh=True)
    active, note = toolchain.sandbox_status()
    if not active:
        pytest.skip(f"sandbox unavailable on this host: {note}")

    probe_path = Path("/home/subro/Documents/mentorsmith_sandbox_probe.txt")
    _compile, run_result = toolchain.run(PROBE_HOST_FILESYSTEM)
    assert run_result is not None, run_result.error

    assert "read:blocked" in run_result.stdout, run_result.stdout
    assert "write:blocked" in run_result.stdout, run_result.stdout
    # Nothing may leak onto the real host.
    assert not probe_path.exists()


@pytest.mark.skipif(not Toolchain().detect().available, reason="no C++ compiler")
def test_sandbox_still_runs_ordinary_programs(toolchain: Toolchain) -> None:
    """Isolation must not stop a normal hello-world from working."""
    toolchain.sandbox = True
    toolchain.detect(refresh=True)
    if not toolchain.sandbox_status()[0]:
        pytest.skip("sandbox unavailable on this host")
    compile_result, run_result = toolchain.run(HELLO)
    assert compile_result.ok, compile_result.stderr
    assert run_result is not None
    assert run_result.ok, f"sandboxed run failed: {run_result.stderr}"
    assert run_result.stdout == "hi\n"


# ----------------------------------------------------------------------
# Filesystem containment
# ----------------------------------------------------------------------
def test_source_is_written_only_to_the_work_directory(
    toolchain: Toolchain, tmp_path: Path
) -> None:
    """Compiled output must never land next to the application source."""
    assert toolchain.work_dir.is_relative_to(tmp_path)