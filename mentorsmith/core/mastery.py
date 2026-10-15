"""Turning raw attempt evidence into a mastery label you can explain.

A label such as ``strong`` is a **summary, not a measurement**. Nothing here
claims to know what a learner understands; it only summarises recorded
behaviour, and it must always be able to say *why*.

Design rules:

* Every label carries a list of human-readable evidence strings.
* Labels are derived from counts, never from time spent in the app or the
  number of chat messages. Phase 2 explicitly forbids treating either as proof
  of learning.
* ``not_started`` is distinguished from ``needs_review``. Doing nothing is not
  the same as having tried and struggling.
* Prerequisites gate recommendations but never fabricate a label: a concept
  with no attempts is ``not_started`` regardless of its prerequisites.

Score composition (0.0 to 1.0)::

    score = accuracy
          + 0.15 if the very first attempt was already correct
          + 0.10 if a free-form explanation was judged correct
          - 0.15 if free-form attempts exist but none were correct
          + 0.10 if an unfamiliar variation was solved
          - 0.10 per hint used beyond the first, capped at -0.30

Labels from the score, with evidence-based overrides described in
:func:`assess`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Ordered weakest to strongest. Used for sorting and for "advance one step".
LABEL_ORDER = ("not_started", "needs_review", "developing", "strong")

LABEL_DESCRIPTIONS = {
    "not_started": "No graded attempts recorded yet.",
    "needs_review": "Attempted, but the evidence is weak or shows a repeated problem.",
    "developing": "Making real progress; some signals are mixed.",
    "strong": "Consistent correct results across several attempts.",
}

#: exercise_type values starting with this mark a deliberate review attempt.
REVIEW_PREFIX = "review:"

#: One error category repeated this many times forces a review flag.
REPEAT_ERROR_THRESHOLD = 3

#: Attempts needed before the "strong" label can be granted at all.
MIN_ATTEMPTS_FOR_STRONG = 2


def is_review_attempt(exercise_type: str) -> bool:
    """Whether an attempt was a deliberate review of a past concept."""
    return (exercise_type or "").startswith(REVIEW_PREFIX)


@dataclass
class MasteryAssessment:
    """One concept's label, score and the evidence behind both."""

    concept_id: str
    label: str = "not_started"
    score: float = 0.0
    evidence: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)
    blocking_prerequisites: list[str] = field(default_factory=list)

    @property
    def is_mastered(self) -> bool:
        """Strong enough to build on. Gated on attempt count, not just score."""
        return self.label == "strong" and self.metrics.get("attempts", 0) >= MIN_ATTEMPTS_FOR_STRONG

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "label": self.label,
            "score": round(self.score, 3),
            "evidence": list(self.evidence),
            "metrics": dict(self.metrics),
            "blocking_prerequisites": list(self.blocking_prerequisites),
        }

    def explain(self) -> str:
        """One paragraph a learner can read and challenge."""
        lines = [f"{self.concept_id}: {self.label} (score {self.score:.2f})"]
        for item in self.evidence:
            lines.append(f"  - {item}")
        if self.blocking_prerequisites:
            lines.append(
                "  - blocked by: " + ", ".join(self.blocking_prerequisites)
            )
        return "\n".join(lines)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def assess(concept_id: str, evidence: dict) -> MasteryAssessment:
    """Derive a label from one concept's aggregated evidence counts.

    ``evidence`` is the shape returned by :meth:`Database.concept_evidence`.
    """
    metrics = dict(evidence or {})
    attempts = int(metrics.get("attempts", 0))
    correct = int(metrics.get("correct", 0))
    incorrect = int(metrics.get("incorrect", 0))
    hints = int(metrics.get("hints_used", 0))
    first_try = int(metrics.get("first_try_correct", 0)) > 0
    freeform = int(metrics.get("freeform_attempts", 0))
    freeform_correct = int(metrics.get("freeform_correct", 0))
    novel = int(metrics.get("novel_attempts", 0))
    error_categories: dict[str, int] = metrics.get("error_categories", {}) or {}
    exercise_types: dict[str, int] = metrics.get("exercise_types", {}) or {}

    assessment = MasteryAssessment(concept_id=concept_id)
    assessment.metrics = {
        "attempts": attempts,
        "correct": correct,
        "incorrect": incorrect,
        "hints_used": hints,
        "freeform_attempts": freeform,
        "freeform_correct": freeform_correct,
        "novel_attempts": novel,
        "first_attempt_correct": first_try,
        "accuracy": round(correct / attempts, 3) if attempts else 0.0,
        # Carried through so every consumer (recommendations, reviews) can
        # cite the same evidence the label was derived from.
        "error_categories": dict(error_categories),
        "exercise_types": dict(exercise_types),
    }

    if attempts == 0:
        assessment.label = "not_started"
        assessment.score = 0.0
        assessment.evidence.append(
            "No graded attempts recorded. Completing a lesson does not count "
            "as evidence."
        )
        return assessment

    accuracy = correct / attempts
    score = accuracy
    assessment.evidence.append(
        f"{correct} of {attempts} graded attempts were correct "
        f"({accuracy * 100:.0f}%)."
    )

    if first_try:
        score += 0.15
        assessment.evidence.append(
            "The very first attempt was already correct."
        )
    else:
        assessment.evidence.append(
            "The first attempt was wrong, so this concept needed practice."
        )

    if freeform:
        if freeform_correct:
            score += 0.10
            assessment.evidence.append(
                f"You also explained a solution correctly in your own words "
                f"({freeform_correct} of {freeform} free-form attempt(s))."
            )
        else:
            score -= 0.15
            assessment.evidence.append(
                f"{freeform} free-form explanation attempt(s) were not judged "
                "correct. Code can work without being understood, so this "
                "counts against mastery."
            )

    if novel:
        score += 0.10
        assessment.evidence.append(
            f"Solved an unfamiliar variation ({novel} attempt(s)), not just the "
            "worked example."
        )

    if hints:
        penalty = min(0.30, 0.10 * max(0, hints - 1))
        score -= penalty
        assessment.evidence.append(
            f"{hints} hint(s) used, which reduces confidence in independent "
            "understanding."
        )
    else:
        assessment.evidence.append("No hints were used on these attempts.")

    repeated = {k: v for k, v in error_categories.items() if v >= REPEAT_ERROR_THRESHOLD}
    if repeated:
        for category, count in sorted(repeated.items()):
            assessment.evidence.append(
                f"'{category}' came up {count} times — a repeating problem, not "
                "a one-off slip."
            )

    review_attempts = sum(
        count for name, count in exercise_types.items() if is_review_attempt(name)
    )
    if review_attempts:
        assessment.evidence.append(
            f"{review_attempts} of these were deliberate review attempts."
        )

    assessment.score = _clamp(score)

    # Label from score, then evidence-based overrides.
    if assessment.score >= 0.75 and attempts >= MIN_ATTEMPTS_FOR_STRONG:
        assessment.label = "strong"
    elif assessment.score >= 0.45:
        assessment.label = "developing"
    else:
        assessment.label = "needs_review"

    # A concept can score well overall while one specific misunderstanding keeps
    # recurring. That recurring misunderstanding is the thing to fix.
    if repeated and assessment.label in ("strong", "developing"):
        assessment.label = "needs_review"
        assessment.evidence.append(
            "Downgraded from the score-based label because of a repeated error "
            "category."
        )

    if assessment.label == "needs_review" and accuracy == 1.0 and attempts < MIN_ATTEMPTS_FOR_STRONG:
        assessment.evidence.append(
            f"Only {attempts} attempt so far, which is too few to judge; "
            "needing a second attempt is not the same as struggling."
        )

    return assessment


def assess_many(evidence_by_concept: dict[str, dict]) -> dict[str, MasteryAssessment]:
    """Assess several concepts at once, keyed by concept id."""
    return {
        concept_id: assess(concept_id, evidence)
        for concept_id, evidence in evidence_by_concept.items()
    }


def mastered_concepts(assessments: dict[str, MasteryAssessment]) -> set[str]:
    """Concepts strong enough to satisfy a prerequisite."""
    return {cid for cid, a in assessments.items() if a.is_mastered}


def label_rank(label: str) -> int:
    """Sort key for labels, weakest first. Unknown labels sort first."""
    try:
        return LABEL_ORDER.index(label)
    except ValueError:
        return -1