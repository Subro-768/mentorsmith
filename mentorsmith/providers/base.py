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


@dataclass(frozen=True)
class TokenUsage:
    """How much of the model's context a request consumed.

    Providers report this in a ``usage`` object and it is the only honest
    source for what a call cost - counting characters locally would be a guess
    dressed up as a number, and would be wrong for every tokeniser but one.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self) -> None:
        """Derive the total when it was not supplied.

        A record built by hand with only the two halves should still total
        correctly, rather than quietly reporting that the call cost nothing.
        """
        if not self.total_tokens:
            total = self.prompt_tokens + self.completion_tokens
            if total:
                object.__setattr__(self, "total_tokens", total)

    @classmethod
    def from_payload(cls, payload: object) -> "TokenUsage | None":
        """Build from a provider's ``usage`` object, or None if absent.

        Tolerant on purpose: gateways differ over whether fields are ints,
        strings, or missing entirely, and a reply is not worth discarding over
        its accounting.
        """
        if not isinstance(payload, dict):
            return None

        def as_int(*names: str) -> int:
            for name in names:
                value = payload.get(name)
                if isinstance(value, bool):
                    continue
                if isinstance(value, int):
                    return max(0, value)
                if isinstance(value, str) and value.strip().isdigit():
                    return max(0, int(value.strip()))
            return 0

        prompt = as_int("prompt_tokens", "input_tokens")
        completion = as_int("completion_tokens", "output_tokens")
        total = as_int("total_tokens")
        if not total:
            total = prompt + completion
        if not (prompt or completion or total):
            return None
        return cls(prompt_tokens=prompt, completion_tokens=completion,
                   total_tokens=total)


@dataclass
class CompletionResponse:
    """A successful reply."""

    text: str
    model: str = ""
    provider: str = ""
    #: Whether the provider flagged the reply as truncated.
    truncated: bool = False
    #: Token accounting, when the provider reported it.
    usage: TokenUsage | None = None
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

    def close_active(self) -> bool:
        """Interrupt a request in flight, if this provider can.

        Returns True when a request was actually interrupted. The default is
        False: a provider that cannot be interrupted says so rather than
        pretending. The reply from an interrupted request, if it arrives at
        all, is discarded by the caller.
        """
        return False

    @property
    def configured(self) -> bool:
        """Whether this provider has everything it needs to make a call."""
        return True