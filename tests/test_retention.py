"""Delayed-review analytics, plus a regression test for the output-cap bug.

The memory test at the bottom is the important one: it failed by taking down a
16 GB machine during development, and it must never do so again.
"""

from __future__ import annotations

import resource
import tempfile
from pathlib import Path

import pytest

from mentorsmith.services.retention import (
    MIN_REVIEW_GAP_SECONDS,
    ReviewOutcome,
    analyse_delayed_reviews,
)


def row(**kwargs) -> dict:
    """One attempt row, with sensible defaults."""
    base = {
        "id": 0,
        "concept_id": "pointers",
        "exercise_id": "e1",
        "created_at": "2026-01-01T00:00:00+00:00",
        "correct": True,
        "hints_used": 0,
        "novel": False,
    }
    base.update(kwargs)
    return base


DAY = 24 * 60 * 60


class TestNoReviews:
    def test_nothing_attempted_means_nothing_known(self) -> None:
        summary = analyse_delayed_reviews([])
        assert summary.total == 0
        assert summary.retention_rate() is None, (
            "no reviews must be None, not 0.0 - they are different claims"
        )
        assert "nothing is known yet" in summary.summary()

    def test_strong_concepts_never_rechecked_are_named(self) -> None:
        summary = analyse_delayed_reviews(
            [row(correct=True)], mastered_concepts={"pointers", "arrays"}
        )
        assert summary.never_rechecked == ["arrays", "pointers"]
        assert "never been re-checked" in summary.summary()

    def test_a_concept_that_was_rechecked_is_not_listed(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(created_at="2026-01-01T00:00:00+00:00"),
                row(
                    created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2",
                    novel=True,
                ),
            ],
            mastered_concepts={"pointers"},
        )
        assert summary.never_rechecked == []


class TestGapRequirement:
    def test_a_second_attempt_the_same_day_is_not_a_review(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(created_at="2026-01-01T00:00:00+00:00"),
                row(created_at="2026-01-01T00:00:30+00:00"),
            ]
        )
        assert summary.total == 0, "30 seconds later is not a delayed review"

    def test_a_review_after_a_real_gap_counts(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(created_at="2026-01-01T00:00:00+00:00"),
                row(
                    created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2",
                    novel=True,
                ),
            ]
        )
        assert summary.total == 1
        assert summary.events[0].gap_days == 4.0

    def test_the_gap_threshold_is_configurable(self) -> None:
        attempts = [
            row(created_at="2026-01-01T00:00:00+00:00"),
            row(created_at="2026-01-01T00:01:00+00:00", exercise_id="e2"),
        ]
        assert analyse_delayed_reviews(attempts).total == 0
        assert analyse_delayed_reviews(attempts, min_gap_seconds=30).total == 1

    def test_attempts_out_of_order_are_sorted_first(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(created_at="2026-01-05T00:00:00+00:00", exercise_id="e2"),
                row(created_at="2026-01-01T00:00:00+00:00"),
            ]
        )
        assert summary.total == 1


class TestOutcomes:
    def test_correct_and_unfamiliar_after_a_gap_held(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2", novel=True),
            ]
        )
        assert summary.events[0].outcome is ReviewOutcome.HELD
        assert summary.events[0].counts_as_strong

    def test_correct_but_needing_a_hint_is_weaker(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2", novel=True, hints_used=2),
            ]
        )
        assert summary.events[0].outcome is ReviewOutcome.HELD_WITH_HELP
        assert not summary.events[0].counts_as_strong

    def test_a_familiar_exercise_is_recall_not_transfer(self) -> None:
        """Getting the same question right again mostly tests memory of it."""
        summary = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00", exercise_id="e1"),
            ]
        )
        assert summary.events[0].outcome is ReviewOutcome.RECALL_ONLY
        assert not summary.events[0].counts_as_strong

    def test_wrong_after_a_gap_is_lost(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2", novel=True, correct=False),
            ]
        )
        assert summary.events[0].outcome is ReviewOutcome.LOST
        assert summary.lost == 1

    def test_transfer_needs_an_unfamiliar_exercise_and_no_hints(self) -> None:
        strong = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2", novel=True),
            ]
        )
        assert strong.transfer_confirmed == 1


class TestSummary:
    def test_no_reviews_never_claims_a_retention_rate(self) -> None:
        summary = analyse_delayed_reviews([])
        assert summary.retention_rate() is None
        assert "%" not in summary.summary()

    def test_a_lost_concept_is_called_out(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2", novel=True, correct=False),
            ]
        )
        assert "did not hold up" in summary.summary()

    def test_counts_cover_every_outcome(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2", novel=True),
            ]
        )
        counts = summary.counts()
        assert set(counts) == {o.value for o in ReviewOutcome}
        assert counts["held"] == 1

    def test_recall_is_reported_separately_from_transfer(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00", exercise_id="e1"),
            ]
        )
        assert "Only 0 of these used an unfamiliar exercise" in summary.summary()

    def test_events_describe_themselves_with_the_gap(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(),
                row(created_at="2026-01-05T00:00:00+00:00",
                    exercise_id="e2", novel=True),
            ]
        )
        text = summary.events[0].describe()
        assert "after 4.0 days" in text
        assert "unfamiliar exercise" in text


