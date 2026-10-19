"""The sandbox is on by default wherever bubblewrap is installed.

Feature #4 on the list. Learner code is code the learner did not write, and
running it with the user's own file access means a stray path or a mistaken
`rm` can do real damage. Where bubblewrap is available the default is now
on; where it is not, the setting stays off rather than promising
containment that is not there.

The user's own choice is remembered - the default only applies to a setting
that has never been set.
"""

from __future__ import annotations

import importlib

import pytest


@pytest.fixture()
def fresh_config(tmp_path, monkeypatch):
    """A config module whose data directory is a throwaway one."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    import mentorsmith.config as config

    importlib.reload(config)
    return config


class TestTheDefault:
    def test_it_is_on_when_bubblewrap_is_installed(
        self, fresh_config, monkeypatch
    ) -> None:
        monkeypatch.setattr(fresh_config.shutil, "which", lambda name: "/usr/bin/bwrap")
        fresh_config.sandbox_available.cache_clear()
        assert fresh_config.default_settings()["sandbox_enabled"] is True

    def test_it_is_off_when_bubblewrap_is_missing(
        self, fresh_config, monkeypatch
    ) -> None:
        monkeypatch.setattr(fresh_config.shutil, "which", lambda name: None)
        fresh_config.sandbox_available.cache_clear()
        assert fresh_config.default_settings()["sandbox_enabled"] is False

    def test_it_looks_for_the_right_binary(self, fresh_config, monkeypatch) -> None:
        seen: list[str] = []

        def which(name: str):
            seen.append(name)
            return "/usr/bin/bwrap" if name == "bwrap" else None

        monkeypatch.setattr(fresh_config.shutil, "which", which)
        fresh_config.sandbox_available.cache_clear()
        fresh_config.sandbox_available()
        assert seen == ["bwrap"]


class TestTheUsersChoiceWins:
    def test_a_setting_the_user_turned_off_stays_off(
        self, fresh_config, monkeypatch
    ) -> None:
        monkeypatch.setattr(fresh_config.shutil, "which", lambda name: "/usr/bin/bwrap")
        fresh_config.sandbox_available.cache_clear()

        fresh_config.save_settings({"sandbox_enabled": False})
        settings = fresh_config.load_settings()
        assert settings["sandbox_enabled"] is False

    def test_a_setting_the_user_turned_on_stays_on(
        self, fresh_config, monkeypatch
    ) -> None:
        monkeypatch.setattr(fresh_config.shutil, "which", lambda name: None)
        fresh_config.sandbox_available.cache_clear()

        fresh_config.save_settings({"sandbox_enabled": True})
        settings = fresh_config.load_settings()
        assert settings["sandbox_enabled"] is True

    def test_a_settings_file_with_no_sandbox_key_takes_the_default(
        self, fresh_config, monkeypatch
    ) -> None:
        """A partial file must not silently switch the sandbox off."""
        monkeypatch.setattr(fresh_config.shutil, "which", lambda name: "/usr/bin/bwrap")
        fresh_config.sandbox_available.cache_clear()

        fresh_config.save_settings({"theme": "light"})
        settings = fresh_config.load_settings()
        assert settings["sandbox_enabled"] is True
        assert settings["theme"] == "light"


class TestTheStatusIsHonest:
    """The app must never claim isolation it does not have."""

    def test_it_says_off_when_off(self, tmp_path) -> None:
        from mentorsmith.execution.cpp import CppAdapter

        adapter = CppAdapter(tmp_path, sandbox=False)
        active, message = adapter.sandbox_status()
        assert active is False
        assert "OFF" in message
        assert "ACTIVE" not in message

    def test_it_says_requested_but_missing_when_bwrap_is_absent(
        self, tmp_path, monkeypatch
    ) -> None:
        import shutil

        from mentorsmith.execution.cpp import CppAdapter

        monkeypatch.setattr(shutil, "which", lambda name: None)
        adapter = CppAdapter(tmp_path, sandbox=True)
        active, message = adapter.sandbox_status()
        assert active is False
        assert "REQUESTED" in message
        assert "NOT active" in message

    def test_it_says_active_when_it_is(self, tmp_path) -> None:
        import shutil

        from mentorsmith.execution.cpp import CppAdapter

        if shutil.which("bwrap") is None:
            pytest.skip("bubblewrap is not installed here")
        adapter = CppAdapter(tmp_path, sandbox=True)
        active, message = adapter.sandbox_status()
        assert active is True
        assert "ACTIVE" in message


class TestTheSandboxActuallyContains:
    """A default that does not contain anything is worse than no default."""

    def test_a_write_outside_the_sandbox_does_not_reach_the_host(
        self, tmp_path
    ) -> None:
        import shutil

        from mentorsmith.execution.cpp import CppAdapter

        if shutil.which("bwrap") is None:
            pytest.skip("bubblewrap is not installed here")
        if not shutil.which("g++"):
            pytest.skip("no C++ compiler here")

        target = tmp_path / "escaped.txt"
        source = (
            "#include <fstream>\n"
            "#include <iostream>\n"
            "int main(){\n"
            f'  std::ofstream f("{target}");\n'
            '  f << "x";\n'
            '  std::cout << (f.good() ? "wrote" : "blocked") << "\\n";\n'
            "}\n"
        )
        adapter = CppAdapter(tmp_path / "work", sandbox=True)
        _build, run = adapter.run(source)
        assert run is not None
        assert run.exit_code == 0
        assert not target.exists(), (
            "the sandboxed program wrote to the host filesystem"
        )
