"""Which concepts to review, and an honest account of why.

**No scheduling method guarantees mastery.** That is stated in the module
docstring and repeated in the data the UI shows, because a review queue that
claims to guarantee mastery would be lying.

What this module does is narrow and defensible: it looks at recorded evidence
and names concepts worth revisiting, giving a reason for each one. The reasons
are derived from counts the learner can verify themselves — how many attempts
were wrong, whether a specific error kept recurring, how long ago they last
practised, and whether a later review attempt disagreed with the earlier one.

The "disagreement" signal is the closest thing here to delayed-performance
evidence: a concept that was right during practice and wrong again on a later
review suggests the earlier success was recall rather than understanding.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .concepts import ConceptModel
from .mastery import MasteryAssessment, is_review_attempt

#: A concept practised within this many days is not overdue for review.
DUE_AFTER_DAYS = 10

#: Attempts must reach this before "not practised recently" can be claimed.
MIN_ATTEMPTS_FOR_STALENESS = 1

#: Human-facing disclaimer attached to every review list.
DISCLAIMER = (
    "Review suggestions come from your own recorded attempts. No review "
    "schedule can guarantee that a concept is mastered — only a new, "
    "unfamiliar problem can show whether it transferred."
)


@dataclass
class ReviewItem:
    """One concept flagged for review, with its justification."""

    concept_id: str
    title: str
    reason: str
    evidence: list[str] = field(default_factory=list)
    urgency: float = 0.0

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "title": self.title,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "urgency": round(self.urgency, 3),
        }


def _parse(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def days_since(timestamp: str | None) -> float | None:
    parsed = _parse(timestamp)
    if parsed is None:
        return None
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0)


def recommend_reviews(
    model: ConceptModel,
    assessments: dict[str, MasteryAssessment],
    *,
    last_attempt_at: dict[str, str] | None = None,
    review_regressions: dict[str, int] | None = None,
    limit: int = 5,
) -> list[ReviewItem]:
    """Rank concepts for review, most urgent first.

    ``review_regressions`` maps a concept to how many review attempts were
    wrong after the concept had already been solved once. That is the
    delayed-performance signal described in the module docstring.
    """
    last_attempt_at = last_attempt_at or {}
    review_regressions = review_regressions or {}
    items: list[ReviewItem] = []

    for concept_id, assessment in assessments.items():
        concept = model.get(concept_id)
        title = concept.title if concept else concept_id
        metrics = assessment.metrics
        attempts = int(metrics.get("attempts", 0))
        if attempts == 0:
            continue

        evidence: list[str] = []
        urgency = 0.0
        reason_parts: list[str] = []

        categories = metrics.get("error_categories", {}) or {}
        repeated = {k: v for k, v in categories.items() if v >= 2}
        if repeated:
            worst = max(repeated.items(), key=lambda kv: kv[1])
            reason_parts.append(
                f"'{worst[0]}' has come up {worst[1]} times across your attempts"
            )
            evidence.append(f"Recurring error category: {worst[0]} x{worst[1]}")
            urgency += 3.0 + worst[1]

        if assessment.label == "needs_review":
            correct = int(metrics.get("correct", 0))
            reason_parts.append(
                f"only {correct} of {attempts} graded attempts were correct"
            )
            evidence.append(f"{correct}/{attempts} graded attempts correct")
            urgency += 4.0

        if not metrics.get("first_attempt_correct"):
            reason_parts.append("the first attempt was wrong")
            evidence.append("First attempt was incorrect")
            urgency += 1.0

        hints = int(metrics.get("hints_used", 0))
        if hints:
            reason_parts.append(f"{hints} hint(s) were needed")
            evidence.append(f"{hints} hints used")
            urgency += 1.0

        freeform = int(metrics.get("freeform_attempts", 0))
        freeform_correct = int(metrics.get("freeform_correct", 0))
        if freeform and not freeform_correct:
            reason_parts.append("you have not explained a solution correctly in your own words")
            evidence.append("Free-form explanation never judged correct")
            urgency += 2.0

        regressions = int(review_regressions.get(concept_id, 0))
        if regressions:
            reason_parts.append(
                f"{regressions} later review attempt(s) were wrong after an "
                "earlier success, which suggests recall rather than understanding"
            )
            evidence.append(f"{regressions} review regression(s)")
            urgency += 4.0 + regressions

        age = days_since(last_attempt_at.get(concept_id))
        if age is not None and age >= DUE_AFTER_DAYS and attempts >= MIN_ATTEMPTS_FOR_STALENESS:
            reason_parts.append(f"last practised {int(age)} days ago")
            evidence.append(f"Last attempt {int(age)} days ago")
            urgency += 1.0 + min(age / 10.0, 3.0)

        if not reason_parts:
            continue

        items.append(
            ReviewItem(
                concept_id=concept_id,
                title=title,
                reason="Recommended because " + ", and ".join(reason_parts) + ".",
                evidence=evidence,
                urgency=urgency,
            )
        )

    items.sort(key=lambda item: -item.urgency)
    return items[:limit]


def compute_review_regressions(attempts: list[dict]) -> dict[str, int]:
    """Count concepts that failed a review after having been solved once.

    ``attempts`` are ordered oldest first.
    """
    solved: set[str] = set()
    regressions: dict[str, int] = {}
    for attempt in attempts:
        concept_id = str(attempt.get("concept_id", ""))
        if not concept_id:
            continue
        correct = bool(attempt.get("correct"))
        if is_review_attempt(str(attempt.get("exercise_type", ""))):
            if correct:
                solved.discard(concept_id)
            elif concept_id in solved:
                regressions[concept_id] = regressions.get(concept_id, 0) + 1
        elif correct:
            solved.add(concept_id)
    return regressions


def persist_reviews(database, items: list[ReviewItem], language: str = "cpp") -> list[int]:
    """Store review flags, deduplicated on (concept, language, open).

    A C++ pointer review and a C pointer review are different flags: they point
    at different mistakes, so one must not satisfy the other.
    """
    return [
        database.add_review(
            item.concept_id, item.reason, "; ".join(item.evidence), language
        )
        for item in items
    ]