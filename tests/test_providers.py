"""Provider behaviour: configuration, response parsing and failure handling.

No test here touches the network. ``urllib.request.urlopen`` is replaced with
a fake that returns scripted bodies or raises scripted errors.
"""

from __future__ import annotations

import json
import urllib.error

import pytest

from mentorsmith.providers.base import (
    CompletionRequest,
    ProviderAuthError,
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderResponseError,
    ProviderTimeout,
)
from mentorsmith.providers.openai_compat import (
    EchoProvider,
    OpenAICompatibleProvider,
    build_provider,
    network_allowed,
)


def make_payload(content: str = "hello", **extra) -> str:
    """A minimal valid chat-completions body."""
    body = {
        "model": "test-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
    }
    body.update(extra)
    return json.dumps(body)


class FakeResponse:
    """Minimal stand-in for the object ``urlopen`` returns."""

    def __init__(self, body: str) -> None:
        self._body = body.encode("utf-8")

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None


def http_error(code: int, body: str = "", headers: dict | None = None) -> urllib.error.HTTPError:
    """Build an HTTPError with a readable body and headers."""
    return urllib.error.HTTPError(
        url="https://example.invalid/v1/chat/completions",
        code=code,
        msg=f"HTTP {code}",
        hdrs=headers or {},  # type: ignore[arg-type]
        fp=None,
    )


@pytest.fixture()
def provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider(
        base_url="https://example.invalid/v1",
        model="test-model",
        api_key="sk-test-not-a-real-key",
    )


@pytest.fixture()
def prompt_request() -> CompletionRequest:
    return CompletionRequest(system="s", user="u")


# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
def test_unconfigured_provider_is_detected() -> None:
    provider = OpenAICompatibleProvider(base_url="", model="", api_key="")
    assert not provider.configured
    description = provider.describe()
    assert "Not configured" in description


def test_describe_never_leaks_the_key() -> None:
    provider = OpenAICompatibleProvider(
        base_url="https://example.invalid/v1",
        model="m",
        api_key="sk-super-secret-value",
    )
    assert provider.configured
    assert "sk-super-secret-value" not in provider.describe()
    assert "example.invalid" in provider.describe()


def test_describe_names_the_missing_piece() -> None:
    provider = OpenAICompatibleProvider(base_url="", model="m", api_key="k")
    assert "base URL" in provider.describe()


def test_key_is_read_from_the_environment(monkeypatch) -> None:
    monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-from-env")
    provider = OpenAICompatibleProvider(base_url="https://x.invalid/v1", model="m")
    assert provider.api_key() == "sk-from-env"
    assert provider.configured


def test_missing_environment_key_is_not_configured(monkeypatch) -> None:
    monkeypatch.delenv("MENTORSMITH_API_KEY", raising=False)
    provider = OpenAICompatibleProvider(base_url="https://x.invalid/v1", model="m")
    assert not provider.configured
    with pytest.raises(ProviderNotConfigured) as excinfo:
        provider.complete(CompletionRequest(system="s", user="u"))
    assert "MENTORSMITH_API_KEY" in str(excinfo.value)


def test_build_provider_falls_back_to_offline(monkeypatch) -> None:
    monkeypatch.delenv("MENTORSMITH_API_KEY", raising=False)
    provider = build_provider({"provider_base_url": "", "provider_model": ""})
    assert isinstance(provider, EchoProvider)
    assert not provider.configured


def test_build_provider_returns_real_provider_when_set(monkeypatch) -> None:
    monkeypatch.setenv("MENTORSMITH_API_KEY", "sk-test")
    provider = build_provider(
        {"provider_base_url": "https://x.invalid/v1", "provider_model": "m"}
    )
    assert isinstance(provider, OpenAICompatibleProvider)


def test_offline_switch(monkeypatch) -> None:
    monkeypatch.delenv("MENTORSMITH_OFFLINE", raising=False)
    assert network_allowed() is True
    monkeypatch.setenv("MENTORSMITH_OFFLINE", "1")
    assert network_allowed() is False


# ----------------------------------------------------------------------
# Endpoint construction
# ----------------------------------------------------------------------
@pytest.mark.parametrize(
    "base,expected",
    [
        ("https://x.invalid/v1", "https://x.invalid/v1/chat/completions"),
        ("https://x.invalid/v1/", "https://x.invalid/v1/chat/completions"),
        ("https://x.invalid", "https://x.invalid/v1/chat/completions"),
        (
            "https://x.invalid/v1/chat/completions",
            "https://x.invalid/v1/chat/completions",
        ),
    ],
)
def test_endpoint_construction(provider, base, expected) -> None:
    provider.base_url = base
    assert provider._endpoint() == expected


# ----------------------------------------------------------------------
# Successful parsing
# ----------------------------------------------------------------------
def test_successful_request_is_parsed(provider, prompt_request, monkeypatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout=None):
        captured["url"] = req.full_url
        captured["body"] = json.loads(req.data.decode())
        captured["auth"] = req.get_header("Authorization")
        captured["timeout"] = timeout
        return FakeResponse(make_payload("The answer is 42"))

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    response = provider.complete(prompt_request)

    assert response.text == "The answer is 42"
    assert response.model == "test-model"
    assert not response.truncated
    assert captured["url"].endswith("/v1/chat/completions")
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["messages"][0]["role"] == "system"
    assert captured["auth"] == "Bearer sk-test-not-a-real-key"