class TestRobustness:
    def test_rows_with_no_timestamp_are_ignored_not_fatal(self) -> None:
        summary = analyse_delayed_reviews([row(created_at="")])
        assert summary.total == 0

    def test_an_unparseable_timestamp_is_skipped(self) -> None:
        summary = analyse_delayed_reviews([row(created_at="not a date")])
        assert summary.total == 0

    def test_a_trailing_z_is_accepted(self) -> None:
        summary = analyse_delayed_reviews(
            [
                row(created_at="2026-01-01T00:00:00Z"),
                row(created_at="2026-01-05T00:00:00Z", exercise_id="e2", novel=True),
            ]
        )
        assert summary.total == 1

    def test_rows_without_a_concept_are_skipped(self) -> None:
        summary = analyse_delayed_reviews([row(concept_id="")])
        assert summary.total == 0


# ======================================================================
# Regression: bounded output reading
# ======================================================================
class TestOutputIsBoundedWhileReading:
    """A runaway printer must not be able to exhaust the host's memory.

    This is not hypothetical. `ProcessHandle.wait()` used to call
    `communicate()`, which buffered the child's entire output before any
    truncation. A program printing in a loop reached 13 GB and the kernel
    OOM-killed the whole session. The cap is now applied while reading.
    """

    def test_runaway_output_does_not_exhaust_memory(self, tmp_path: Path) -> None:
        from mentorsmith.execution import adapter
        from mentorsmith.execution.base import MAX_OUTPUT_CHARS

        before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

        instance = adapter("python", tmp_path / "work", sandbox=False)
        instance.run_timeout = 2
        _build, result = instance.run("while True:\n    print('x' * 1000)\n")

        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        growth_mb = (peak - before) / 1024

        assert len(result.stdout) <= MAX_OUTPUT_CHARS + 1_000, "output was not capped"
        # Generous, but the old behaviour grew by orders of magnitude more.
        assert growth_mb < 200, f"parent grew {growth_mb:.0f} MB reading child output"

    def test_the_learner_is_told_output_was_dropped(self, tmp_path: Path) -> None:
        from mentorsmith.execution import adapter

        instance = adapter("python", tmp_path / "work", sandbox=False)
        instance.run_timeout = 2
        _build, result = instance.run("while True:\n    print('x' * 1000)\n")
        assert "discarded" in result.stdout, (
            "silent truncation hides that the program produced more"
        )

    def test_the_notice_survives_truncation(self, tmp_path: Path) -> None:
        """The notice is prepended, because `truncate()` clips the tail."""
        from mentorsmith.execution import adapter

        instance = adapter("python", tmp_path / "work", sandbox=False)
        instance.run_timeout = 2
        _build, result = instance.run("while True:\n    print('x' * 1000)\n")
        assert result.stdout.startswith("[")

    def test_stderr_is_capped_too(self, tmp_path: Path) -> None:
        from mentorsmith.execution import adapter
        from mentorsmith.execution.base import MAX_OUTPUT_CHARS

        instance = adapter("python", tmp_path / "work", sandbox=False)
        instance.run_timeout = 2
        source = "import sys\nwhile True:\n    sys.stderr.write('y' * 1000)\n"
        _build, result = instance.run(source)
        assert len(result.stderr) <= MAX_OUTPUT_CHARS + 1_000

    def test_small_output_gets_no_spurious_notice(self, tmp_path: Path) -> None:
        from mentorsmith.execution import adapter

        instance = adapter("python", tmp_path / "work", sandbox=False)
        _build, result = instance.run("print('hello')\n")
        assert result.stdout == "hello\n"
        assert "discarded" not in result.stdout

    def test_ordinary_output_is_still_complete(self, tmp_path: Path) -> None:
        from mentorsmith.execution import adapter

        instance = adapter("python", tmp_path / "work", sandbox=False)
        _build, result = instance.run(
            "for i in range(2000):\n    print(i)\n"
        )
        assert result.stdout.count("\n") == 2000

    def test_exit_code_and_stderr_are_unaffected(self, tmp_path: Path) -> None:
        from mentorsmith.execution import adapter

        instance = adapter("python", tmp_path / "work", sandbox=False)
        _build, result = instance.run(
            "import sys\nsys.stderr.write('boom\\n')\nsys.exit(3)\n"
        )
        assert result.exit_code == 3
        assert not result.ok
        assert "boom" in result.stderr

    def test_timeout_still_reported(self, tmp_path: Path) -> None:
        from mentorsmith.execution import adapter

        instance = adapter("python", tmp_path / "work", sandbox=False)
        instance.run_timeout = 2
        _build, result = instance.run("import time\ntime.sleep(30)\n")
        assert result.timed_out
        assert "runtime limit" in result.error