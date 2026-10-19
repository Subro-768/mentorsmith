"""Token and cost metering.

The provider never read the ``usage`` object from a reply, so a request's
size and cost were invisible. A learner with a metered key has no way of
finding out what a session costs, which is a real problem, not a nicety.

Two rules drive the design, and the tests below hold the implementation to
them:

* **Tokens are exact.** They come from the provider's own accounting, never
  from counting characters locally.
* **Money is an estimate, and only where it can be computed.** A model that is
  not in the price table gets *no* figure - not zero, not a guess.
"""

from __future__ import annotations

import pytest

from mentorsmith.providers.base import (
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)
from mentorsmith.services.metering import (
    PRICES,
    PRICE_AS_OF,
    UsageMeter,
    estimate_cost,
    format_cost,
    format_tokens,
    price_for,
)


class TestTokenUsageParsing:
    def test_it_reads_the_standard_fields(self) -> None:
        usage = TokenUsage.from_payload(
            {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165}
        )
        assert usage is not None
        assert usage.prompt_tokens == 120
        assert usage.completion_tokens == 45
        assert usage.total_tokens == 165

    def test_it_reads_the_gateway_names(self) -> None:
        """Some gateways call them input_tokens and output_tokens."""
        usage = TokenUsage.from_payload({"input_tokens": 7, "output_tokens": 3})
        assert usage is not None
        assert usage.prompt_tokens == 7
        assert usage.completion_tokens == 3
        assert usage.total_tokens == 10

    def test_it_derives_a_missing_total(self) -> None:
        usage = TokenUsage.from_payload({"prompt_tokens": 10, "completion_tokens": 5})
        assert usage is not None
        assert usage.total_tokens == 15

    def test_a_missing_usage_block_means_no_usage(self) -> None:
        assert TokenUsage.from_payload(None) is None
        assert TokenUsage.from_payload({}) is None
        assert TokenUsage.from_payload("nonsense") is None

    def test_an_all_zero_block_means_no_usage(self) -> None:
        """A provider that reports zeros has told us nothing."""
        assert TokenUsage.from_payload(
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        ) is None

    def test_string_numbers_are_tolerated(self) -> None:
        usage = TokenUsage.from_payload({"prompt_tokens": "12", "completion_tokens": "3"})
        assert usage is not None
        assert usage.prompt_tokens == 12

    def test_negative_numbers_are_clamped(self) -> None:
        usage = TokenUsage.from_payload({"prompt_tokens": -5, "completion_tokens": 2})
        assert usage is not None
        assert usage.prompt_tokens == 0
        assert usage.total_tokens == 2

    def test_booleans_are_not_numbers(self) -> None:
        """True is an int in Python; treating it as a count would be silly."""
        usage = TokenUsage.from_payload({"prompt_tokens": True, "completion_tokens": 4})
        assert usage is not None
        assert usage.prompt_tokens == 0
        assert usage.completion_tokens == 4


class TestProviderReportsUsage:
    def test_the_openai_compatible_provider_passes_usage_through(self) -> None:
        import json
        import urllib.request

        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        class Response:
            def read(self) -> bytes:
                return json.dumps({
                    "model": "gpt-4o-mini",
                    "choices": [{"message": {"content": "hello"}}],
                    "usage": {
                        "prompt_tokens": 30,
                        "completion_tokens": 12,
                        "total_tokens": 42,
                    },
                }).encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        monkey = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: Response()
        try:
            provider = OpenAICompatibleProvider(
                base_url="https://x.test/v1", model="gpt-4o-mini"
            )
            provider._api_key = "sk-test"
            reply = provider.complete(CompletionRequest(system="s", user="u"))
        finally:
            urllib.request.urlopen = monkey

        assert reply.usage is not None
        assert reply.usage.total_tokens == 42

    def test_a_reply_without_usage_still_works(self) -> None:
        import json
        import urllib.request

        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        class Response:
            def read(self) -> bytes:
                return json.dumps({
                    "model": "m",
                    "choices": [{"message": {"content": "hi"}}],
                }).encode()

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        monkey = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: Response()
        try:
            provider = OpenAICompatibleProvider(
                base_url="https://x.test/v1", model="m"
            )
            provider._api_key = "sk-test"
            reply = provider.complete(CompletionRequest(system="s", user="u"))
        finally:
            urllib.request.urlopen = monkey

        assert reply.text == "hi"
        assert reply.usage is None


