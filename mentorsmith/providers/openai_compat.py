"""An HTTP client for OpenAI-compatible ``/chat/completions`` endpoints.

Many hosted models speak this shape, so one adapter covers a wide range
without hardcoding any particular vendor or model. The base URL, the model
name and the key all come from configuration.

Credentials are read from the environment variable named by
``api_key_env`` (default ``MENTORSMITH_API_KEY``) and are never written to
disk, to the database, or to any log or exception message.

The request is sent with :mod:`urllib` rather than a third-party HTTP client so
the app has no runtime dependency beyond PyQt6.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from ..config import is_truthy
from .base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderAuthError,
    ProviderNetworkError,
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderResponseError,
    ProviderTimeout,
)

#: Never echo more than this much of an error body back to the UI, because
#: some providers quote the submitted prompt (which contains learner code).
MAX_ERROR_BODY_CHARS = 400


def _summarise(body: str) -> str:
    """Condense a provider error body without dumping the whole payload."""
    text = " ".join(body.split())
    if len(text) > MAX_ERROR_BODY_CHARS:
        text = text[:MAX_ERROR_BODY_CHARS] + "..."
    return text


class OpenAICompatibleProvider(LLMProvider):
    """Talks to any endpoint that accepts ``POST /chat/completions``."""

    name = "openai_compatible"

    def __init__(
        self,
        base_url: str,
        model: str,
        *,
        api_key: str | None = None,
        api_key_env: str = "MENTORSMITH_API_KEY",
        timeout: int = 60,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.model = (model or "").strip()
        self._api_key = api_key
        self.api_key_env = api_key_env
        self.timeout = timeout
        self.extra_headers = extra_headers or {}

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @classmethod
    def from_settings(cls, settings: dict) -> "OpenAICompatibleProvider":
        """Build a provider from :func:`mentorsmith.config.load_settings`.

        Reads the key from the environment at call time rather than caching it,
        so exporting a new key takes effect without restarting the app.
        """
        return cls(
            base_url=settings.get("provider_base_url", ""),
            model=settings.get("provider_model", ""),
            timeout=int(settings.get("provider_timeout", 60) or 60),
        )

    def api_key(self) -> str:
        """Resolve the credential, preferring an explicitly supplied one."""
        if self._api_key:
            return self._api_key
        return os.environ.get(self.api_key_env, "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.model and self.api_key())

    def describe(self) -> str:
        """Secret-free summary. The key is never included."""
        if not self.configured:
            missing = []
            if not self.base_url:
                missing.append("base URL")
            if not self.model:
                missing.append("model")
            if not self.api_key():
                missing.append(f"API key (env {self.api_key_env})")
            return "Not configured — missing " + ", ".join(missing)
        return f"{self.base_url} | model {self.model} | key from ${self.api_key_env}"

    # ------------------------------------------------------------------
    # Request
    # ------------------------------------------------------------------
    def _endpoint(self) -> str:
        """Build the chat-completions URL.

        Normalises the trailing slash here as well as in ``__init__``, so a
        ``base_url`` assigned directly after construction still produces a
        correct URL rather than a doubled path segment.
        """
        url = (self.base_url or "").rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if not url.endswith("/v1"):
            url += "/v1"
        return url + "/chat/completions"

    def _payload(self, request: CompletionRequest) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.user},
            ],
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "MentorSmith/0.1",
        }
        key = self.api_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
        # Some gateways require an explicit referrer/origin style header set.
        headers.update(self.extra_headers)
        return headers

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send the request and normalise the reply.

        Raises a specific :class:`~mentorsmith.providers.base.ProviderError`
        subclass for each failure mode so the UI can react appropriately.
        """
        if not self.base_url:
            raise ProviderNotConfigured(
                "No provider base URL set. Open Settings and enter the API endpoint."
            )
        if not self.model:
            raise ProviderNotConfigured(
                "No model selected. Open Settings and enter a model name."
            )
        if not self.api_key():
            raise ProviderNotConfigured(
                f"No API key found. Export {self.api_key_env} and restart the app, "
                "for example:\n\n    export "
                f"{self.api_key_env}=your-key-here"
            )

        # The offline switch is enforced here, at the only place that opens a
        # socket, rather than in a caller. It used to be checked in the UI only,
        # which meant any code path that used the provider directly - including
        # the Phase 5 developer tools - could still make a request while the
        # user believed they were offline. That is exactly the kind of promise
        # that must not be kept by remembering to check in one place.
        if not network_allowed():
            raise ProviderNetworkError(
                "Offline mode is on (MENTORSMITH_OFFLINE=1), so no request was "
                "sent. Lessons, compiling and running, progress and the "
                "developer tools all work without a network; only the AI tutor "
                "needs one."
            )

        body = json.dumps(self._payload(request)).encode("utf-8")
        req = urllib.request.Request(
            self._endpoint(), data=body, headers=self._headers(), method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise self._map_http_error(exc) from None
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise ProviderTimeout(
                    f"The provider did not respond within {self.timeout}s. "
                    "Check your network, or raise the timeout in Settings."
                ) from None
            raise ProviderNetworkError(
                f"Could not reach {self.base_url}: {reason}. "
                "Check the base URL and your network connection."
            ) from None
        except TimeoutError:
            raise ProviderTimeout(
                f"The provider did not respond within {self.timeout}s."
            ) from None

        return self._parse(raw)

    # ------------------------------------------------------------------
    # Error handling and parsing
    # ------------------------------------------------------------------
    def _map_http_error(self, exc: urllib.error.HTTPError) -> Exception:
        """Translate an HTTP status into a typed, actionable error."""
        try:
            detail = exc.read().decode("utf-8", errors="replace")
        except Exception:  # pragma: no cover - defensive
            detail = ""
        summary = _summarise(detail)

        if exc.code in (401, 403):
            return ProviderAuthError(
                f"The provider rejected the API key (HTTP {exc.code}). "
                f"Check that ${self.api_key_env} holds the correct key and is still valid."
                + (f" Provider said: {summary}" if summary else "")
            )
        if exc.code == 429:
            retry_after = None
            header = exc.headers.get("Retry-After") if exc.headers else None
            if header:
                try:
                    retry_after = float(header)
                except ValueError:
                    retry_after = None
            return ProviderRateLimited(
                "The provider is rate limiting or out of quota (HTTP 429). "
                "Wait a moment before retrying."
                + (f" Provider said: {summary}" if summary else ""),
                retry_after=retry_after,
            )
        if exc.code == 404:
            return ProviderResponseError(
                f"Endpoint not found (HTTP 404): {self._endpoint()}. "
                "Check the base URL in Settings — it usually needs to end at the "
                "API root, for example https://example.com/v1."
            )
        if exc.code >= 500:
            return ProviderNetworkError(
                f"The provider reported a server error (HTTP {exc.code}). "
                "This is usually temporary — try again shortly."
            )
        return ProviderResponseError(
            f"The provider returned HTTP {exc.code}."
            + (f" Provider said: {summary}" if summary else "")
        )

    def _parse(self, raw: str) -> CompletionResponse:
        """Extract assistant text from a chat-completions response."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            raise ProviderResponseError(
                "The provider replied with something that is not valid JSON. "
                "This usually means the base URL points at a web page rather "
                "than an API endpoint."
            ) from None

        if not isinstance(data, dict):
            raise ProviderResponseError(
                "The provider returned an unexpected JSON structure."
            )

        # Surface a provider-level error object instead of failing obscurely.
        if "error" in data and isinstance(data["error"], dict):
            message = str(data["error"].get("message", "unknown provider error"))
            raise ProviderResponseError(f"The provider reported an error: {message}")

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ProviderResponseError(
                "The provider returned no choices. The response may have been "
                "filtered or the model may not be available to this key."
            )

        first = choices[0]
        if not isinstance(first, dict):
            raise ProviderResponseError("The provider returned a malformed choice entry.")

        message = first.get("message")
        text = ""
        if isinstance(message, dict):
            content = message.get("content")
            # Some gateways return content as a list of parts.
            if isinstance(content, list):
                text = "".join(
                    part.get("text", "") for part in content if isinstance(part, dict)
                )
            elif isinstance(content, str):
                text = content
        if not text.strip():
            finish = first.get("finish_reason")
            raise ProviderResponseError(
                "The provider returned an empty reply"
                + (f" (finish_reason: {finish})." if finish else ".")
            )

        return CompletionResponse(
            text=text.strip(),
            model=str(data.get("model", self.model)),
            provider=self.name,
            truncated=first.get("finish_reason") == "length",
            raw=data,
        )


class EchoProvider(LLMProvider):
    """Offline stand-in that never calls the network.

    Used by the UI when nothing is configured yet, and by tests, so the app is
    usable and verifiable without spending anything or leaking prompts.
    """

    name = "offline_echo"

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        raise ProviderNotConfigured(
            "No AI provider is configured, so the tutor cannot answer yet.\n\n"
            "Open Settings and provide:\n"
            "  1. an API base URL (ending in /v1 for most providers)\n"
            "  2. a model name\n"
            "  3. an API key in the environment variable MENTORSMITH_API_KEY\n\n"
            "Everything else in MentorSmith — lessons, compiling, running and "
            "progress tracking — works without the AI."
        )

    def describe(self) -> str:
        return "Offline mode — no AI calls are made"

    @property
    def configured(self) -> bool:
        return False


def build_provider(settings: dict):
    """Return the provider described by ``settings``.

    Falls back to :class:`EchoProvider` when nothing usable is configured, so
    the rest of the app never has to handle ``None``.
    """
    base_url = settings.get("provider_base_url", "").strip()
    model = settings.get("provider_model", "").strip()
    if not base_url or not model:
        return EchoProvider()
    return OpenAICompatibleProvider.from_settings(settings)


# Kept so callers can honour a global "no network" preference.
def network_allowed() -> bool:
    """False when ``MENTORSMITH_OFFLINE=1`` forbids outbound AI calls."""
    return not is_truthy(os.environ.get("MENTORSMITH_OFFLINE", ""))


# Re-exported for callers that want timing without importing time themselves.
def monotonic() -> float:
    return time.monotonic()