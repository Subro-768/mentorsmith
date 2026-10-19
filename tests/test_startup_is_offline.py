"""The app must open without touching the network.

It once took 15-20 seconds. The cause was a feature added here: the model
picker calls ``GET /models`` on the provider, and
``MainWindow.__init__`` -> ``_refresh_provider_status`` -> ``set_provider``
reached that fetch for *every* chat panel - twice - synchronously, on the UI
thread, with a 20 second timeout, before the window could be shown.

A regression test is the only thing that reliably keeps a network call off a
startup path, because the call itself looks harmless and works fine.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

import pytest

pytest.importorskip("PyQt6")


@pytest.fixture(scope="module")
def qapp():
    """One QApplication for the module.

    Constructing a widget with no application alive segfaults Qt, and
    constructing a second QApplication segfaults it too, so this is
    module-scoped and reused.
    """
    from PyQt6.QtWidgets import QApplication

    existing = QApplication.instance()
    app = existing or QApplication([])
    yield app


@pytest.fixture()
def no_network(monkeypatch):
    """Record every urlopen instead of performing it."""
    import urllib.request

    calls: list[str] = []
    real = urllib.request.urlopen

    def spy(request, *args, **kwargs):
        url = getattr(request, "full_url", None) or getattr(request, "get_full_url", None)
        calls.append(url() if callable(url) else str(request))
        raise AssertionError(
            f"startup attempted a network call to {calls[-1]}"
        )

    monkeypatch.setattr(urllib.request, "urlopen", spy)
    return calls


_PROBE_SCRIPT = """
import json, os, sys, time, urllib.request
calls = []
real = urllib.request.urlopen
def spy(request, *a, **k):
    url = getattr(request, "full_url", None)
    calls.append(url() if callable(url) else str(request))
    return real(request, *a, **k)
urllib.request.urlopen = spy

from PyQt6.QtWidgets import QApplication
from mentorsmith.app import build_window