class TestPriceLookup:
    def test_a_bare_id_is_found(self) -> None:
        assert price_for("gpt-4o-mini") is not None

    def test_a_prefixed_gateway_id_is_found(self) -> None:
        assert price_for("openai/gpt-4o-mini") is not None

    def test_a_variant_suffix_is_ignored(self) -> None:
        price = price_for("meta-llama/llama-3.3-70b-instruct:free")
        assert price is not None
        assert price == PRICES["llama-3.3-70b-instruct"]

    def test_a_dated_model_finds_its_family(self) -> None:
        price = price_for("gpt-4.1-mini-2025-04-14")
        assert price is not None
        assert price == PRICES["gpt-4.1-mini"]

    def test_the_longest_family_wins(self) -> None:
        """gpt-4.1-mini must not be priced as gpt-4.1."""
        assert price_for("gpt-4.1-mini") == PRICES["gpt-4.1-mini"]
        assert price_for("gpt-4.1") == PRICES["gpt-4.1"]

    def test_an_unknown_model_has_no_price(self) -> None:
        assert price_for("some-model-nobody-has-priced") is None

    def test_an_empty_model_has_no_price(self) -> None:
        assert price_for("") is None
        assert price_for("   ") is None

    def test_every_price_is_non_negative(self) -> None:
        for name, price in PRICES.items():
            assert price.input_per_million >= 0, name
            assert price.output_per_million >= 0, name

    def test_the_table_states_when_it_was_read(self) -> None:
        assert PRICE_AS_OF


class TestCostEstimate:
    def test_a_known_model_costs_something(self) -> None:
        usage = TokenUsage(prompt_tokens=1_000_000, completion_tokens=0)
        cost = estimate_cost("gpt-4o-mini", usage)
        assert cost == pytest.approx(0.15)

    def test_output_is_priced_separately(self) -> None:
        usage = TokenUsage(prompt_tokens=0, completion_tokens=1_000_000)
        cost = estimate_cost("gpt-4o-mini", usage)
        assert cost == pytest.approx(0.60)

    def test_an_unknown_model_has_no_cost(self) -> None:
        usage = TokenUsage(prompt_tokens=1000, completion_tokens=1000)
        assert estimate_cost("unpriced-model", usage) is None

    def test_no_usage_has_no_cost(self) -> None:
        assert estimate_cost("gpt-4o-mini", None) is None

    def test_a_zero_call_costs_nothing(self) -> None:
        assert estimate_cost("gpt-4o-mini", TokenUsage()) == 0.0


class TestFormatting:
    def test_tokens_are_grouped(self) -> None:
        assert format_tokens(1234567) == "1,234,567"

    def test_no_tokens_shows_a_dash(self) -> None:
        assert format_tokens(None) == "—"

    def test_an_unknown_price_says_so(self) -> None:
        assert "unknown" in format_cost(None).lower()

    def test_a_sub_cent_cost_is_not_rounded_away(self) -> None:
        """A short exchange costs fractions of a cent; $0.00 would be a lie."""
        text = format_cost(0.00012)
        assert text != "$0.00"
        assert text.startswith("$0.0001")

    def test_a_tiny_cost_does_not_claim_zero(self) -> None:
        assert format_cost(0.0000001).startswith("<$")

    def test_zero_is_zero(self) -> None:
        assert format_cost(0) == "$0"


