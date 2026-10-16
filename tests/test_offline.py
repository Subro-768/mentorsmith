"""Phase 5 §6: what works offline, and the promise that offline is honoured.

Two things are checked here.

**The promise.** ``MENTORSMITH_OFFLINE=1`` used to be enforced in the UI only,
so any code path that used the provider directly could still open a socket while
the user believed they were offline. The gate now lives in ``complete()``, the
only place that sends anything, and a test asserts no request is attempted.

**The behaviour.** Everything except the tutor's AI must keep working with no
network. The tests below do not merely assert "no exception"; several of them
compile and run real programs with the socket layer disabled.
"""

from __future__ import annotations

import os
import socket
import tempfile
from pathlib import Path

import pytest

from mentorsmith.providers.base import (
    CompletionRequest,
    ProviderError,
    ProviderNetworkError,
    ProviderNotConfigured,
)
from mentorsmith.providers.openai_compat import (
    EchoProvider,
    OpenAICompatibleProvider,
    build_provider,
    network_allowed,
)

# Note: from_settings does not read an api_key_env setting; the credential
# always comes from the environment, at call time. Getting this wrong is what
# the first version of this test did.
FULL_SETTINGS = {
    "provider_base_url": "https://example.invalid/v1",
    "provider_model": "some-model",
}


@pytest.fixture()
def offline(monkeypatch):
    monkeypatch.setenv("MENTORSMITH_OFFLINE", "1")
    monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-not-a-real-key")
    yield


@pytest.fixture()
def online(monkeypatch):
    monkeypatch.delenv("MENTORSMITH_OFFLINE", raising=False)
    monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-not-a-real-key")
    yield


