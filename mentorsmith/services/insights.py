"""Assembling what the dashboard shows, and being able to justify every line.

Phase 2 is explicit that the dashboard must show a suggested next activity
**with its reason**, and that chat message counts and time spent in the app
must **not** be counted as proof of learning. Neither quantity is read
anywhere in this module — only graded attempts, hint usage and recorded
outcomes.

Everything returned here is derived from the database through
:mod:`mentorsmith.core.mastery`, :mod:`mentorsmith.core.adaptive` and
:mod:`mentorsmith.core.revision`, so the UI does no interpretation of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..core.adaptive import Recommendation, recommend_next
from ..core.concepts import ConceptModel
from ..core.db import Database
from ..core.exercises import ExerciseBank
from ..core.mastery import (
    LABEL_DESCRIPTIONS,
    MasteryAssessment,
    assess_many,
    label_rank,
)
from ..core.revision import (
    DISCLAIMER,
    ReviewItem,
    compute_review_regressions,
    recommend_reviews,
)

#: Counts of things that are explicitly NOT treated as evidence.
NOT_EVIDENCE_NOTE = (
    "Chat messages sent and time spent in the app are not counted here. Only "
    "graded exercise attempts are."
)


@dataclass
class ConceptRow:
    """One concept's state, for the dashboard table."""

    concept_id: str
    title: str
    label: str
    score: float
    attempts: int
    correct: int
    hints_used: int
    independent: int
    evidence: list[str] = field(default_factory=list)
    missing_prerequisites: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "concept_id": self.concept_id,
            "title": self.title,
            "label": self.label,
            "score": round(self.score, 3),
            "attempts": self.attempts,
            "correct": self.correct,
            "hints_used": self.hints_used,
            "independent": self.independent,
            "evidence": list(self.evidence),
            "missing_prerequisites": list(self.missing_prerequisites),
        }


@dataclass
class DashboardReport:
    """Everything the dashboard renders."""

    concepts: list[ConceptRow] = field(default_factory=list)
    assessments: dict[str, MasteryAssessment] = field(default_factory=dict)
    recommendations: list[Recommendation] = field(default_factory=list)
    reviews: list[ReviewItem] = field(default_factory=list)
    label_counts: dict[str, int] = field(default_factory=dict)
    independent_results: int = 0
    hints_used: int = 0
    total_attempts: int = 0
    error_categories: list[tuple[str, int]] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)
    milestone_totals: dict[str, int] = field(default_factory=dict)
    next_activity: Recommendation | None = None
    next_activity_reason: str = ""
    disclaimer: str = DISCLAIMER
    not_evidence_note: str = NOT_EVIDENCE_NOTE

    def summary_line(self) -> str:
        done = self.label_counts.get("strong", 0)
        total = len(self.concepts)
        return (
            f"{done} of {total} concepts strong · "
            f"{self.total_attempts} graded attempts · "
            f"{self.independent_results} solved independently · "
            f"{self.hints_used} hints used"
        )

    def to_dict(self) -> dict:
        return {
            "concepts": [c.to_dict() for c in self.concepts],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "reviews": [r.to_dict() for r in self.reviews],
            "label_counts": dict(self.label_counts),
            "independent_results": self.independent_results,
            "hints_used": self.hints_used,
            "total_attempts": self.total_attempts,
            "error_categories": [list(e) for e in self.error_categories],
            "projects": list(self.projects),
            "milestone_totals": dict(self.milestone_totals),
            "next_activity": self.next_activity.to_dict() if self.next_activity else None,
            "next_activity_reason": self.next_activity_reason,
            "summary": self.summary_line(),
        }


def _attempt_history(database: Database, concept_ids: list[str], language: str) -> list[dict]:
    """All attempts for the given concepts in one language, oldest first."""
    history: list[dict] = []
    for concept_id in concept_ids:
        attempts = database.attempts_for_concept(concept_id, language)
        history.extend(reversed(attempts))     # newest first -> reverse
    history.sort(key=lambda row: int(row.get("id", 0)))
    return history


