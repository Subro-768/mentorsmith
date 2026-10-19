"""A small abstraction over LLM providers.

Only one method matters to the rest of the app:

    provider.complete(CompletionRequest(...)) -> CompletionResponse

Everything provider-specific (endpoint shape, auth header, error mapping) lives
behind that boundary, so swapping vendors does not touch the tutor service.

No provider is hardcoded and no model is assumed. The user must supply a base
URL and a model name, and the key is read from an environment variable. This
module never logs or stores credentials.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class ProviderError(RuntimeError):
    """Base class for every provider failure.

    The UI shows ``str(error)`` directly, so messages should be understandable
    on their own and must never contain an API key.
    """

    #: Short machine-readable label used for grouping in logs and tests.
    kind = "provider_error"


class ProviderNotConfigured(ProviderError):
    """No base URL, model or API key has been supplied."""

    kind = "not_configured"


class ProviderTimeout(ProviderError):
    """The provider did not respond within the configured time."""

    kind = "timeout"


class ProviderRateLimited(ProviderError):
    """The provider rejected the request due to quota or rate limiting."""

    kind = "rate_limited"

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ProviderAuthError(ProviderError):
    """The API key was missing, rejected or expired."""

    kind = "auth"


class ProviderNetworkError(ProviderError):
    """DNS, connection or TLS failure reaching the provider."""

    kind = "network"


class ProviderResponseError(ProviderError):
    """The provider replied with something unusable or malformed."""

    kind = "malformed_response"


@dataclass
class CompletionRequest:
    """One request to the tutor model.

    ``model`` overrides the provider's configured default for this one request.
    It is optional: leaving it None means "use whatever Settings says", which
    keeps every existing caller working unchanged while letting the UI let
    somebody switch model mid-conversation.
    """

    system: str
    user: str
    max_tokens: int = 1200
    temperature: float = 0.4
    model: str | None = None


@dataclass
class CompletionResponse:
    """A successful reply."""

    text: str
    model: str = ""
    provider: str = ""
    #: Whether the provider flagged the reply as truncated.
    truncated: bool = False
    raw: dict = field(default_factory=dict)


class LLMProvider(ABC):
    """Interface implemented by every provider."""

    #: Short identifier shown in the UI.
    name: str = "provider"

    @abstractmethod
    def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Return the model's reply, or raise a :class:`ProviderError`."""

    @abstractmethod
    def describe(self) -> str:
        """One-line, secret-free summary for the settings screen."""

    @property
    def configured(self) -> bool:
        """Whether this provider has everything it needs to make a call."""
        return True