started = time.perf_counter()
app = QApplication([])
_app, window = build_window(app)
elapsed = time.perf_counter() - started
print("RESULT" + json.dumps({"calls": calls, "elapsed": elapsed}))
sys.stdout.flush()
# Skip Qt teardown entirely. MainWindow owns QThreads, and letting those be
# destroyed during interpreter shutdown after the QApplication has gone segfaults
# under the offscreen platform. The measurement is already complete.
os._exit(0)
"""


class TestStartupMakesNoNetworkCall:
    def test_building_the_window_stays_offline(self, tmp_path, monkeypatch) -> None:
        """With a *configured* provider, which is what triggered the 15-20s.

        The probe writes a configured provider into its own XDG_DATA_HOME, so
        this exercises the exact path that used to block.
        """
        script = (
            "import mentorsmith.config as c;"
            "c.save_settings({'provider_base_url':'https://openrouter.ai/api/v1',"
            "'provider_model':'openai/gpt-4o-mini'});"
            "c.save_api_key('sk-or-v1-fake')"
        )
        import subprocess
        import sys
        import tempfile
        from pathlib import Path

        home = tempfile.mkdtemp()
        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        env["XDG_DATA_HOME"] = home
        setup = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=300,
        )
        assert setup.returncode == 0, setup.stderr[-500:]

        # Now probe in the same home.
        probe = subprocess.run(
            [sys.executable, "-c", _PROBE_SCRIPT],
            capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=300,
        )
        marker = [l for l in probe.stdout.splitlines() if l.startswith("RESULT")]
        assert marker, f"probe failed:\n{probe.stderr[-800:]}"
        import json

        payload = json.loads(marker[0][len("RESULT"):])
        assert not payload["calls"], (
            f"startup made {len(payload['calls'])} network call(s): "
            f"{payload['calls']}"
        )

    def test_the_model_picker_does_not_fetch_on_being_given_a_provider(self, qapp) -> None:
        """set_provider() is called from the constructor; it must only record."""
        from mentorsmith.ui.chat_panel import ChatPanel

        assert qapp is not None  # a widget cannot exist without an application

        class Provider:
            model = "some/model"

            def __init__(self):
                self.calls = 0

            def list_models(self):
                self.calls += 1
                return [{"id": "a", "name": "A"}]

        panel = ChatPanel()
        try:
            provider = Provider()
            panel.set_provider(provider)
            assert provider.calls == 0, (
                "set_provider fetched models; it runs during MainWindow.__init__ "
                "and a 20s timeout there is a 15-20 second startup"
            )
            assert panel.current_model() == "some/model"
        finally:
            panel.deleteLater()

    def test_the_list_is_fetched_on_demand_instead(self, qapp) -> None:
        from mentorsmith.ui.chat_panel import ChatPanel

        class Provider:
            model = "some/model"

            def __init__(self):
                self.calls = 0

            def list_models(self):
                self.calls += 1
                return [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}]

        panel = ChatPanel()
        try:
            provider = Provider()
            panel.set_provider(provider)
            assert provider.calls == 0
            panel.ensure_models_loaded()
            assert provider.calls == 1
            assert panel.model_combo.count() == 2
        finally:
            panel.deleteLater()


class TestStartupIsFast:
    def test_the_window_appears_quickly(self, tmp_path, monkeypatch) -> None:
        """A generous ceiling, but one a 20-second block cannot meet."""
        import subprocess
        import sys
        import tempfile

        env = dict(os.environ)
        env.setdefault("QT_QPA_PLATFORM", "offscreen")
        env["XDG_DATA_HOME"] = tempfile.mkdtemp()
        probe = subprocess.run(
            [sys.executable, "-c", _PROBE_SCRIPT],
            capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=300,
        )
        marker = [l for l in probe.stdout.splitlines() if l.startswith("RESULT")]
        assert marker, probe.stderr[-800:]
        import json

        payload = json.loads(marker[0][len("RESULT"):])
        assert payload["elapsed"] < 8.0, (
            f"window took {payload['elapsed']:.1f}s to build"
        )


class TestModelListingIsCached:
    def test_the_listing_is_fetched_once_per_provider(self, tmp_path, monkeypatch) -> None:
        """Two chat panels, one request between them."""
        import json
        import urllib.request

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-test")
        import importlib

        import mentorsmith.config as config

        importlib.reload(config)

        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        calls = []

        class Response:
            def read(self):
                return json.dumps({"data": [{"id": "a", "name": "A"}]}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake(*args, **kwargs):
            calls.append(1)
            return Response()

        monkeypatch.setattr(urllib.request, "urlopen", fake)

        provider = OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")
        assert len(provider.list_models()) == 1
        assert len(provider.list_models()) == 1
        assert len(provider.list_models()) == 1
        assert len(calls) == 1, f"{len(calls)} requests for one listing"

    def test_an_endpoint_with_no_listing_is_not_retried_forever(self, tmp_path, monkeypatch) -> None:
        import urllib.request

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-test")
        import importlib

        import mentorsmith.config as config

        importlib.reload(config)
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        calls = []

        class Response:
            def read(self):
                return b'{"models": []}'

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        monkeypatch.setattr(
            urllib.request, "urlopen",
            lambda *a, **k: (calls.append(1), Response())[1],
        )
        provider = OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")
        provider.list_models()
        provider.list_models()
        assert len(calls) == 1, "an empty listing should be cached too"

    def test_the_listing_timeout_is_short(self, tmp_path, monkeypatch) -> None:
        """A dropdown is not worth a generation's worth of waiting.

        Asserted on the value actually passed to urlopen rather than on the
        source text: a test that greps its own source breaks the moment the
        file is edited, which is a good way to make a test cry wolf.
        """
        import json
        import urllib.request

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-test")
        import importlib

        import mentorsmith.config as config

        importlib.reload(config)

        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        seen: list[float] = []

        class Response:
            def read(self):
                return json.dumps({"data": [{"id": "a", "name": "A"}]}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        def fake(url, *args, **kwargs):
            seen.append(kwargs.get("timeout"))
            return Response()

        monkeypatch.setattr(urllib.request, "urlopen", fake)

        provider = OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")
        provider.list_models()
        assert seen, "no request was made"
        assert seen[0] is not None
        assert seen[0] <= 8, f"the model listing timeout is {seen[0]}s"
