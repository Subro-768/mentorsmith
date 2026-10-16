"""Delayed-review outcomes: did a concept hold up when it came back?

Phase 5 asks analytics to show *delayed review results*. A concept marked
`strong` today may be strong only because the answer was three minutes ago. The
interesting question is what happened when it was asked again after a gap.

Two rules shape this module:

* **A gap is required.** A second attempt 30 seconds later is not a delayed
  review; counting it would inflate the result and make the number flattering.
* **Recall is not the same as recognition.** A review on a familiar, already-seen
  exercise mostly tests memory of that exercise. Reviews on an unfamiliar
  exercise test something stronger, so the two are reported separately rather
  than averaged into one flattering figure.

Nothing here reads time spent or chat messages. The unit is a graded attempt,
and nothing else.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

#: Below this, two attempts are effectively the same sitting, not a review.
MIN_REVIEW_GAP_SECONDS = 24 * 60 * 60      # one day

#: Beyond this, the gap is long enough to mean real forgetting-and-recovery.
STRONG_REVIEW_GAP_SECONDS = 7 * 24 * 60 * 60   # one week


class ReviewOutcome(str, Enum):
    """What a delayed review showed."""

    #: Correct with no hints after a real gap: the concept held.
    HELD = "held"

    #: Correct, but only after a hint. Weaker than it looks.
    HELD_WITH_HELP = "held with help"

    #: Wrong after a real gap: the earlier `strong` label overstated it.
    LOST = "lost"

    #: Right answer, familiar exercise. Recall of the worked example, not
    #: transfer.
    RECALL_ONLY = "recall only"


@dataclass
class ReviewEvent:
    """One concept asked again after a gap."""

    concept_id: str
    gap_seconds: float
    correct: bool
    hints_used: int
    #: True when the exercise had not been attempted before.
    novel_exercise: bool
    outcome: ReviewOutcome
    occurred_at: str = ""

    @property
    def gap_days(self) -> float:
        return round(self.gap_seconds / 86_400, 1)

    @property
    def counts_as_strong(self) -> bool:
        """Only an unassisted recall on a *new* exercise proves transfer."""
        return self.outcome is ReviewOutcome.HELD and self.novel_exercise

    def describe(self) -> str:
        return (
            f"{self.concept_id}: {self.outcome.value} after {self.gap_days} days"
            + (" (unfamiliar exercise)" if self.novel_exercise else " (familiar exercise)")
            + (f", {self.hints_used} hint(s)" if self.hints_used else "")
        )


@dataclass
class RetentionSummary:
    """Delayed-review results, with the caveats attached."""

    events: list[ReviewEvent] = field(default_factory=list)
    #: Concepts that were `strong` and have never been re-checked.
    never_rechecked: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.events)

    def counts(self) -> dict[str, int]:
        result = {outcome.value: 0 for outcome in ReviewOutcome}
        for event in self.events:
            result[event.outcome.value] += 1
        return result

    @property
    def held(self) -> int:
        return sum(1 for e in self.events if e.outcome is ReviewOutcome.HELD)

    @property
    def lost(self) -> int:
        return sum(1 for e in self.events if e.outcome is ReviewOutcome.LOST)

    @property
    def transfer_confirmed(self) -> int:
        """Reviews that prove transfer, not recall."""
        return sum(1 for e in self.events if e.counts_as_strong)

    def retention_rate(self) -> float | None:
        """Fraction of delayed reviews that held up, or ``None`` if there are none.

        Returning ``None`` rather than 0.0 matters: "no reviews yet" is not
        "everything was forgotten".
        """
        if not self.events:
            return None
        return self.held / len(self.events)

    def summary(self) -> str:
        if not self.events:
            lines = [
                "No delayed reviews recorded. A concept marked strong has not yet "
                "been asked again after a real gap, so nothing is known yet about "
                "whether it held."
            ]
            if self.never_rechecked:
                lines.append(
                    f"{len(self.never_rechecked)} strong concept(s) have never been "
                    "re-checked: " + ", ".join(self.never_rechecked[:6])
                )
            return " ".join(lines)

        counts = self.counts()
        rate = self.retention_rate()
        lines = [
            f"{self.total} delayed review(s): "
            f"{counts['held']} held, {counts['held with help']} held with help, "
            f"{counts['recall only']} recall only, {counts['lost']} lost.",
            f"Retention: {(rate * 100):.0f}%.",
            (
                f"Only {self.transfer_confirmed} of these used an unfamiliar exercise "
                "with no hints, which is the only combination that demonstrates "
                "transfer rather than recall."
            ),
        ]
        if self.lost:
            lines.append(
                f"{self.lost} concept(s) did not hold up. A 'strong' label is a "
                "summary of past attempts, not a guarantee."
            )
        return " ".join(lines)


def _parse(timestamp: str) -> datetime | None:
    """ISO-8601 to a datetime, tolerating a trailing Z."""
    if not timestamp:
        return None
    text = timestamp.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def analyse_delayed_reviews(
    attempts: list[dict],
    *,
    mastered_concepts: set[str] | None = None,
    min_gap_seconds: int = MIN_REVIEW_GAP_SECONDS,
    now: str | None = None,
) -> RetentionSummary:
    """Find re-attempts after a real gap and judge how they went.

    ``attempts`` are rows with ``id``, ``concept_id``, ``exercise_id``,
    ``created_at``, ``correct``, ``hints_used`` and ``novel``, for one language.
    """
    ordered = sorted(attempts, key=lambda row: _parse(str(row.get("created_at", "")))
                     or datetime.min.replace(tzinfo=timezone.utc))

    # First attempt time per concept, and which exercises have been seen.
    first_seen: dict[str, datetime] = {}
    seen_exercises: dict[str, set[str]] = {}
    summary = RetentionSummary()

    for row in ordered:
        concept_id = str(row.get("concept_id") or "")
        if not concept_id:
            continue
        when = _parse(str(row.get("created_at", "")))
        if when is None:
            continue

        exercise_id = str(row.get("exercise_id") or "")
        if concept_id not in first_seen:
            first_seen[concept_id] = when
            seen_exercises[concept_id] = {exercise_id} if exercise_id else set()
            continue

        gap = (when - first_seen[concept_id]).total_seconds()
        if gap < min_gap_seconds:
            continue      # too soon to count as a delayed review

        novel = bool(row.get("novel")) or exercise_id not in seen_exercises[concept_id]
        if exercise_id:
            seen_exercises[concept_id].add(exercise_id)

        correct = bool(row.get("correct"))
        hints = int(row.get("hints_used") or 0)

        if not correct:
            outcome = ReviewOutcome.LOST
        elif hints > 0:
            outcome = ReviewOutcome.HELD_WITH_HELP
        elif not novel:
            outcome = ReviewOutcome.RECALL_ONLY
        else:
            outcome = ReviewOutcome.HELD

        summary.events.append(
            ReviewEvent(
                concept_id=concept_id,
                gap_seconds=gap,
                correct=correct,
                hints_used=hints,
                novel_exercise=novel,
                outcome=outcome,
                occurred_at=str(row.get("created_at", "")),
            )
        )
        # The clock restarts from the most recent attempt, so a chain of reviews
        # is measured against the last contact rather than the first ever.
        first_seen[concept_id] = when

    if mastered_concepts:
        rechecked = {e.concept_id for e in summary.events}
        summary.never_rechecked = sorted(mastered_concepts - rechecked)

    return summary