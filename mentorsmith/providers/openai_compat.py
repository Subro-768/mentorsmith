"""An HTTP client for OpenAI-compatible ``/chat/completions`` endpoints.

Many hosted models speak this shape, so one adapter covers a wide range
without hardcoding any particular vendor or model. The base URL, the model
name and the key all come from configuration.

Credentials are resolved by :meth:`OpenAICompatibleProvider.api_key`: a key
entered in Settings (stored ``0600``, outside settings.json) takes precedence
over the ``api_key_env`` environment variable, which is still honoured. A key
is never written to the database, to a log, or into an exception message -
``describe()`` reports only *where* the key came from, never the key.

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

from ..config import is_truthy, load_api_key, secrets_path
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
    TokenUsage,
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
        #: Memoised ``/models`` listing. None means "not fetched yet"; an empty
        #: list is a real answer from an endpoint that publishes no listing,
        #: and is cached too so the picker does not retry on every focus.
        self._models_cache: list[dict[str, str]] | None = None
        #: The response currently being read, so it can be closed to cancel.
        self._active_response = None

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    @classmethod
    def from_settings(cls, settings: dict) -> "OpenAICompatibleProvider":
        """Build a provider from the settings dictionary.

        Reads the key from the environment at call time rather than caching it,
        so exporting a new key takes effect without restarting the app.
        """
        return cls(
            base_url=settings.get("provider_base_url", ""),
            model=settings.get("provider_model", ""),
            timeout=int(settings.get("provider_timeout", 60) or 60),
        )

    def api_key(self) -> str:
        """Resolve the credential.

        Precedence, highest first:

        1. a key passed explicitly to the constructor (tests, one-off use);
        2. the key typed into Settings, stored ``0600`` outside settings.json;
        3. the ``MENTORSMITH_API_KEY`` environment variable.

        The environment remains a working fallback so existing command-line
        setups keep functioning, and so a user who prefers not to have a key on
        disk still can. Read fresh on every call, so setting or replacing a key
        takes effect without restarting the app.
        """
        if self._api_key:
            return self._api_key
        stored = load_api_key()
        if stored:
            return stored
        return os.environ.get(self.api_key_env, "").strip()

    def credential_source(self) -> str:
        """Where the key came from, for display. Never includes the key."""
        if self._api_key:
            return "supplied directly"
        if load_api_key():
            return f"Settings (stored in {secrets_path().name})"
        if os.environ.get(self.api_key_env, "").strip():
            return f"${self.api_key_env}"
        return "none"

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
        return (
            f"{self.base_url} | model {self.model} "
            f"| key from {self.credential_source()}"
        )

    # ------------------------------------------------------------------
    # Model discovery
    # ------------------------------------------------------------------
    def _models_url(self) -> str:
        """URL of the ``/models`` listing.

        Mirrors :meth:`_endpoint`: whatever the user typed as a base URL, with
        ``/v1`` appended if they left it off.
        """
        url = (self.base_url or "").rstrip("/")
        if url.endswith("/models"):
            return url
        if not url.endswith("/v1"):
            url += "/v1"
        return url + "/models"

    def list_models(self) -> list[dict[str, str]]:
        """Return ``[{"id", "name"}, ...]`` from ``GET /models``.

        Fetches from the configured endpoint rather than shipping a hardcoded
        list, because a hardcoded one goes stale silently and is exactly how
        the two apps drifted apart on colour.

        Returns ``[]`` on any failure. A model picker is a convenience; failing
        to reach the endpoint must not stop somebody typing a model name by
        hand, and must not surface a raw HTTP error over a UI that is otherwise
        working.
        """
        if not self.base_url or not self.api_key():
            return []
        if not network_allowed():
            return []

        # Cached per provider instance so the several chat panels in the app
        # cost one request between them rather than one each.
        if self._models_cache is not None:
            return self._models_cache

        request = urllib.request.Request(
            self._models_url(),
            headers=self._headers(),
            method="GET",
        )
        try:
            # Short on purpose. A listing is a nicety; nobody should wait a
            # generation's worth of timeout for a dropdown.
            with urllib.request.urlopen(request, timeout=8) as resp:
                payload = json.loads(resp.read().decode("utf-8", "replace"))
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            return []

        entries = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            # Cache the empty result too, so an endpoint that does not publish a
            # listing is not re-fetched every time the picker gains focus.
            self._models_cache = []
            return self._models_cache

        models = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            identifier = entry.get("id")
            if not isinstance(identifier, str) or not identifier.strip():
                continue
            label = entry.get("name")
            models.append({
                "id": identifier.strip(),
                # Fall back to the id when the endpoint sends no display name.
                "name": label.strip() if isinstance(label, str) and label.strip()
                else identifier.strip(),
            })
        models.sort(key=lambda m: m["name"].lower())
        self._models_cache = models
        return self._models_cache

    def close_active(self) -> bool:
        """Close the connection of a request that is still in flight.

        Returns True when there was one to close. Closing the response makes
        a blocked body read fail on the other thread, which is what actually
        stops the request; the caller then discards whatever comes back.
        """
        response = self._active_response
        if response is None:
            return False
        try:
            response.close()
        except Exception:  # pragma: no cover - defensive
            return False
        return True

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
            # A per-request model wins over the configured default, so the
            # model picker can switch mid-conversation.
            #
            # Strip *before* falling back, not after: a model box containing
            # only whitespace is truthy, so `(a or b).strip()` would send an
            # empty model and the endpoint would reject it with something
            # unhelpful. Selecting all and typing a space is an easy thing to
            # do in an editable combo box.
            "model": (request.model or "").strip() or self.model.strip(),
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
                "No API key found.\n\n"
                "Either paste one into Settings, which stores it in "
                f"{secrets_path().name} with owner-only permissions, or keep it "
                "out of the app entirely and export it in the shell:\n\n"
                f"    export {self.api_key_env}=your-key-here"
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
                # Kept so a cancel can close the connection and unblock the
                # read below. Without this a request that has already been
                # sent cannot be stopped at all.
                self._active_response = response
                try:
                    raw = response.read().decode("utf-8", errors="replace")
                finally:
                    self._active_response = None
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
            usage=TokenUsage.from_payload(data.get("usage")),
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