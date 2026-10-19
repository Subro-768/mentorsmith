"""The self-check has to work through every entry point.

``--check`` used to be implemented only in ``main.py``. The installed command
calls ``mentorsmith.app.main()`` instead, which ignored the flag and launched
the full GUI. With no display that sits in the Qt event loop forever, so the
command produced no report and never returned - indistinguishable, from a
terminal, from a hang.

These tests run the real commands in a subprocess with a timeout. A test that
only imports the function would not have caught it.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _run(command: list[str], timeout: int = 240) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env["XDG_DATA_HOME"] = env.get("XDG_DATA_HOME", "/tmp/opencode/selfcheck-home")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(ROOT),
        env=env,
    )


# ======================================================================
# Both entry points honour the flag
# ======================================================================
class TestSelfCheckFromEveryEntryPoint:
    def test_the_package_main_runs_the_check(self) -> None:
        """This is what the installed `mentorsmith` command calls."""
        result = _run([sys.executable, "-c",
                       "import sys; from mentorsmith.app import main; "
                       "sys.exit(main(['--check']))"])
        assert result.returncode == 0, result.stderr[-2000:]
        assert "Self-check completed" in result.stdout

    def test_main_py_runs_the_check(self) -> None:
        result = _run([sys.executable, "main.py", "--check"])
        assert result.returncode == 0, result.stderr[-2000:]
        assert "Self-check completed" in result.stdout

    def test_the_check_returns_rather_than_blocking(self) -> None:
        """The regression itself.

        A GUI launch that never exits raises TimeoutExpired here instead of
        hanging a test run forever, which is what makes this cheap to keep.
        """
        try:
            result = _run(
                [sys.executable, "-c",
                 "import sys; from mentorsmith.app import main; "
                 "sys.exit(main(['--check']))"],
                timeout=240,
            )
        except subprocess.TimeoutExpired:
            pytest.fail("--check launched the GUI instead of exiting")
        assert result.returncode == 0

    def test_the_check_is_reachable_without_the_dev_script(self) -> None:
        """If somebody moves main.py, the installed command must still work."""
        source = (ROOT / "mentorsmith" / "app.py").read_text(encoding="utf-8")
        assert "wants_self_check" in source, (
            "app.main no longer handles --check, so `mentorsmith --check` "
            "would silently launch the GUI"
        )

    def test_argv_detection_is_exact(self) -> None:
        from mentorsmith.selfcheck import wants_self_check

        assert wants_self_check(["--check"]) is True
        assert wants_self_check(["--other", "--check"]) is True
        assert wants_self_check(None) is False
        assert wants_self_check([]) is False
        assert wants_self_check(["--other"]) is False


# ======================================================================
# What it reports
# ======================================================================
@pytest.fixture(scope="module")
def output() -> str:
    """One self-check run, shared by the assertions below.

    Each run constructs the whole UI, so doing it per test would dominate the
    suite's runtime for no extra coverage.
    """
    return _run([sys.executable, "main.py", "--check"]).stdout


class TestSelfCheckReports:
    def test_it_names_the_app_and_version(self, output: str) -> None:
        assert "MentorSmith" in output

    def test_it_lists_every_language(self, output: str) -> None:
        for language in ("C++", "Python", "Java", "C ", "JavaScript"):
            assert language in output, f"{language} missing from the report"

    def test_it_counts_real_content(self, output: str) -> None:
        """The numbers must come from the data, not be hardcoded."""
        assert "lessons" in output and "exercises" in output
        assert " 0 lessons" not in output, "a language reported no content"

    def test_it_reports_toolchains(self, output: str) -> None:
        assert "toolchains:" in output
        assert "g++" in output or "gcc" in output

    def test_it_is_honest_about_sandboxing(self, output: str) -> None:
        """The containment line must state what is and is not applied."""
        assert "C++ containment:" in output
        line = next(l for l in output.splitlines() if "containment" in l)
        assert "sandbox" in line.lower()

    def test_it_reports_the_page_and_database(self, output: str) -> None:
        assert "pages built" in output
        assert "progress.db" in output


# ======================================================================
# It must not leak a key into its output
# ======================================================================
class TestSelfCheckNeverLeaksCredentials:
    def test_no_key_appears_in_the_report(self, tmp_path, monkeypatch) -> None:
        """A diagnostic command is exactly the kind of thing that gets piped
        into a bug report."""
        env_home = tmp_path / "home"
        env_home.mkdir()
        script = (
            "import sys, os\n"
            "sys.path.insert(0, %r)\n"
            "os.environ['XDG_DATA_HOME'] = %r\n"
            "import mentorsmith.config as c\n"
            "c.save_api_key('sk-or-v1-SUPERSECRET')\n"
            "from mentorsmith.app import main\n"
            "sys.exit(main(['--check']))\n"
        ) % (str(ROOT), str(env_home))

        env = dict(os.environ)
        env["QT_QPA_PLATFORM"] = "offscreen"
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, timeout=240,
            cwd=str(ROOT), env=env,
        )
        assert "SUPERSECRET" not in result.stdout
        assert "SUPERSECRET" not in result.stderr