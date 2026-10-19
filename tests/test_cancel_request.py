"""Cancelling a tutor request that is still in flight.

Before this, a request to the provider could not be given up on. The only
thing that ended it was the provider answering, so a slow or wedged endpoint
left the learner watching a spinner with no way out.

The implementation has two layers, and both are tested here:

* the provider's connection is closed, which unblocks a read in progress;
* a flag is set, so a reply that still arrives is discarded instead of
  appearing in the transcript as though it had been wanted.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PyQt6")

from mentorsmith.providers.base import (
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
    ProviderError,
    ProviderTimeout,
)
from mentorsmith.services.tutor import TutorContext, TutorService


class SlowProvider(LLMProvider):
    """A provider whose reply arrives only when the test says so."""

    name = "slow"

    def __init__(self, reply: str = "EXPLANATION: done") -> None:
        self.reply = reply
        self.calls = 0
        self.closed = 0

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.calls += 1
        raise ProviderTimeout("never returns in the test")

    def describe(self) -> str:
        return "slow"

    def close_active(self) -> bool:
        self.closed += 1
        return True


class TestWorkerCancellation:
    @pytest.fixture(scope="module")
    def qapp(self):
        from PyQt6.QtWidgets import QApplication

        existing = QApplication.instance()
        app = existing or QApplication([])
        yield app

    def _worker(self, provider):
        from mentorsmith.ui.main_window import TutorWorker

        service = TutorService(provider=provider, level="guided")
        return TutorWorker(service, TutorContext(user_message="hello"))

    def test_a_cancelled_request_never_reaches_the_provider(self, qapp) -> None:
        provider = SlowProvider()
        worker = self._worker(provider)
        worker.cancel()

        results: list[str] = []
        worker.cancelled.connect(lambda: results.append("cancelled"))
        worker.replied.connect(lambda reply: results.append("replied"))
        worker.failed.connect(lambda message: results.append("failed"))

        worker.run()

        assert provider.calls == 0, "a cancelled request was still sent"
        assert results == ["cancelled"]

    def test_cancelling_asks_the_provider_to_stop(self, qapp) -> None:
        provider = SlowProvider()
        worker = self._worker(provider)
        assert worker.cancel() is True
        assert provider.closed == 1

    def test_cancelling_twice_is_harmless(self, qapp) -> None:
        provider = SlowProvider()
        worker = self._worker(provider)
        worker.cancel()
        assert worker.cancel() is False
        assert provider.closed == 1

    def test_a_reply_after_a_cancel_is_discarded(self, qapp) -> None:
        """The reply that arrives after the learner gave up must not appear."""
        provider = SlowProvider()
        worker = self._worker(provider)
        worker.cancel()

        results: list[str] = []
        worker.cancelled.connect(lambda: results.append("cancelled"))
        worker.replied.connect(lambda reply: results.append("replied"))

        # Pretend the request had already been sent and came back late.
        worker.service.provider = provider
        worker.run()

        assert "replied" not in results
        assert "cancelled" in results

    def test_a_failure_after_a_cancel_reads_as_a_cancellation(self, qapp) -> None:
        """Closing the socket makes the read fail; that is not an error."""
        provider = SlowProvider()
        worker = self._worker(provider)

        results: list[str] = []
        worker.cancelled.connect(lambda: results.append("cancelled"))
        worker.failed.connect(lambda message: results.append("failed"))

        # Cancel after the request is in flight, then let the failure arrive.
        original = provider.complete

        def complete_then_cancel(request):
            worker.cancel()
            return original(request)

        provider.complete = complete_then_cancel  # type: ignore[method-assign]
        worker.run()

        assert "failed" not in results
        assert "cancelled" in results

    def test_an_uncancelled_failure_is_still_a_failure(self, qapp) -> None:
        provider = SlowProvider()
        worker = self._worker(provider)
        results: list[str] = []
        worker.failed.connect(lambda message: results.append("failed"))
        worker.cancelled.connect(lambda: results.append("cancelled"))
        worker.run()
        assert results == ["failed"]

    def test_the_flag_is_readable(self, qapp) -> None:
        worker = self._worker(SlowProvider())
        assert worker.cancelled_requested is False
        worker.cancel()
        assert worker.cancelled_requested is True


class TestProviderInterruption:
    def test_nothing_to_close_means_nothing_claimed(self) -> None:
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")
        assert provider.close_active() is False

    def test_an_open_response_is_closed(self) -> None:
        from mentorsmith.providers.openai_compat import OpenAICompatibleProvider

        provider = OpenAICompatibleProvider(base_url="https://x.test/v1", model="m")

        class Response:
            closed = False

            def close(self) -> None:
                self.closed = True

        response = Response()
        provider._active_response = response
        assert provider.close_active() is True
        assert response.closed is True

    def test_the_base_provider_says_it_cannot_interrupt(self) -> None:
        class Provider(LLMProvider):
            name = "p"

            def complete(self, request):
                return CompletionResponse(text="x")

            def describe(self) -> str:
                return "p"

        assert Provider().close_active() is False


class TestTheStopButton:
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

    def test_it_is_disabled_until_a_request_is_running(self, panel) -> None:
        assert panel.cancel_button.isEnabled() is False

    def test_it_is_enabled_while_waiting(self, panel) -> None:
        panel.set_sending(True)
        assert panel.cancel_button.isEnabled() is True
        panel.set_sending(False)
        assert panel.cancel_button.isEnabled() is False

    def test_clicking_it_asks_for_a_cancellation(self, panel) -> None:
        seen: list[bool] = []
        panel.cancel_requested.connect(lambda: seen.append(True))
        panel.set_sending(True)
        panel.cancel_button.click()
        assert seen == [True]

    def test_clicking_it_disables_itself_immediately(self, panel) -> None:
        panel.set_sending(True)
        panel.cancel_button.click()
        assert panel.cancel_button.isEnabled() is False

    def test_the_status_line_says_it_is_stopping(self, panel) -> None:
        panel.set_sending(True)
        panel.cancel_button.click()
        assert "Stopping" in panel.sending_label.text()
