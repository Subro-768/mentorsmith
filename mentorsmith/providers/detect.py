"""Identify which provider an API key belongs to, from the key alone.

Why this exists: making somebody type a base URL alongside a key is friction
that gets configuration wrong. OpenRouter keys start ``sk-or-v1-``, which is
uniquely theirs, so the common case can be handled without asking.

**Detection never touches the network.** A tempting alternative is to send the
key to each candidate provider and keep the one that answers. That would spray
a single credential across several third parties, and the "loser" that logs the
attempt has now seen a key that was meant for somebody else. Everything here is
string inspection, offline.

**Not every prefix identifies a provider.** ``sk-`` is used by OpenAI,
OpenRouter's legacy keys, Together, DeepSeek, Fireworks and others. Guessing
between them means guessing which company receives the user's credential, so an
ambiguous key is reported as ambiguous and the UI asks - once - instead of
silently picking.

The result therefore carries a confidence:

``certain``
    Exactly one provider can hold a key with this prefix.
``ambiguous``
    The prefix is shared. Several candidates are named; the UI offers them.
``unknown``
    Nothing recognisable. The user is asked, and the app works exactly as
    before.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Base URLs, one per provider. OpenAI-compatible unless noted.
OPENROUTER = "https://openrouter.ai/api/v1"
OPENAI = "https://api.openai.com/v1"
GROQ = "https://api.groq.com/openai/v1"
GOOGLE = "https://generativelanguage.googleapis.com/v1beta/openai"
DEEPSEEK = "https://api.deepseek.com/v1"
TOGETHER = "https://api.together.xyz/v1"

CERTAIN = "certain"
AMBIGUOUS = "ambiguous"
UNKNOWN = "unknown"


@dataclass(frozen=True)
class Detection:
    """What a key looks like, and how sure we are."""

    #: Display name of the detected provider, or "" when unknown.
    provider: str = ""
    #: Base URL to use, or "" when unknown or ambiguous.
    base_url: str = ""
    #: One of ``certain`` / ``ambiguous`` / ``unknown``.
    confidence: str = UNKNOWN
    #: Human-readable explanation, shown in the UI.
    reason: str = ""
    #: Providers this prefix could belong to, when ambiguous.
    candidates: tuple[str, ...] = ()
    #: A model to suggest. Empty when there is nothing safe to suggest.
    suggested_model: str = ""
    #: Set when the provider is not reachable through the OpenAI-compatible
    #: adapter this app uses.
    unsupported: bool = False
    notes: list[str] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """True when this can be applied without asking the user anything."""
        return self.confidence == CERTAIN and bool(self.base_url)


#: Prefixes that only one provider uses. These are safe to act on.
_UNIQUE_PREFIXES: tuple[tuple[str, str, str, str], ...] = (
    # (prefix, provider, base_url, suggested model)
    ("sk-or-v1-", "OpenRouter", OPENROUTER, "openai/gpt-4o-mini"),
    ("gsk_", "Groq", GROQ, "llama-3.3-70b-versatile"),
    ("AIza", "Google AI", GOOGLE, "gemini-2.0-flash"),
)

#: Prefixes shared by more than one provider. Never acted on automatically.
_SHARED_PREFIXES: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "sk-ant-",
        (("Anthropic", ""),),
    ),
    (
        "sk-",
        (
            ("OpenAI", OPENAI),
            ("OpenRouter (legacy key)", OPENROUTER),
            ("DeepSeek", DEEPSEEK),
            ("Together", TOGETHER),
        ),
    ),
)


def detect_provider(key: str) -> Detection:
    """Identify the provider for ``key``.

    Purely local: the key is inspected and nothing is transmitted anywhere.
    """
    token = (key or "").strip()
    if not token:
        return Detection(reason="No key entered yet.")

    for prefix, provider, url, model in _UNIQUE_PREFIXES:
        if token.startswith(prefix):
            return Detection(
                provider=provider,
                base_url=url,
                confidence=CERTAIN,
                reason=(
                    f"Keys starting {prefix!r} are issued only by {provider}, "
                    f"so this is unambiguous."
                ),
                suggested_model=model,
            )

    for prefix, options in _SHARED_PREFIXES:
        if token.startswith(prefix):
            names = tuple(name for name, _ in options)
            if not options or not options[0][1]:
                # Every option lacks a URL, so we cannot act anyway.
                only = options[0][0]
                return Detection(
                    provider=only,
                    confidence=AMBIGUOUS,
                    reason=(
                        f"{only} keys start {prefix!r}, but this app talks to "
                        f"{only} through a different API shape, so it is not "
                        f"usable here as-is."
                    ),
                    candidates=names,
                    unsupported=True,
                    notes=[
                        f"{only} does not serve /v1/chat/completions, which is "
                        f"what this app speaks. An OpenRouter key gives access "
                        f"to the same models and does work.",
                    ],
                )
            return Detection(
                confidence=AMBIGUOUS,
                reason=(
                    f"{len(options)} providers issue keys starting "
                    f"{prefix!r}, so this cannot be resolved without guessing "
                    f"who would receive the credential."
                ),
                candidates=names,
            )

    return Detection(
        confidence=UNKNOWN,
        reason=(
            "This does not start with a prefix any known provider uses, so the "
            "provider cannot be identified from the key."
        ),
    )


def apply(detection: Detection) -> tuple[str, str]:
    """Return ``(base_url, suggested_model)`` to write into settings.

    Empty strings when the detection is not certain: applying a guess would be
    the one behaviour this module exists to prevent.
    """
    if not detection.usable:
        return "", ""
    return detection.base_url, detection.suggested_model