# ======================================================================
# The offline promise
# ======================================================================
class TestOfflineIsEnforcedAtTheSource:
    def test_the_flag_is_read(self, offline) -> None:
        assert network_allowed() is False

    def test_no_flag_means_allowed(self, online) -> None:
        assert network_allowed() is True

    @pytest.mark.parametrize(
        "value,expected", [("1", False), ("true", False), ("yes", False),
                           ("0", True), ("", True), ("false", True)]
    )
    def test_truthy_values_are_respected(self, monkeypatch, value, expected) -> None:
        monkeypatch.setenv("MENTORSMITH_OFFLINE", value)
        assert network_allowed() is expected

    def test_a_configured_provider_refuses_while_offline(self, offline) -> None:
        """The regression: this used to be checked in the UI only."""
        provider = build_provider(FULL_SETTINGS)
        assert isinstance(provider, OpenAICompatibleProvider)
        with pytest.raises(ProviderNetworkError) as excinfo:
            provider.complete(CompletionRequest(system="s", user="u"))
        assert "MENTORSMITH_OFFLINE" in str(excinfo.value)

    def test_no_socket_is_opened_while_offline(self, offline, monkeypatch) -> None:
        """Belt and braces: even a direct urlopen must not be reached."""

        def explode(*args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("a network call was attempted while offline")

        monkeypatch.setattr("urllib.request.urlopen", explode)
        provider = build_provider(FULL_SETTINGS)
        with pytest.raises(ProviderError):
            provider.complete(CompletionRequest(system="s", user="u"))

    def test_the_refusal_explains_what_still_works(self, offline) -> None:
        provider = build_provider(FULL_SETTINGS)
        with pytest.raises(ProviderNetworkError) as excinfo:
            provider.complete(CompletionRequest(system="s", user="u"))
        message = str(excinfo.value)
        assert "Lessons" in message, "say what is still available"

    def test_the_echo_provider_refuses_without_touching_the_network(
        self, online, monkeypatch
    ) -> None:
        """It is a null object: it raises ProviderNotConfigured, and never dials out."""

        def explode(*args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("EchoProvider attempted a network call")

        monkeypatch.setattr("urllib.request.urlopen", explode)
        with pytest.raises(ProviderNotConfigured) as excinfo:
            EchoProvider().complete(CompletionRequest(system="s", user="u"))
        # The message has to tell the learner what still works.
        assert "works without the AI" in str(excinfo.value)

    def test_nothing_configured_is_not_a_network_error(self, monkeypatch) -> None:
        """A missing key is a configuration problem, not a connectivity one."""
        monkeypatch.setenv("MENTORSMITH_OFFLINE", "1")
        monkeypatch.delenv("MENTORSMITH_API_KEY", raising=False)
        provider = OpenAICompatibleProvider.from_settings(FULL_SETTINGS)
        with pytest.raises(ProviderNotConfigured):
            provider.complete(CompletionRequest(system="s", user="u"))

    def test_offline_does_not_prevent_building_a_provider(self, offline) -> None:
        """Construction is fine; only sending is refused."""
        provider = build_provider(FULL_SETTINGS)
        assert provider is not None


# ======================================================================
# What actually works offline
# ======================================================================
class TestExecutionWorksOffline:
    """Real compilers and interpreters, with sockets disabled entirely."""

    @pytest.fixture()
    def no_network(self, monkeypatch):
        def refuse(*args, **kwargs):  # pragma: no cover - must never run
            raise AssertionError("something tried to open a socket")

        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)
        yield

    @pytest.mark.parametrize(
        "language,source",
        [
            ("cpp", '#include <iostream>\nint main(){std::cout<<"ok\\n";return 0;}\n'),
            ("python", 'print("ok")\n'),
            ("c", '#include <stdio.h>\nint main(void){printf("ok\\n");return 0;}\n'),
            ("javascript", 'console.log("ok");\n'),
        ],
    )
    def test_every_language_runs_with_no_socket(
        self, no_network, language, source, tmp_path: Path
    ) -> None:
        from mentorsmith.execution import adapter, detect

        if not detect(language).available:
            pytest.skip(f"{language} toolchain not installed")
        instance = adapter(language, tmp_path / language, sandbox=False)
        _build, result = instance.run(source)
        assert result is not None and result.ok, result.stderr if result else ""
        assert result.stdout.strip() == "ok"

    def test_lessons_load_with_no_network(self, no_network) -> None:
        from mentorsmith.core.curriculum_registry import load_track

        for language in ("cpp", "python", "c", "javascript"):
            track = load_track(language)
            assert track.lessons
            assert track.bank is not None and track.bank.exercises

    def test_the_dashboard_builds_with_no_network(self, no_network, offline) -> None:
        from mentorsmith.core import curriculum_registry as registry
        from mentorsmith.core.db import Database
        from mentorsmith.services.insights import build_report

        database = Database(os.path.join(tempfile.mkdtemp(), "offline.db"))
        database.connect()
        track = registry.load_track("cpp")
        database.record_exercise_attempt(
            "01-program-structure", "e1", concept_id="program-structure",
            language="cpp", correct=True, hints_used=0,
        )
        report = build_report(database, track.model, track.bank, language="cpp")
        assert report.total_attempts == 1
        assert report.summary_line()

    def test_the_developer_audit_runs_with_no_network(
        self, no_network, offline
    ) -> None:
        """The audit's checks are local; none of them needs a socket."""
        from mentorsmith.services.security_audit import (
            check_language_isolation,
            check_no_shell_execution,
            check_stale_binary_removed,
        )

        assert check_no_shell_execution().status.value == "passed"
        assert check_stale_binary_removed().status.value in ("passed", "skipped")
        assert check_language_isolation().status.value == "passed"

    def test_git_inspection_works_with_no_network(self, no_network, tmp_path) -> None:
        """Read-only git must not need a remote."""
        import subprocess

        from mentorsmith.services.git_tools import GitRepository

        root = tmp_path / "repo"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True)
        repo = GitRepository(root)
        assert repo.exists()
        assert repo.status() == []
        assert repo.log() == []


# ======================================================================
# The documentation must match
# ======================================================================
class TestDocumentationMatchesBehaviour:
    """§6 says to explain which features need a network. Check the claim."""

    @pytest.fixture()
    def readme(self) -> str:
        return (
            Path(__file__).resolve().parent.parent / "README.md"
        ).read_text(encoding="utf-8")

    def test_the_readme_says_offline_is_not_ai(self, readme) -> None:
        lowered = readme.lower()
        assert "offline" in lowered
        # It must not claim the AI works offline.
        assert "no offline model" in lowered or "not work" in lowered

    def test_the_readme_lists_the_runtime_dependency_truthfully(self, readme) -> None:
        assert "pyqt6 only" in readme.lower()

    def test_the_provider_enforces_offline_in_its_own_source(self) -> None:
        """The gate must live at the socket, not only in a caller."""
        source = (
            Path(__file__).resolve().parent.parent
            / "mentorsmith" / "providers" / "openai_compat.py"
        )
        text = source.read_text(encoding="utf-8")
        body = text.split("def network_allowed")[0]
        assert "network_allowed()" in body, (
            "complete() must consult the offline flag itself"
        )