"""In-app API key entry, provider detection, and per-request model selection.

Three things are new here, and each has a failure mode worth pinning down:

* Storing a key means it lands on disk. The file must be 0600, must not be the
  settings file, and must never appear in a log or an exception.
* Identifying the provider from a key prefix means guessing who receives a
  credential. Only unambiguous prefixes may be acted on.
* A per-request model must override the configured default without breaking any
  caller that does not pass one.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path

import pytest

from mentorsmith.providers.base import CompletionRequest, ProviderNotConfigured
from mentorsmith.providers.detect import (
    AMBIGUOUS,
    CERTAIN,
    UNKNOWN,
    apply,
    detect_provider,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))


# ======================================================================
# Storing the key
# ======================================================================
class TestSecretStorage:
    @pytest.fixture()
    def cfg(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import importlib

        import mentorsmith.config as module

        return importlib.reload(module)

    def test_round_trips(self, cfg) -> None:
        cfg.save_api_key("sk-or-v1-abc")
        assert cfg.load_api_key() == "sk-or-v1-abc"

    def test_absent_reads_empty(self, cfg) -> None:
        assert cfg.load_api_key() == ""

    def test_the_file_is_owner_only(self, cfg) -> None:
        """The whole point of storing it at all."""
        cfg.save_api_key("secret")
        mode = cfg.secrets_path().stat().st_mode
        assert stat.S_IMODE(mode) == 0o600, oct(mode)

    def test_a_loose_permission_file_is_tightened_on_rewrite(self, cfg) -> None:
        """O_CREAT's mode only applies to a new file; an existing one keeps
        its mode through O_TRUNC. Without the explicit chmod, a file left at
        0644 would stay world-readable forever."""
        cfg.save_api_key("first")
        os.chmod(cfg.secrets_path(), 0o644)
        cfg.save_api_key("second")
        assert stat.S_IMODE(cfg.secrets_path().stat().st_mode) == 0o600

    def test_it_is_a_different_file_from_settings(self, cfg) -> None:
        cfg.save_api_key("secret")
        assert cfg.secrets_path() != cfg.settings_path()
        cfg.save_settings({"provider_base_url": "https://example.test/v1"})
        assert "secret" not in cfg.settings_path().read_text(encoding="utf-8")

    def test_settings_never_contains_a_key_field(self, cfg) -> None:
        """save_settings filters to known keys, so a caller cannot smuggle one
        in even by accident."""
        cfg.save_settings({"api_key": "leaked"})
        assert "leaked" not in cfg.settings_path().read_text(encoding="utf-8")

    def test_saving_empty_removes_the_file(self, cfg) -> None:
        cfg.save_api_key("secret")
        assert cfg.secrets_path().exists()
        cfg.save_api_key("   ")
        assert not cfg.secrets_path().exists()

    def test_clear_reports_whether_it_removed_anything(self, cfg) -> None:
        assert cfg.clear_api_key() is False
        cfg.save_api_key("secret")
        assert cfg.clear_api_key() is True

    def test_whitespace_is_stripped(self, cfg) -> None:
        cfg.save_api_key("  sk-or-v1-abc  ")
        assert cfg.load_api_key() == "sk-or-v1-abc"

    def test_a_corrupt_file_does_not_crash_startup(self, cfg) -> None:
        cfg.secrets_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.secrets_path().write_text("{not json", encoding="utf-8")
        assert cfg.load_api_key() == ""

    def test_a_json_file_of_the_wrong_shape_reads_empty(self, cfg) -> None:
        cfg.secrets_path().parent.mkdir(parents=True, exist_ok=True)
        cfg.secrets_path().write_text(json.dumps(["a", "list"]), encoding="utf-8")
        assert cfg.load_api_key() == ""


# ======================================================================
# Identifying the provider
# ======================================================================
class TestDetection:
    def test_openrouter_is_recognised(self) -> None:
        d = detect_provider("sk-or-v1-1234567890")
        assert d.provider == "OpenRouter"
        assert d.confidence == CERTAIN
        assert d.base_url == "https://openrouter.ai/api/v1"
        assert d.usable

    def test_groq_is_recognised(self) -> None:
        assert detect_provider("gsk_abc").provider == "Groq"

    def test_google_is_recognised(self) -> None:
        assert detect_provider("AIzaSyABC").provider == "Google AI"

    @pytest.mark.parametrize(
        "key", ["sk-abc", "sk-proj-abc", "sk-live-abc", "sk-or-legacy"]
    )
    def test_a_shared_prefix_is_never_guessed(self, key) -> None:
        """``sk-`` is issued by at least four providers. Picking one decides
        which company receives the credential, so it must not be automatic."""
        d = detect_provider(key)
        if d.confidence == CERTAIN:
            # Only sk-or-v1- may be certain, and it does not match these.
            assert d.provider != "", f"{key} was guessed as {d.provider}"
        assert d.base_url == "", "an ambiguous key must not produce a URL"
        assert not d.usable

    def test_ambiguity_names_the_candidates(self) -> None:
        d = detect_provider("sk-proj-abc")
        assert d.confidence == AMBIGUOUS
        assert "OpenAI" in d.candidates
        assert len(d.candidates) > 1

    def test_anthropic_is_flagged_unsupported_not_guessed(self) -> None:
        """It does not speak /v1/chat/completions, so an endpoint would not
        help even if we picked one."""
        d = detect_provider("sk-ant-api03-xyz")
        assert d.unsupported
        assert d.base_url == ""
        assert d.notes, "the user deserves to know why"

    def test_an_unrecognised_key_says_so(self) -> None:
        d = detect_provider("hunter2")
        assert d.confidence == UNKNOWN
        assert d.provider == ""
        assert not d.usable

    def test_an_empty_key_says_so(self) -> None:
        assert detect_provider("").confidence == UNKNOWN
        assert detect_provider("   ").confidence == UNKNOWN

    def test_detection_touches_no_network(self, monkeypatch) -> None:
        """Guessing must never be implemented as 'try the key everywhere'.

        That would hand the same credential to every candidate provider.
        """
        import urllib.request

        def explode(*args, **kwargs):
            raise AssertionError("detection attempted a network call")

        monkeypatch.setattr(urllib.request, "urlopen", explode)
        for key in ("sk-or-v1-x", "sk-proj-x", "sk-ant-x", "AIzaX", "gsk_x", "zzz"):
            detect_provider(key)

    def test_detection_does_not_echo_the_key(self) -> None:
        """The reason string is displayed, so it must not carry the secret."""
        d = detect_provider("sk-or-v1-SUPERSECRET")
        blob = f"{d.provider} {d.reason} {d.base_url} {d.candidates}"
        assert "SUPERSECRET" not in blob

    def test_apply_only_fills_in_for_a_certain_detection(self) -> None:
        assert apply(detect_provider("sk-or-v1-x"))[0] == "https://openrouter.ai/api/v1"
        assert apply(detect_provider("sk-proj-x")) == ("", "")
        assert apply(detect_provider("nope")) == ("", "")

    def test_whitespace_does_not_break_a_detect(self) -> None:
        assert detect_provider("  sk-or-v1-x  ").confidence == CERTAIN


# ======================================================================
# Credential resolution
# ======================================================================
class TestCredentialResolution:
    @pytest.fixture()
    def provider(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import importlib

        import mentorsmith.config as config

        importlib.reload(config)
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        return OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")

    def test_the_stored_key_wins_over_the_environment(self, provider, monkeypatch) -> None:
        import mentorsmith.config as config

        config.save_api_key("sk-stored")
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-from-env")
        assert provider.api_key() == "sk-stored"

    def test_the_environment_still_works(self, provider, monkeypatch) -> None:
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-from-env")
        assert provider.api_key() == "sk-from-env"

    def test_an_explicitly_supplied_key_wins_over_both(self, provider, monkeypatch) -> None:
        import mentorsmith.config as config

        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        config.save_api_key("sk-stored")
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-from-env")
        direct = OpenAICompatibleProvider(
            base_url="https://x.test/v1", model="m", api_key="sk-explicit"
        )
        assert direct.api_key() == "sk-explicit"

    def test_a_newly_saved_key_takes_effect_without_a_restart(self, provider) -> None:
        import mentorsmith.config as config

        assert provider.api_key() == ""
        config.save_api_key("sk-later")
        assert provider.api_key() == "sk-later", "the key must be read per call"

    def test_configured_requires_a_key(self, provider, monkeypatch) -> None:
        assert not provider.configured
        monkeypatch.setenv("MENTORSMITH_API_KEY", "k")
        assert provider.configured

    def test_the_source_is_reported_without_the_key(self, provider, monkeypatch) -> None:
        import mentorsmith.config as config

        config.save_api_key("sk-SECRET")
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-ENV")
        source = provider.credential_source()
        assert "SECRET" not in source and "ENV" not in source
        assert "Settings" in source

    def test_describe_never_contains_the_key(self, provider) -> None:
        import mentorsmith.config as config

        config.save_api_key("sk-SECRET-VALUE")
        assert "SECRET-VALUE" not in provider.describe()

    def test_the_missing_key_error_points_at_both_routes(self, provider) -> None:
        with pytest.raises(ProviderNotConfigured) as excinfo:
            provider.complete(CompletionRequest(system="s", user="u"))
        message = str(excinfo.value)
        assert "Settings" in message
        assert "MENTORSMITH_API_KEY" in message


# ======================================================================
# Per-request model
# ======================================================================
class TestPerRequestModel:
    @pytest.fixture()
    def provider(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-test")
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        return OpenAICompatibleProvider(base_url="https://x.test/v1", model="default-model")

    def _payload(self, provider, **kwargs) -> dict:
        return provider._payload(CompletionRequest(system="s", user="u", **kwargs))

    def test_the_default_is_used_when_none_is_given(self, provider) -> None:
        assert self._payload(provider)["model"] == "default-model"

    def test_a_request_model_overrides_it(self, provider) -> None:
        assert self._payload(provider, model="other-model")["model"] == "other-model"

    def test_an_empty_string_falls_back_to_the_default(self, provider) -> None:
        assert self._payload(provider, model="")["model"] == "default-model"
        assert self._payload(provider, model="   ")["model"] == "default-model"

    def test_the_model_is_trimmed(self, provider) -> None:
        assert self._payload(provider, model="  spaced  ")["model"] == "spaced"

    def test_build_request_passes_the_model_through(self) -> None:
        from mentorsmith.services.tutor import build_request
        from mentorsmith.services.tutor import TutorContext

        ctx = TutorContext(lesson_title="T", section="exercise")
        assert build_request("guided", ctx).model is None
        assert build_request("guided", ctx, "chosen").model == "chosen"
        assert build_request("guided", ctx, "  ").model is None

    def test_the_service_carries_the_model_into_the_request(self) -> None:
        from mentorsmith.services.tutor import TutorContext, TutorService

        sent = {}

        class Recorder:
            configured = True
            model = "default"

            def complete(self, request):
                sent["model"] = request.model
                from mentorsmith.providers.base import CompletionResponse

                return CompletionResponse(text="ok", model="ok")

        service = TutorService(provider=Recorder(), level="guided")
        service.model = "picked-in-the-ui"
        service.ask(TutorContext(lesson_title="T", section="exercise"))
        assert sent["model"] == "picked-in-the-ui"


# ======================================================================
# Listing models
# ======================================================================
class TestListModels:
    @pytest.fixture()
    def provider(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-test")
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        return OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")

    @staticmethod
    def _serve(monkeypatch, body: str):
        import urllib.request

        class FakeResponse:
            def read(self):
                return body.encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(
            urllib.request, "urlopen",
            lambda *a, **k: FakeResponse(),
        )

    def test_it_parses_the_listing(self, provider, monkeypatch) -> None:
        self._serve(monkeypatch, json.dumps({"data": [
            {"id": "b/model", "name": "B"},
            {"id": "a/model", "name": "A"},
        ]}))
        models = provider.list_models()
        assert [m["id"] for m in models] == ["a/model", "b/model"]
        assert models[0]["name"] == "A"

    def test_the_url_gets_v1_appended(self, provider) -> None:
        assert provider._models_url() == "https://x.test/v1/models"

    def test_a_base_url_already_ending_in_v1_is_not_doubled(self) -> None:
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        p = OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")
        assert p._models_url() == "https://x.test/v1/models"

    def test_a_missing_display_name_falls_back_to_the_id(self, provider, monkeypatch) -> None:
        self._serve(monkeypatch, json.dumps({"data": [{"id": "only/id"}]}))
        assert provider.list_models() == [{"id": "only/id", "name": "only/id"}]

    def test_malformed_entries_are_skipped(self, provider, monkeypatch) -> None:
        self._serve(monkeypatch, json.dumps({"data": [
            {"id": "good/model"}, {"id": ""}, {"nope": 1}, "junk", None,
        ]}))
        assert [m["id"] for m in provider.list_models()] == ["good/model"]

    def test_an_unexpected_shape_yields_nothing(self, provider, monkeypatch) -> None:
        self._serve(monkeypatch, json.dumps({"models": ["a"]}))
        assert provider.list_models() == []

    def test_a_network_failure_yields_nothing_rather_than_raising(
        self, provider, monkeypatch
    ) -> None:
        import urllib.error
        import urllib.request

        def boom(*a, **k):
            raise urllib.error.URLError("unreachable")

        monkeypatch.setattr(urllib.request, "urlopen", boom)
        assert provider.list_models() == []

    def test_it_does_nothing_without_a_key(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("MENTORSMITH_API_KEY", raising=False)
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        p = OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")

        import urllib.request

        monkeypatch.setattr(
            urllib.request, "urlopen",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("called anyway")),
        )
        assert p.list_models() == []

    def test_it_respects_the_offline_switch(self, provider, monkeypatch) -> None:
        """Listing models is a network call like any other."""
        monkeypatch.setenv("MENTORSMITH_OFFLINE", "1")
        import urllib.request

        monkeypatch.setattr(
            urllib.request, "urlopen",
            lambda *a, **k: (_ for _ in ()).throw(AssertionError("called anyway")),
        )
        assert provider.list_models() == []

# ======================================================================
# The settings dialog has to be usable
# ======================================================================
class TestSettingsDialogIsReachable:
    """It grew tall enough to run off the bottom of the screen.

    Save and Cancel ended up below the fold with no scroll bar and no way to
    resize, so the only way out was to kill the process. A dialog nobody can
    close is worse than no dialog.
    """

    @pytest.fixture()
    def dialog(self, tmp_path, monkeypatch):
        pytest.importorskip("PyQt6")
        from PyQt6.QtWidgets import QApplication

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        app = QApplication.instance() or QApplication([])
        import importlib

        import mentorsmith.config as config

        importlib.reload(config)
        config.save_settings({})
        from mentorsmith.ui.settings_dialog import SettingsDialog

        widget = SettingsDialog()
        widget.show()
        app.processEvents()
        yield widget, app
        widget.deleteLater()

    def test_it_fits_within_the_available_screen(self, dialog) -> None:
        from PyQt6.QtWidgets import QApplication

        widget, _app = dialog
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        assert widget.height() <= available.height(), (
            f"dialog is {widget.height()}px tall on a {available.height()}px screen"
        )
        assert widget.width() <= available.width()

    def test_it_can_be_resized(self, dialog) -> None:
        widget, _app = dialog
        minimum = widget.minimumSize()
        assert minimum.height() <= 400, (
            f"minimum height {minimum.height()}px forces it off a short screen"
        )
        widget.resize(minimum.width(), minimum.height())
        assert widget.height() == minimum.height()

    def test_the_long_form_is_scrollable(self, dialog) -> None:
        from PyQt6.QtWidgets import QScrollArea

        widget, app = dialog
        area = widget.findChild(QScrollArea)
        assert area is not None, "no scroll area, so the bottom is unreachable"
        assert area.widgetResizable()
        app.processEvents()
        if area.widget().sizeHint().height() > area.viewport().height():
            assert area.verticalScrollBar().maximum() > 0, (
                "content overflows but there is no scroll bar"
            )

    def test_save_and_cancel_are_on_screen_without_scrolling(self, dialog) -> None:
        from PyQt6.QtCore import QPoint
        from PyQt6.QtWidgets import QDialogButtonBox, QPushButton

        widget, _app = dialog
        box = widget.findChild(QDialogButtonBox)
        assert box is not None
        found = {}
        for button in box.findChildren(QPushButton):
            found[button.text().strip()] = button
        assert {"Save", "Cancel"} <= set(found), f"only found {sorted(found)}"
        for name in ("Save", "Cancel"):
            position = found[name].mapTo(widget, QPoint(0, 0))
            assert position.y() + found[name].height() <= widget.height(), (
                f"{name} is below the bottom of the dialog"
            )


# ======================================================================
# The status line must not contradict itself
# ======================================================================
class TestKeyStatusIsLive:
    @pytest.fixture()
    def dialog(self, tmp_path, monkeypatch):
        pytest.importorskip("PyQt6")
        from PyQt6.QtWidgets import QApplication

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.delenv("MENTORSMITH_API_KEY", raising=False)
        app = QApplication.instance() or QApplication([])
        import importlib

        import mentorsmith.config as config

        importlib.reload(config)
        config.save_settings({})
        from mentorsmith.ui.settings_dialog import SettingsDialog

        widget = SettingsDialog()
        yield widget
        widget.deleteLater()

    def _status(self, dialog) -> str:
        return dialog.key_status.text()

    def test_an_empty_field_says_there_is_no_key(self, dialog) -> None:
        assert "No key" in self._status(dialog)

    def test_typing_updates_it_immediately(self, dialog) -> None:
        """It used to be computed only on open, so the dialog showed a red
        "No key." directly above a green "Detected OpenRouter" - two
        contradictory statements about the same field, both on screen."""
        dialog.key_edit.setText("sk-or-v1-abc")
        assert "No key" not in self._status(dialog)

    def test_a_typed_unsaved_key_is_distinguished_from_a_saved_one(
        self, dialog
    ) -> None:
        dialog.key_edit.setText("sk-or-v1-abc")
        assert "not saved" in self._status(dialog)

    def test_a_saved_key_says_so(self, dialog) -> None:
        import mentorsmith.config as config

        config.save_api_key("sk-or-v1-abc")
        dialog._refresh_key_status()
        assert "saved" in self._status(dialog).lower()

    def test_the_environment_is_reported_when_it_is_the_only_source(
        self, dialog, monkeypatch
    ) -> None:
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-env")
        dialog._refresh_key_status()
        assert "MENTORSMITH_API_KEY" in self._status(dialog)

    def test_forgetting_clears_both_the_file_and_the_field(self, dialog) -> None:
        import mentorsmith.config as config

        config.save_api_key("sk-or-v1-abc")
        dialog._on_forget_key()
        assert config.load_api_key() == ""
        assert not config.secrets_path().exists()
        assert dialog.key_edit.text() == ""
        assert "No key" in self._status(dialog)

    def test_clearing_the_field_and_saving_deletes_the_stored_key(
        self, dialog
    ) -> None:
        import mentorsmith.config as config

        dialog.key_edit.setText("sk-or-v1-abc")
        dialog._on_save()
        assert config.load_api_key() == "sk-or-v1-abc"

        dialog.key_edit.setText("")
        dialog._on_save()
        assert config.load_api_key() == ""
        assert not config.secrets_path().exists()


# ======================================================================
# Tests must never touch the real credential
# ======================================================================
class TestTestsCannotReachTheRealKey:
    """A regression guard for a fault that actually happened.

    ``mentorsmith.config`` resolves its data directory from XDG_DATA_HOME,
    which defaults to the real ``~/.local/share/mentorsmith``. Before the
    autouse fixtures in conftest.py redirected it, tests asking for "the
    stored API key" read the user's actual credential, and tests that removed
    MENTORSMITH_API_KEY from the environment still found the stored key and
    concluded the provider was configured.

    The second half is the dangerous half: a test that believed it had no
    credentials could make a real network request carrying a real key.
    """

    def test_the_data_home_is_redirected(self) -> None:
        import os
        import tempfile

        import mentorsmith.config as config

        data = config.data_dir()
        assert str(tempfile.gettempdir()) in str(data) or "/tmp" in str(data), (
            f"tests are using the real data directory: {data}"
        )
        assert os.environ["XDG_DATA_HOME"] != str(Path.home() / ".local" / "share")

    def test_no_key_is_visible_by_default(self) -> None:
        import os

        import mentorsmith.config as config

        assert config.load_api_key() == "", (
            "a test can see a stored API key; the data directory is not isolated"
        )
        assert "MENTORSMITH_API_KEY" not in os.environ

    def test_the_provider_is_not_configured_by_default(self) -> None:
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(
            base_url="https://x.test/v1", model="m"
        )
        assert not provider.configured
        assert provider.api_key() == ""

    def test_a_test_can_still_create_its_own_key(self) -> None:
        """Isolation must not make credential handling untestable."""
        import importlib

        import mentorsmith.config as config

        importlib.reload(config)
        config.save_api_key("sk-made-by-this-test")
        assert config.load_api_key() == "sk-made-by-this-test"
