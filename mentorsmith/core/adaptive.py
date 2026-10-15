"""Choosing the next exercise, and being able to say why.

The selection is **deterministic**: the same history always produces the same
recommendation. Nothing here calls the AI, which means it can be unit-tested
exhaustively and the learner can be told exactly why something was suggested.

A deliberate omission: **lesson completion is never treated as evidence.**
Reading a lesson and clicking through it says nothing about understanding, so
:class:`Recommendation` is derived only from graded attempts. The
``lesson_progress`` table is not read by this module at all.

Priorities, highest first:

1. **Repair** — a concept already attempted but weak, especially with a
   recurring error category. New material waits.
2. **Prerequisite repair** — fix the blocking concept before the dependent one.
3. **Extension** — a concept whose prerequisites are all strong but which has
   not been attempted.
4. **Novel variation** — the standard exercise is solved, so try an unfamiliar
   one, since recall of a worked example is not generalisation.
5. **Delayed review** — a strong concept not touched recently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from .concepts import ConceptModel
from .exercises import Exercise, ExerciseBank
from .mastery import MasteryAssessment, label_rank

#: Order of exercise types tried when a concept has variety constraints.
TYPE_PREFERENCE = (
    "predict-output",
    "find-a-bug",
    "write-a-function",
    "complete-code",
    "modify-code",
    "compare-implementations",
    "explain-code",
    "solve-without-AI",
)

#: A strong concept is suggested for review after this many days.
REVIEW_AFTER_DAYS = 14

#: PRIME-like relevance bonus for matching the learner's most common mistake.
RECURRING_MISTAKE_WEIGHT = 0.6


@dataclass
class Recommendation:
    """One suggested next activity, with its justification."""

    exercise_id: str
    concept_id: str
    exercise_type: str
    title: str
    reason: str
    category: str
    score: float = 0.0
    is_review: bool = False
    blocked_by: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "exercise_id": self.exercise_id,
            "concept_id": self.concept_id,
            "exercise_type": self.exercise_type,
            "title": self.title,
            "reason": self.reason,
            "category": self.category,
            "score": round(self.score, 3),
            "is_review": self.is_review,
            "blocked_by": list(self.blocked_by),
        }


def _days_since(timestamp: str | None) -> float | None:
    """Whole days since an ISO timestamp, or None if unparseable."""
    if not timestamp:
        return None
    try:
        parsed = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0)


def _pick_exercise(
    bank: ExerciseBank,
    concept_id: str,
    attempted_ids: set[str],
    attempted_types: set[str],
    *,
    prefer_novel: bool,
) -> Exercise | None:
    """Choose the best exercise for a concept.

    Avoids anything already attempted, prefers an unfamiliar variation when
    asked, and otherwise prefers an exercise type not yet used so the same
    skill is not drilled through one lens.
    """
    candidates = bank.unattempted(concept_id, attempted_ids)
    if not candidates:
        return None

    if prefer_novel:
        novel = [e for e in candidates if e.novel]
        if novel:
            candidates = novel

    for preferred_type in TYPE_PREFERENCE:
        for exercise in candidates:
            if exercise.type == preferred_type and exercise.type not in attempted_types:
                return exercise
    # Everything left is a type already used for this concept; take the first
    # novel one, else the first candidate.
    for exercise in candidates:
        if exercise.novel:
            return exercise
    return candidates[0]


def recommend_next(
    bank: ExerciseBank,
    model: ConceptModel,
    assessments: dict[str, MasteryAssessment],
    *,
    attempted_by_concept: dict[str, set[str]] | None = None,
    types_by_concept: dict[str, set[str]] | None = None,
    last_attempt_at: dict[str, str] | None = None,
    recurring_categories: set[str] | None = None,
    limit: int = 3,
) -> list[Recommendation]:
    """Return up to ``limit`` recommended exercises, best first.

    Each recommendation carries a plain-language ``reason``. When no exercise
    can be justified, the result is empty rather than padded with filler.
    """
    attempted_by_concept = attempted_by_concept or {}
    types_by_concept = types_by_concept or {}
    last_attempt_at = last_attempt_at or {}
    recurring_categories = recurring_categories or set()

    candidates: list[tuple[float, int, Recommendation]] = []
    seen_exercises: set[str] = set()

    # Concepts in prerequisite order, so a repair suggestion always names a
    # concept the learner is actually ready to work on.
    for concept_id in model.ordered_ids():
        assessment = assessments.get(concept_id)
        if assessment is None:
            continue
        concept = model.concepts[concept_id]
        missing = model.missing_prerequisites(concept_id, {
            cid for cid, a in assessments.items() if a.is_mastered
        })

        attempts = int(assessment.metrics.get("attempts", 0))
        hints = int(assessment.metrics.get("hints_used", 0))
        first_try = bool(assessment.metrics.get("first_attempt_correct"))
        thin_evidence = attempts < 2 and not hints and first_try

        # Genuine weakness: something failed, or help was needed.
        needs_repair = (
            assessment.label == "needs_review"
            or (
                assessment.label == "developing"
                and attempts >= 2
                and not assessment.is_mastered
            )
            or (attempts >= 1 and not first_try)
            or hints > 0
        )

        if attempts > 0 and needs_repair and not thin_evidence:
            exercise = _pick_exercise(
                bank,
                concept_id,
                attempted_by_concept.get(concept_id, set()),
                types_by_concept.get(concept_id, set()),
                prefer_novel=False,
            )
            if exercise is not None and exercise.id not in seen_exercises:
                reason = _repair_reason(assessment, concept.title)
                score = 100.0 + (10 - label_rank(assessment.label)) * 5
                if recurring_categories & set(
                    assessment.metrics.get("error_categories", {})
                ):
                    score += RECURRING_MISTAKE_WEIGHT
                candidates.append(
                    (
                        score,
                        0,
                        Recommendation(
                            exercise_id=exercise.id,
                            concept_id=concept_id,
                            exercise_type=exercise.type,
                            title=exercise.title,
                            reason=reason,
                            category="repair",
                            score=score,
                            blocked_by=tuple(missing),
                        ),
                    )
                )
                seen_exercises.add(exercise.id)

        # Thin evidence: right first time, but a single attempt proves little.
        elif attempts > 0 and thin_evidence:
            exercise = _pick_exercise(
                bank,
                concept_id,
                attempted_by_concept.get(concept_id, set()),
                types_by_concept.get(concept_id, set()),
                prefer_novel=True,
            )
            if exercise is not None and exercise.id not in seen_exercises:
                candidates.append(
                    (
                        65.0,
                        1,
                        Recommendation(
                            exercise_id=exercise.id,
                            concept_id=concept_id,
                            exercise_type=exercise.type,
                            title=exercise.title,
                            reason=(
                                f"'{concept.title}' was correct first time, but one "
                                "attempt is not enough to call it understood. This "
                                "is an unfamiliar variation, which tests transfer "
                                "rather than recall."
                            ),
                            category="consolidate",
                            score=65.0,
                        ),
                    )
                )
                seen_exercises.add(exercise.id)

        # Extension: prerequisites are strong, nothing attempted yet.
        elif assessment.label == "not_started" and not missing:
            exercise = _pick_exercise(
                bank,
                concept_id,
                set(),
                set(),
                prefer_novel=False,
            )
            if exercise is not None and exercise.id not in seen_exercises:
                score = 80.0
                candidates.append(
                    (
                        score,
                        1,
                        Recommendation(
                            exercise_id=exercise.id,
                            concept_id=concept_id,
                            exercise_type=exercise.type,
                            title=exercise.title,
                            reason=(
                                f"No graded attempts at '{concept.title}' yet, and "
                                "its prerequisites are strong, so it is a good "
                                "next step."
                            ),
                            category="extension",
                            score=score,
                        ),
                    )
                )
                seen_exercises.add(exercise.id)

        # Delayed review of a strong concept.
        elif assessment.is_mastered:
            age = _days_since(last_attempt_at.get(concept_id))
            if age is None or age >= REVIEW_AFTER_DAYS:
                exercise = _pick_exercise(
                    bank,
                    concept_id,
                    attempted_by_concept.get(concept_id, set()),
                    types_by_concept.get(concept_id, set()),
                    prefer_novel=True,
                )
                if exercise is not None and exercise.id not in seen_exercises:
                    score = 50.0 + (age or REVIEW_AFTER_DAYS) * 0.5
                    when = (
                        f"last practised {int(age)} days ago"
                        if age is not None
                        else "with no recent practice recorded"
                    )
                    candidates.append(
                        (
                            score,
                            2,
                            Recommendation(
                                exercise_id=exercise.id,
                                concept_id=concept_id,
                                exercise_type=exercise.type,
                                title=exercise.title,
                                reason=(
                                    f"'{concept.title}' is strong and was {when}. "
                                    "This is an unfamiliar variation, which is a "
                                    "better check than repeating the worked example."
                                ),
                                category="review",
                                score=score,
                                is_review=True,
                            ),
                        )
                    )
                    seen_exercises.add(exercise.id)

    candidates.sort(key=lambda item: (-item[0], item[1]))
    return [recommendation for _score, _tier, recommendation in candidates[:limit]]


def _repair_reason(assessment: MasteryAssessment, title: str) -> str:
    """Explain a repair suggestion from the learner's own evidence."""
    attempts = assessment.metrics.get("attempts", 0)
    correct = assessment.metrics.get("correct", 0)
    categories = assessment.metrics.get("error_categories", {}) or {}
    repeated = [
        f"'{name}' came up {count} times"
        for name, count in sorted(categories.items(), key=lambda kv: -kv[1])
        if count >= 3
    ]

    parts = [f"{correct} of {attempts} graded attempts at '{title}' were correct."]
    if repeated:
        parts.append("There is a repeating problem: " + ", ".join(repeated) + ".")
    elif categories:
        top = max(categories.items(), key=lambda kv: kv[1])
        parts.append(f"The most common failure was '{top[0]}' ({top[1]} times).")
    hints = assessment.metrics.get("hints_used", 0)
    if hints:
        parts.append(f"{hints} hint(s) were used, so this was not yet independent.")
    return " ".join(parts)


def prerequisite_gaps(
    model: ConceptModel, assessments: dict[str, MasteryAssessment], concept_id: str
) -> list[str]:
    """Concepts the learner must strengthen before ``concept_id``."""
    mastered = {cid for cid, a in assessments.items() if a.is_mastered}
    return model.missing_prerequisites(concept_id, mastered)


def prerequisites_status(
    model: ConceptModel, assessments: dict[str, MasteryAssessment]
) -> dict[str, list[str]]:
    """For every concept, the prerequisites not yet strong."""
    mastered = {cid for cid, a in assessments.items() if a.is_mastered}
    return {
        concept_id: model.missing_prerequisites(concept_id, mastered)
        for concept_id in model.concepts
    }