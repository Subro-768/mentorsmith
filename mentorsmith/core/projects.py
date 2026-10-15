"""Project generation and milestone tracking.

A project is proposed only when its concepts have evidence behind them. The
handoff is explicit that projects should be based on concepts the learner has
"studied **and demonstrated**", so a project whose concepts are untouched is
not silently offered; it is returned with its gaps flagged, and the caller
decides whether to show it.

Generated projects come from the structured catalogue in
``concepts.json``, not from the model. Generation here means: *choose*, *check*
and *tailor* — deciding which project fits, warning about prerequisites, and
estimating difficulty from the learner's own record rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .concepts import ConceptModel, Project
from .mastery import MasteryAssessment

DIFFICULTY_ORDER = ("beginner", "intermediate", "advanced")


@dataclass
class ProjectProposal:
    """A project suggestion with its readiness and gaps made explicit."""

    project: Project
    ready: bool
    missing_prerequisites: list[str] = field(default_factory=list)
    weak_concepts: list[str] = field(default_factory=list)
    estimated_difficulty: str = "beginner"
    rationale: str = ""
    prerequisites_required: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_id": self.project.id,
            "title": self.project.title,
            "purpose": self.project.purpose,
            "ready": self.ready,
            "missing_prerequisites": list(self.missing_prerequisites),
            "weak_concepts": list(self.weak_concepts),
            "estimated_difficulty": self.estimated_difficulty,
            "rationale": self.rationale,
            "prerequisites_required": list(self.prerequisites_required),
            "milestones": [m.to_dict() for m in self.project.milestones],
            "extensions": list(self.project.extensions),
        }


def _index(value: str) -> int:
    try:
        return DIFFICULTY_ORDER.index(value)
    except ValueError:
        return 0


def estimate_difficulty(
    project: Project, assessments: dict[str, MasteryAssessment]
) -> str:
    """Raise or lower the catalogue difficulty from the learner's record.

    The catalogue's rating is a starting point. If the learner is struggling
    with the project's own concepts the estimate goes up, because the same
    project is harder when you keep getting it wrong.
    """
    base = _index(project.difficulty)
    project_concepts = [assessments.get(cid) for cid in project.concepts]
    relevant = [a for a in project_concepts if a is not None and a.metrics.get("attempts", 0) > 0]

    if not relevant:
        return project.difficulty

    weak = sum(1 for a in relevant if a.label in ("needs_review", "not_started"))
    strong = sum(1 for a in relevant if a.is_mastered)

    if weak and not strong:
        base += 1
    elif strong and not weak:
        base -= 1

    return DIFFICULTY_ORDER[max(0, min(len(DIFFICULTY_ORDER) - 1, base))]


def prerequisites_of(model: ConceptModel, project: Project) -> list[str]:
    """Every concept the project depends on, including indirect ones."""
    collected: set[str] = set()

    def visit(concept_id: str, stack: tuple[str, ...] = ()) -> None:
        if concept_id in collected or concept_id in stack:
            return
        collected.add(concept_id)
        concept = model.get(concept_id)
        if concept is None:
            return
        for prerequisite in concept.prerequisites:
            visit(prerequisite, stack + (concept_id,))

    for concept_id in project.concepts:
        visit(concept_id)
    return sorted(collected)


def propose_project(
    model: ConceptModel,
    assessments: dict[str, MasteryAssessment],
    project_id: str | None = None,
) -> ProjectProposal | None:
    """Propose one project, chosen by fit, with gaps spelled out."""
    projects = list(model.projects.values())
    if not projects:
        return None

    if project_id:
        chosen = model.projects.get(project_id)
        if chosen is None:
            return None
        candidates = [chosen]
    else:
        candidates = projects

    scored = sorted(
        (_score_project(p, model, assessments) for p in candidates),
        key=lambda item: -item[0],
    )
    best_score, best = scored[0]
    return _build_proposal(best, best_score, model, assessments)


def propose_projects(
    model: ConceptModel,
    assessments: dict[str, MasteryAssessment],
    limit: int = 3,
    ready_only: bool = False,
) -> list[ProjectProposal]:
    """Rank every catalogue project by fit.

    ``ready_only`` filters to projects with no missing prerequisites, which is
    what the "build something" action should offer.
    """
    proposals = [
        _build_proposal(project, score, model, assessments)
        for score, project in (
            _score_project(p, model, assessments) for p in model.projects.values()
        )
    ]
    proposals.sort(key=lambda p: (not p.ready, -_index(p.estimated_difficulty), p.project.id))
    if ready_only:
        proposals = [p for p in proposals if p.ready]
    return proposals[:limit]


def _score_project(
    project: Project, model: ConceptModel, assessments: dict[str, MasteryAssessment]
) -> tuple[float, Project]:
    """Higher is a better fit. Ready projects outrank blocked ones."""
    relevant = [assessments.get(cid) for cid in project.concepts]
    strong = sum(1 for a in relevant if a is not None and a.is_mastered)
    weak = sum(1 for a in relevant if a is not None and a.label in ("needs_review", "not_started"))
    required = prerequisites_of(model, project)
    missing = [
        cid
        for cid in required
        if not (assessments.get(cid) and assessments[cid].is_mastered)
    ]

    score = strong * 10.0 - weak * 4.0 - len(missing) * 6.0
    return score, project


def _build_proposal(
    project: Project,
    score: float,
    model: ConceptModel,
    assessments: dict[str, MasteryAssessment],
) -> ProjectProposal:
    required = prerequisites_of(model, project)
    missing = [
        cid for cid in required
        if not (assessments.get(cid) and assessments[cid].is_mastered)
    ]
    weak = [
        cid
        for cid in project.concepts
        if assessments.get(cid) is not None
        and assessments[cid].label == "needs_review"
    ]

    ready = not missing
    difficulty = estimate_difficulty(project, assessments)

    if ready:
        rationale = (
            f"All {len(required)} concept(s) this project needs are strong "
            f"based on your graded attempts: {', '.join(required)}."
        )
    elif weak:
        rationale = (
            "Blocked by work in progress on "
            f"{', '.join(weak)}. Strengthening those first will make this "
            "much easier."
        )
    else:
        rationale = (
            "Missing evidence for "
            f"{', '.join(missing)}. Do the exercises for those concepts first; "
            "the project is worth doing afterwards."
        )

    return ProjectProposal(
        project=project,
        ready=ready,
        missing_prerequisites=missing,
        weak_concepts=weak,
        estimated_difficulty=difficulty,
        rationale=rationale,
        prerequisites_required=required,
    )


# ----------------------------------------------------------------------
# Milestone tracking
# ----------------------------------------------------------------------
def milestone_progress(milestones: list[dict]) -> dict:
    """Summarise milestone states for the UI."""
    total = len(milestones)
    done = sum(1 for m in milestones if m.get("status") == "done")
    in_progress = sum(1 for m in milestones if m.get("status") == "in_progress")
    return {
        "total": total,
        "done": done,
        "in_progress": in_progress,
        "pending": total - done - in_progress,
        "percent": int(round(done * 100 / total)) if total else 0,
        "next": next(
            (m for m in sorted(milestones, key=lambda m: m.get("ordinal", 0))
             if m.get("status") != "done"),
            None,
        ),
    }


def save_project(database, proposal: ProjectProposal) -> str:
    """Persist a project and its milestones.

    Additive and idempotent, so re-proposing the same project is harmless.
    """
    project = proposal.project
    return database.create_project(
        project.id,
        project.title,
        purpose=project.purpose,
        concepts=project.concepts,
        difficulty=proposal.estimated_difficulty,
        milestones=[m.to_dict() for m in project.milestones],
    )