def build_report(
    database: Database,
    model: ConceptModel,
    bank: ExerciseBank,
    *,
    language: str = "cpp",
    review_limit: int = 5,
    recommendation_limit: int = 3,
) -> DashboardReport:
    """Build the full dashboard report from stored evidence for one language.

    ``language`` scopes every query. Progress is never carried between tracks:
    being strong at C++ pointers says nothing about C pointers, so Phase 4
    requires a diagnostic exercise rather than transferring a label.
    """
    concept_ids = list(model.concepts)
    evidence = database.concept_evidence(concept_ids, language)
    assessments = assess_many(evidence)

    history = _attempt_history(database, concept_ids, language)
    last_attempt_at = {
        str(row["concept_id"]): str(row["created_at"])
        for row in history
        if row.get("concept_id")
    }
    regressions = compute_review_regressions(history)

    report = DashboardReport(assessments=assessments)
    report.total_attempts = len(history)
    report.hints_used = database.total_hints_used()
    report.independent_results = database.independent_attempt_count()
    report.error_categories = database.error_category_counts(limit=8)

    # Concept rows, weakest first so problems surface at the top.
    mastered = {cid for cid, a in assessments.items() if a.is_mastered}
    for concept_id in concept_ids:
        assessment = assessments[concept_id]
        concept = model.concepts[concept_id]
        report.label_counts[assessment.label] = (
            report.label_counts.get(assessment.label, 0) + 1
        )
        report.concepts.append(
            ConceptRow(
                concept_id=concept_id,
                title=concept.title,
                label=assessment.label,
                score=assessment.score,
                attempts=int(assessment.metrics.get("attempts", 0)),
                correct=int(assessment.metrics.get("correct", 0)),
                hints_used=int(assessment.metrics.get("hints_used", 0)),
                independent=_independent_for(database, concept_id),
                evidence=list(assessment.evidence),
                missing_prerequisites=model.missing_prerequisites(concept_id, mastered),
            )
        )
    report.concepts.sort(key=lambda row: (label_rank(row.label), row.concept_id))

    # Recommendations, using what has already been attempted.
    attempted_by_concept: dict[str, set[str]] = {}
    types_by_concept: dict[str, set[str]] = {}
    for concept_id in concept_ids:
        attempts = database.attempts_for_concept(concept_id, language)
        attempted_by_concept[concept_id] = {
            str(a["exercise_id"]) for a in attempts if a.get("exercise_id")
        }
        types_by_concept[concept_id] = {
            str(a["exercise_type"]) for a in attempts if a.get("exercise_type")
        }

    report.recommendations = recommend_next(
        bank,
        model,
        assessments,
        attempted_by_concept=attempted_by_concept,
        types_by_concept=types_by_concept,
        last_attempt_at=last_attempt_at,
        recurring_categories={name for name, _ in report.error_categories},
        limit=recommendation_limit,
    )
    report.next_activity = report.recommendations[0] if report.recommendations else None
    report.next_activity_reason = (
        report.next_activity.reason
        if report.next_activity
        else "Nothing to recommend yet: no graded attempts have been recorded, "
             "so there is no evidence to base a suggestion on."
    )

    report.reviews = recommend_reviews(
        model,
        assessments,
        last_attempt_at=last_attempt_at,
        review_regressions=regressions,
        limit=review_limit,
    )

    report.projects = database.list_projects()
    done_milestones = 0
    total_milestones = 0
    for project in report.projects:
        milestones = database.milestones_for(str(project["id"]))
        total_milestones += len(milestones)
        done_milestones += sum(1 for m in milestones if m.get("status") == "done")
    report.milestone_totals = {
        "done": done_milestones,
        "total": total_milestones,
    }

    return report


def _independent_for(database: Database, concept_id: str) -> int:
    rows = database.connect().execute(
        "SELECT COUNT(*) AS n FROM exercise_attempts "
        "WHERE concept_id = ? AND correct = 1 AND independent = 1",
        (concept_id,),
    ).fetchone()
    return int(rows["n"]) if rows else 0


def label_glossary() -> dict[str, str]:
    """Plain-language descriptions of every label, for the UI."""
    return dict(LABEL_DESCRIPTIONS)