class TestUsageMeter:
    def test_a_fresh_meter_says_nothing(self) -> None:
        meter = UsageMeter()
        assert meter.summary() == ""
        assert meter.calls == 0

    def test_it_accumulates_tokens(self) -> None:
        meter = UsageMeter()
        meter.record("gpt-4o-mini", TokenUsage(100, 50))
        meter.record("gpt-4o-mini", TokenUsage(200, 25))
        assert meter.prompt_tokens == 300
        assert meter.completion_tokens == 75
        assert meter.total_tokens == 375
        assert meter.calls == 2

    def test_it_accumulates_cost(self) -> None:
        meter = UsageMeter()
        meter.record("gpt-4o-mini", TokenUsage(1_000_000, 1_000_000))
        assert meter.cost_usd == pytest.approx(0.75)

    def test_an_unpriced_model_contributes_tokens_but_not_money(self) -> None:
        meter = UsageMeter()
        meter.record("mystery-model", TokenUsage(100, 100))
        assert meter.total_tokens == 200
        assert meter.cost_usd is None
        assert "mystery-model" in meter.unpriced_models

    def test_a_priced_call_after_an_unpriced_one_still_reports_cost(self) -> None:
        meter = UsageMeter()
        meter.record("mystery-model", TokenUsage(100, 100))
        meter.record("gpt-4o-mini", TokenUsage(1_000_000, 0))
        assert meter.cost_usd == pytest.approx(0.15)

    def test_a_reply_without_usage_is_not_counted(self) -> None:
        meter = UsageMeter()
        meter.record("gpt-4o-mini", None)
        assert meter.calls == 0
        assert meter.summary() == ""

    def test_the_summary_names_the_tokens_and_the_estimate(self) -> None:
        meter = UsageMeter()
        meter.record("gpt-4o-mini", TokenUsage(1200, 340))
        summary = meter.summary()
        assert "1,540" in summary
        assert "≈" in summary, "the cost must be marked as an estimate"

    def test_the_summary_flags_an_unpriced_model(self) -> None:
        meter = UsageMeter()
        meter.record("mystery-model", TokenUsage(10, 10))
        assert "no price" in meter.summary()

    def test_the_tooltip_explains_what_is_exact(self) -> None:
        meter = UsageMeter()
        meter.record("gpt-4o-mini", TokenUsage(10, 10))
        tip = meter.tooltip()
        assert "exact" in tip.lower()
        assert "estimate" in tip.lower()
        assert PRICE_AS_OF in tip

    def test_the_tooltip_explains_an_empty_meter(self) -> None:
        tip = UsageMeter().tooltip()
        assert tip

    def test_reset_clears_everything(self) -> None:
        meter = UsageMeter()
        meter.record("gpt-4o-mini", TokenUsage(10, 10))
        meter.reset()
        assert meter.calls == 0
        assert meter.total_tokens == 0
        assert meter.cost_usd is None
        assert meter.unpriced_models == set()
        assert meter.summary() == ""


class TestTutorServiceRecordsUsage:
    def test_the_service_keeps_the_last_usage(self) -> None:
        from mentorsmith.providers.base import LLMProvider
        from mentorsmith.services.tutor import TutorContext, TutorService

        class Provider(LLMProvider):
            name = "test"

            def complete(self, request):
                return CompletionResponse(
                    text="EXPLANATION: ok",
                    model="gpt-4o-mini",
                    usage=TokenUsage(11, 22),
                )

            def describe(self) -> str:
                return "test"

        service = TutorService(provider=Provider())
        service.ask(TutorContext(user_message="hi"))
        assert service.last_usage is not None
        assert service.last_usage.total_tokens == 33
        assert service.last_model == "gpt-4o-mini"

    def test_a_provider_that_reports_nothing_leaves_it_none(self) -> None:
        from mentorsmith.providers.base import LLMProvider
        from mentorsmith.services.tutor import TutorContext, TutorService

        class Provider(LLMProvider):
            name = "test"

            def complete(self, request):
                return CompletionResponse(text="EXPLANATION: ok", model="m")

            def describe(self) -> str:
                return "test"

        service = TutorService(provider=Provider())
        service.ask(TutorContext(user_message="hi"))
        assert service.last_usage is None


class TestTheMeterIsVisible:
    """A number nobody can see is not a feature."""

    @pytest.fixture(scope="module")
    def qapp(self):
        from PyQt6.QtWidgets import QApplication

        existing = QApplication.instance()
        app = existing or QApplication([])
        yield app

    @pytest.fixture()
    def panel(self, qapp):
        from mentorsmith.ui.chat_panel import ChatPanel

        widget = ChatPanel()
        yield widget
        widget.deleteLater()

    def test_nothing_is_shown_before_a_request(self, panel) -> None:
        assert panel.usage_label.isVisibleTo(panel) is False
        assert panel.usage_label.text() == ""

    def test_a_completed_request_shows_the_totals(self, panel) -> None:
        panel.record_usage("gpt-4o-mini", TokenUsage(1200, 340))
        assert panel.usage_label.text()
        assert "1,540" in panel.usage_label.text()
        assert panel.usage_label.isVisibleTo(panel) is True

    def test_the_hover_text_explains_the_estimate(self, panel) -> None:
        panel.record_usage("gpt-4o-mini", TokenUsage(1200, 340))
        tip = panel.usage_label.toolTip()
        assert "estimate" in tip.lower()
        assert "exact" in tip.lower()

    def test_clearing_the_chat_resets_the_meter(self, panel) -> None:
        panel.record_usage("gpt-4o-mini", TokenUsage(1200, 340))
        panel.clear_transcript()
        assert panel.usage_meter.calls == 0
        assert panel.usage_label.isVisibleTo(panel) is False

    def test_an_unpriced_model_still_shows_tokens(self, panel) -> None:
        panel.record_usage("mystery-model", TokenUsage(500, 500))
        text = panel.usage_label.text()
        assert "1,000" in text
        assert "no price" in text
