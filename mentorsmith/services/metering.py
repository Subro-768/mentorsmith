"""Turn a provider's token counts into something a learner can act on.

Why this is separate from the provider
--------------------------------------
A provider reports *tokens*. Only a price table can turn those into money, and
the table is a snapshot that will go stale. Keeping the two apart means a
wrong price can be corrected without touching request code, and means the app
can still show exact token counts for a model whose price it does not know.

Honesty rules
-------------
* Tokens are exact: they come from the provider's own accounting.
* Money is an **estimate**, always labelled as one, computed from a dated
  table of published list prices.
* A model that is not in the table gets no cost at all - not zero, not a
  guess. ``.cost_usd`` is ``None`` and the UI says "price unknown".
* Nothing here reads or stores a credential or contacts a network.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..providers.base import TokenUsage

#: Prices per **one million tokens**, in US dollars, as published by the
#: vendors on 2026-10-19. List prices change and negotiated prices differ, so
#: this is a guide rather than a bill - and every surface that shows a figure
#: derived from it says "estimate".
PRICE_AS_OF = "2026-10-19"


@dataclass(frozen=True)
class ModelPrice:
    """List price for one model, per million tokens."""

    input_per_million: float
    output_per_million: float
    note: str = ""


#: Keyed by lower-case model id. Both bare ids (``gpt-4o-mini``) and prefixed
#: gateway ids (``openai/gpt-4o-mini``) are matched by
#: :func:`price_for`, which strips the vendor prefix and any ``:variant``
#: suffix before looking up.
PRICES: dict[str, ModelPrice] = {
    # OpenAI
    "gpt-4o-mini": ModelPrice(0.15, 0.60),
    "gpt-4o": ModelPrice(2.50, 10.00),
    "gpt-4.1": ModelPrice(2.00, 8.00),
    "gpt-4.1-mini": ModelPrice(0.40, 1.60),
    "o4-mini": ModelPrice(1.10, 4.40),
    # Anthropic
    "claude-3-5-haiku": ModelPrice(0.80, 4.00),
    "claude-3-5-sonnet": ModelPrice(3.00, 15.00),
    "claude-sonnet-4": ModelPrice(3.00, 15.00),
    # Google
    "gemini-2.0-flash": ModelPrice(0.10, 0.40),
    "gemini-2.5-flash": ModelPrice(0.30, 2.50),
    # Meta / open weights, as commonly hosted
    "llama-3.3-70b-instruct": ModelPrice(0.12, 0.30),
    "deepseek-chat": ModelPrice(0.27, 1.10),
    "deepseek-reasoner": ModelPrice(0.55, 2.19),
}


def _normalise(model: str) -> str:
    """Reduce a gateway id to the part a price table keys on.

    ``openai/gpt-4o-mini`` -> ``gpt-4o-mini``
    ``meta-llama/llama-3.3-70b-instruct:free`` -> ``llama-3.3-70b-instruct``
    """
    name = (model or "").strip().lower()
    if "/" in name:
        name = name.rsplit("/", 1)[-1]
    return name.split(":", 1)[0]


def price_for(model: str) -> ModelPrice | None:
    """Return the list price for a model, or None when unknown."""
    normalised = _normalise(model)
    if not normalised:
        return None
    if normalised in PRICES:
        return PRICES[normalised]
    # Longest-prefix match, so "gpt-4.1-mini-2025-04-14" finds "gpt-4.1-mini"
    # rather than stopping at "gpt-4.1" and overcharging it eightfold.
    candidates = [
        key for key in PRICES
        if normalised.startswith(key) or key.startswith(normalised)
    ]
    if not candidates:
        return None
    return PRICES[max(candidates, key=len)]


def estimate_cost(model: str, usage: TokenUsage | None) -> float | None:
    """Estimated US dollars for one call, or None if the model is unknown."""
    if usage is None:
        return None
    price = price_for(model)
    if price is None:
        return None
    return (
        usage.prompt_tokens * price.input_per_million
        + usage.completion_tokens * price.output_per_million
    ) / 1_000_000.0


def format_tokens(count: int | None) -> str:
    """Group digits so a five-figure token count stays readable."""
    if count is None:
        return "—"
    return f"{count:,}"


def format_cost(usd: float | None) -> str:
    """Format an estimate at a resolution that does not lie about precision.

    A single short exchange costs a fraction of a cent, so two decimal places
    would always show ``$0.00``. Six places keeps a real number visible
    without implying the estimate is exact; anything smaller than that is
    reported as "<$0.000001" rather than rounded to nothing.
    """
    if usd is None:
        return "price unknown"
    if usd == 0:
        return "$0"
    if usd < 0.000001:
        return "<$0.000001"
    if usd < 0.01:
        return f"${usd:.6f}"
    return f"${usd:.4f}"


@dataclass
class UsageMeter:
    """Running totals for one conversation.

    Deliberately per-conversation rather than global: the question a learner
    actually asks is "what has this chat cost me", and a lifetime total that
    survived a restart would answer a question nobody asked while hiding the
    one they did.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    #: Total estimated dollars, or None while every call so far is unpriced.
    cost_usd: float | None = None
    #: Models seen and whether their price was known, for an honest footnote.
    unpriced_models: set[str] = field(default_factory=set)

    def record(self, model: str, usage: TokenUsage | None) -> None:
        """Add one call's accounting. No-op when the provider sent none."""
        if usage is None:
            return
        self.calls += 1
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        cost = estimate_cost(model, usage)
        if cost is None:
            if model:
                self.unpriced_models.add(model)
            return
        self.cost_usd = (self.cost_usd or 0.0) + cost

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def summary(self) -> str:
        """One line for the chat footer. Empty when nothing has been measured."""
        if not self.calls:
            return ""
        parts = [
            f"{format_tokens(self.total_tokens)} tokens",
            f"({format_tokens(self.prompt_tokens)} in / "
            f"{format_tokens(self.completion_tokens)} out)",
            f"≈ {format_cost(self.cost_usd)}",
        ]
        text = "  ".join(parts)
        if self.unpriced_models:
            text += f"  ·  no price for {sorted(self.unpriced_models)[0]}"
        return text

    def tooltip(self) -> str:
        if not self.calls:
            return (
                "Token counts are reported by the provider once a request "
                "completes. Nothing is counted for a request that failed."
            )
        lines = [
            f"{self.calls} request(s) this conversation.",
            "Tokens are exact, as reported by the provider.",
            f"Cost is an estimate using published list prices as of "
            f"{PRICE_AS_OF}; your provider may bill differently.",
        ]
        if self.unpriced_models:
            lines.append(
                "No list price is known for: "
                + ", ".join(sorted(self.unpriced_models))
                + ". Token counts are still exact."
            )
        return "\n".join(lines)

    def reset(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.calls = 0
        self.cost_usd = None
        self.unpriced_models.clear()
