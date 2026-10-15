"""LLM provider abstraction. Credentials come from the environment only."""

from .base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderAuthError,
    ProviderError,
    ProviderNetworkError,
    ProviderNotConfigured,
    ProviderRateLimited,
    ProviderResponseError,
    ProviderTimeout,
)
from .openai_compat import EchoProvider, OpenAICompatibleProvider, build_provider

__all__ = [
    "CompletionRequest",
    "CompletionResponse",
    "LLMProvider",
    "ProviderAuthError",
    "ProviderError",
    "ProviderNetworkError",
    "ProviderNotConfigured",
    "ProviderRateLimited",
    "ProviderResponseError",
    "ProviderTimeout",
    "EchoProvider",
    "OpenAICompatibleProvider",
    "build_provider",
]