def test_content_as_parts_is_joined(provider, prompt_request, monkeypatch) -> None:
    payload = json.dumps(
        {
            "model": "m",
            "choices": [
                {"message": {"content": [{"type": "text", "text": "part one "},
                                          {"type": "text", "text": "part two"}]}}
            ],
        }
    )
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(payload))
    assert provider.complete(prompt_request).text == "part one part two"


def test_truncation_is_flagged(provider, prompt_request, monkeypatch) -> None:
    payload = json.dumps(
        {
            "model": "m",
            "choices": [{"message": {"content": "cut"}, "finish_reason": "length"}],
        }
    )
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(payload))
    assert provider.complete(prompt_request).truncated is True


# ----------------------------------------------------------------------
# Malformed responses
# ----------------------------------------------------------------------
def test_non_json_response_is_rejected(provider, prompt_request, monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: FakeResponse("<html>login page</html>")
    )
    with pytest.raises(ProviderResponseError) as excinfo:
        provider.complete(prompt_request)
    assert "not valid JSON" in str(excinfo.value)


def test_empty_choices_are_rejected(provider, prompt_request, monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: FakeResponse(json.dumps({"choices": []})),
    )
    with pytest.raises(ProviderResponseError) as excinfo:
        provider.complete(prompt_request)
    assert "no choices" in str(excinfo.value)


def test_empty_content_is_rejected(provider, prompt_request, monkeypatch) -> None:
    payload = json.dumps({"choices": [{"message": {"content": "   "}}]})
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(payload))
    with pytest.raises(ProviderResponseError):
        provider.complete(prompt_request)


def test_provider_level_error_is_surfaced(provider, prompt_request, monkeypatch) -> None:
    payload = json.dumps({"error": {"message": "model is overloaded"}})
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeResponse(payload))
    with pytest.raises(ProviderResponseError) as excinfo:
        provider.complete(prompt_request)
    assert "model is overloaded" in str(excinfo.value)


# ----------------------------------------------------------------------
# HTTP failures
# ----------------------------------------------------------------------
def test_unauthorised_maps_to_auth_error(provider, prompt_request, monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(http_error(401))
    )
    with pytest.raises(ProviderAuthError) as excinfo:
        provider.complete(prompt_request)
    assert "rejected the API key" in str(excinfo.value)


def test_rate_limit_maps_to_rate_limited(provider, prompt_request, monkeypatch) -> None:
    error = http_error(429, headers={"Retry-After": "30"})
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(error)
    )
    with pytest.raises(ProviderRateLimited) as excinfo:
        provider.complete(prompt_request)
    assert excinfo.value.retry_after == 30.0


def test_server_error_maps_to_network_error(provider, prompt_request, monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(http_error(503))
    )
    with pytest.raises(Exception) as excinfo:
        provider.complete(prompt_request)
    assert "server error" in str(excinfo.value)


def test_not_found_explains_the_base_url(provider, prompt_request, monkeypatch) -> None:
    monkeypatch.setattr(
        "urllib.request.urlopen", lambda *a, **k: (_ for _ in ()).throw(http_error(404))
    )
    with pytest.raises(ProviderResponseError) as excinfo:
        provider.complete(prompt_request)
    assert "base URL" in str(excinfo.value)


def test_timeout_maps_to_timeout_error(provider, prompt_request, monkeypatch) -> None:
    def raise_timeout(*args, **kwargs):
        raise urllib.error.URLError(TimeoutError("timed out"))

    monkeypatch.setattr("urllib.request.urlopen", raise_timeout)
    with pytest.raises(ProviderTimeout):
        provider.complete(prompt_request)


def test_connection_failure_is_a_network_error(provider, prompt_request, monkeypatch) -> None:
    def raise_dns(*args, **kwargs):
        raise urllib.error.URLError("Name or service not known")

    monkeypatch.setattr("urllib.request.urlopen", raise_dns)
    with pytest.raises(Exception) as excinfo:
        provider.complete(prompt_request)
    assert "Could not reach" in str(excinfo.value)


# ----------------------------------------------------------------------
# Secret hygiene
# ----------------------------------------------------------------------
def test_key_never_appears_in_error_messages(provider, prompt_request, monkeypatch) -> None:
    secret = "sk-super-secret-value"
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda *a, **k: (_ for _ in ()).throw(http_error(401, body=f"bad key {secret}")),
    )
    with pytest.raises(ProviderAuthError) as excinfo:
        provider.complete(prompt_request)
    assert secret not in str(excinfo.value)


def test_key_is_never_written_to_the_settings_file(provider) -> None:
    """A guard against a future refactor accidentally persisting the key."""
    import json
    import tempfile
    from pathlib import Path

    from mentorsmith import config

    with tempfile.TemporaryDirectory() as tmp:
        original = config.settings_path
        config.settings_path = lambda: Path(tmp) / "settings.json"
        try:
            config.save_settings({"provider_base_url": "https://x.invalid/v1"})
            written = json.loads((Path(tmp) / "settings.json").read_text())
            assert "sk-super-secret-value" not in json.dumps(written)
            assert "api_key" not in written
        finally:
            config.settings_path = original


def test_echo_provider_explains_how_to_configure() -> None:
    with pytest.raises(ProviderNotConfigured) as excinfo:
        EchoProvider().complete(CompletionRequest(system="s", user="u"))
    message = str(excinfo.value)
    assert "MENTORSMITH_API_KEY" in message
    assert "Settings" in message