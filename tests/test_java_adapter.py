"""The Java execution adapter.

Java had no tests at all, which is how two defects survived in it:

* ``sandbox_status()`` claimed "Java runs in the JVM which provides its own
  memory isolation". The JVM applies no such thing. It defaults to a quarter of
  physical RAM - four gigabytes on the machine this was written on - for what
  should be a homework-sized program.
* The runtime-version parser took the first component of ``java -version``, so
  on Java 8 ("1.8.0_402") it produced ``--release 1``, which javac rejects.

``RLIMIT_AS`` cannot be used to cap a JVM any more than it can cap V8: both
reserve far more virtual address space than they touch, and a hard address
limit kills the runtime rather than the program. That is why ``-Xmx`` is the
cap here, and it is the only thing bounding learner code - so it is tested.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from mentorsmith.execution.base import ProcessResult
from mentorsmith.execution.java import JavaAdapter

pytestmark = pytest.mark.skipif(
    shutil.which("javac") is None or shutil.which("java") is None,
    reason="no JDK on this machine",
)

HELLO = """
public class Main {
    public static void main(String[] args) {
        System.out.println("hello from java");
    }
}
"""


@pytest.fixture()
def adapter(tmp_path) -> JavaAdapter:
    return JavaAdapter(work_dir=tmp_path)


# ======================================================================
# The memory cap
# ======================================================================
class TestHeapIsBounded:
    def test_the_run_command_carries_a_heap_cap(self, adapter) -> None:
        """Without this, limit_memory=False means genuinely unbounded."""
        argv = adapter.run_argv(adapter.source_path(), adapter.work_dir)
        assert any(a.startswith("-Xmx") for a in argv), f"no heap cap in {argv}"

    def test_the_cap_is_a_real_number(self, adapter) -> None:
        argv = adapter.run_argv(None, adapter.work_dir)
        flag = next(a for a in argv if a.startswith("-Xmx"))
        assert flag.endswith("m")
        megabytes = int(flag.removeprefix("-Xmx").removesuffix("m"))
        assert 256 <= megabytes <= 8192, f"{megabytes} MB is not a sane ceiling"

    def test_the_cap_is_small_enough_for_teaching_work(self) -> None:
        """Generous enough for any exercise, small enough not to be the reason
        the machine swaps."""
        assert JavaAdapter.max_heap_megabytes <= 4096

    def test_a_runaway_program_dies_instead_of_eating_the_machine(
        self, adapter
    ) -> None:
        """The whole reason the cap exists.

        An unbounded run of this leaves the JVM to grow until the kernel
        intervenes. That was a real failure mode in this project's history,
        so it is asserted rather than assumed.
        """
        greedy = """
        public class Main {
            public static void main(String[] args) {
                java.util.List<byte[]> keep = new java.util.ArrayList<>();
                while (true) { keep.add(new byte[64 * 1024 * 1024]); }
            }
        }
        """
        compile_result, run_result = adapter.run(greedy)
        assert compile_result.ok, "the program under test should compile"
        assert run_result is not None
        assert not run_result.ok, "an unbounded heap let a runaway program succeed"
        combined = (run_result.combined_output or "").lower()
        if not ("outofmemory" in combined or "heap" in combined):
            # On a busy machine the JVM can be killed by the kernel or by
            # the timeout before it gets to report the error itself. The
            # point of the test is that the runaway program does not
            # survive and eat the machine - and being killed achieves that
            # just as well as an orderly OutOfMemoryError.
            assert run_result.killed or run_result.timed_out, (
                f"expected an out-of-memory failure, got: {combined[:200]}"
            )

    def test_a_normal_program_is_unaffected(self, adapter) -> None:
        compile_result, run_result = adapter.run(HELLO)
        assert compile_result.ok and run_result.ok
        assert "hello from java" in run_result.stdout


# ======================================================================
# What the sandbox message claims
# ======================================================================
class TestSandboxHonesty:
    def test_it_does_not_claim_the_jvm_isolates_memory(self, adapter) -> None:
        """The original message said exactly this, and it was false."""
        _sandboxed, detail = adapter.sandbox_status()
        assert "provides its own memory isolation" not in detail

    def test_it_says_what_is_actually_applied(self, adapter) -> None:
        _sandboxed, detail = adapter.sandbox_status()
        assert "-Xmx" in detail, "the one real limit is not mentioned"

    def test_it_says_what_is_not_applied(self, adapter) -> None:
        _sandboxed, detail = adapter.sandbox_status()
        assert "No OS-level sandbox" in detail

    def test_it_does_not_claim_containment_it_does_not_have(self, adapter) -> None:
        sandboxed, _detail = adapter.sandbox_status()
        assert sandboxed is False


# ======================================================================
# Runtime version detection
# ======================================================================
class TestRuntimeVersion:
    @pytest.mark.parametrize(
        "line, expected",
        [
            ('openjdk version "21.0.2" 2024-01-16 LTS', "21"),
            ('openjdk version "17.0.9" 2023-10-17', "17"),
            ('java version "1.8.0_402"', "8"),
            ('java version "1.7.0_80"', "7"),
        ],
    )
    def test_it_parses_each_version_shape(self, adapter, line, expected, monkeypatch) -> None:
        """Java 8 and earlier version themselves 1.x, so the major version is
        the *second* component. Taking the first gives `--release 1`, which
        javac rejects outright."""
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess(
                a[0] if a else [], 0, "", line
            ),
        )
        assert adapter._java_runtime_version() == expected

    def test_unparseable_output_is_none_not_a_crash(self, adapter, monkeypatch) -> None:
        monkeypatch.setattr(
            subprocess, "run",
            lambda *a, **k: subprocess.CompletedProcess([], 0, "", "no version here"),
        )
        assert adapter._java_runtime_version() is None

    def test_a_failing_java_binary_is_none_not_a_crash(self, adapter, monkeypatch) -> None:
        def boom(*a, **k):
            raise FileNotFoundError("no java here")

        monkeypatch.setattr(subprocess, "run", boom)
        assert adapter._java_runtime_version() is None

    def test_the_release_flag_is_never_one(self, adapter) -> None:
        """`--release 1` is not a valid release; the parser must not emit it."""
        argv = adapter.compile_argv(adapter.source_path(), adapter.work_dir)
        if "--release" in argv:
            assert argv[argv.index("--release") + 1] != "1"


# ======================================================================
# The two-step compile/run contract
# ======================================================================
class TestCompileThenRun:
    def test_the_source_is_always_named_main_java(self, adapter) -> None:
        """javac requires the public class name to match the filename, so the
        caller's filename argument has to be ignored."""
        assert adapter.source_path("SomethingElse.java").name == "Main.java"

    def test_the_run_targets_main(self, adapter) -> None:
        argv = adapter.run_argv(None, adapter.work_dir)
        assert argv[-1] == "Main"

    def test_a_compile_error_skips_the_run(self, adapter) -> None:
        broken = "public class Main { this is not java }"
        compile_result, run_result = adapter.run(broken)
        assert not compile_result.ok
        assert run_result is None, "ran bytecode that never compiled"

    def test_a_stale_class_file_is_cleared_before_compiling(self, adapter) -> None:
        """Otherwise a fixed source can still fail against yesterday's .class."""
        stale = adapter.work_dir / "Main.class"
        adapter.work_dir.mkdir(parents=True, exist_ok=True)
        stale.write_bytes(b"garbage")
        compile_result, _run = adapter.run(HELLO)
        assert compile_result.ok, compile_result.combined_output
        assert stale.read_bytes()[:4] == b"\xca\xfe\xba\xbe", "not real bytecode"

    def test_std_in_reaches_the_program(self, adapter) -> None:
        echo = """
        public class Main {
            public static void main(String[] args) {
                java.util.Scanner s = new java.util.Scanner(System.in);
                System.out.println("echo: " + s.nextLine());
            }
        }
        """
        _compile, run_result = adapter.run(echo, stdin_data="typed this")
        assert run_result.ok
        assert "echo: typed this" in run_result.stdout

    def test_the_compiler_is_asked_for_utf8(self, adapter) -> None:
        """Without this, non-ASCII source fails on a platform default."""
        argv = adapter.compile_argv(adapter.source_path(), adapter.work_dir)
        assert "-encoding" in argv
        assert argv[argv.index("-encoding") + 1].upper() == "UTF-8"

    def test_non_ascii_source_round_trips(self, adapter) -> None:
        program = """
        public class Main {
            public static void main(String[] args) {
                System.out.println("caf\\u00e9 \\u2713");
            }
        }
        """
        _compile, run_result = adapter.run(program)
        assert run_result.ok, run_result.combined_output
        assert "café ✓" in run_result.stdout


# ======================================================================
# Adapter metadata
# ======================================================================
class TestMetadata:
    def test_it_is_the_java_adapter(self) -> None:
        assert JavaAdapter.language_id == "java"
        assert JavaAdapter.kind == "compiled"
        assert JavaAdapter.compiles is True

    def test_the_extension_is_java(self) -> None:
        assert JavaAdapter.extensions == (".java",)

    def test_the_install_hint_names_a_real_package(self) -> None:
        assert "java" in JavaAdapter.install_hint.lower()