"""The concept model: concepts, prerequisites and project definitions.

Concepts are **structured data**, not code. The definitions live in
``mentorsmith/data/concepts.json`` so they can be edited and reviewed without
touching Python, and so the prerequisite graph is data you can validate.

Loading validates the file rather than trusting it:

* every prerequisite must exist
* no concept may require itself
* the graph must be acyclic
* every ``lesson_id`` must resolve to a real lesson

A broken definition raises :class:`ConceptModelError` at load time, so a typo
fails immediately instead of silently producing impossible recommendations.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "concepts.json"


class ConceptModelError(RuntimeError):
    """The concept data file is missing, malformed or internally inconsistent."""


@dataclass(frozen=True)
class Concept:
    """One concept the learner is expected to master."""

    id: str
    title: str
    lesson_id: str
    summary: str
    prerequisites: tuple[str, ...] = ()
    error_categories: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "lesson_id": self.lesson_id,
            "summary": self.summary,
            "prerequisites": list(self.prerequisites),
            "error_categories": list(self.error_categories),
        }


@dataclass(frozen=True)
class Milestone:
    """One small step of a project, with testable acceptance criteria."""

    title: str
    requirements: str
    acceptance_criteria: tuple[str, ...]
    hint: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "requirements": self.requirements,
            "acceptance_criteria": list(self.acceptance_criteria),
            "hint": self.hint,
        }


@dataclass(frozen=True)
class Project:
    """A generated project built from concepts the learner has studied."""

    id: str
    title: str
    purpose: str
    concepts: tuple[str, ...]
    difficulty: str
    milestones: tuple[Milestone, ...]
    extensions: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "purpose": self.purpose,
            "concepts": list(self.concepts),
            "difficulty": self.difficulty,
            "milestones": [m.to_dict() for m in self.milestones],
            "extensions": list(self.extensions),
        }


@dataclass
class ConceptModel:
    """The whole loaded model, with helpers for navigation."""

    concepts: dict[str, Concept] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    @classmethod
    def load(cls, path: Path | None = None, valid_lesson_ids: set[str] | None = None) -> "ConceptModel":
        """Read, parse and validate the model."""
        source = Path(path) if path else DATA_PATH
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ConceptModelError(f"Concept data file not found: {source}") from exc
        except json.JSONDecodeError as exc:
            raise ConceptModelError(f"Concept data file is not valid JSON: {exc}") from exc

        if not isinstance(raw, dict):
            raise ConceptModelError("Concept data must be a JSON object.")

        concepts: dict[str, Concept] = {}
        for entry in raw.get("concepts", []):
            concept_id = str(entry.get("id", "")).strip()
            if not concept_id:
                raise ConceptModelError("Every concept needs a non-empty 'id'.")
            if concept_id in concepts:
                raise ConceptModelError(f"Duplicate concept id: {concept_id}")
            concepts[concept_id] = Concept(
                id=concept_id,
                title=str(entry.get("title", concept_id)),
                lesson_id=str(entry.get("lesson_id", "")),
                summary=str(entry.get("summary", "")),
                prerequisites=tuple(str(p) for p in entry.get("prerequisites", [])),
                error_categories=tuple(str(c) for c in entry.get("error_categories", [])),
            )

        projects: dict[str, Project] = {}
        for entry in raw.get("projects", []):
            project_id = str(entry.get("id", "")).strip()
            if not project_id:
                raise ConceptModelError("Every project needs a non-empty 'id'.")
            milestones = tuple(
                Milestone(
                    title=str(m.get("title", "Milestone")),
                    requirements=str(m.get("requirements", "")),
                    acceptance_criteria=tuple(str(c) for c in m.get("acceptance_criteria", [])),
                    hint=str(m.get("hint", "")),
                )
                for m in entry.get("milestones", [])
            )
            projects[project_id] = Project(
                id=project_id,
                title=str(entry.get("title", project_id)),
                purpose=str(entry.get("purpose", "")),
                concepts=tuple(str(c) for c in entry.get("concepts", [])),
                difficulty=str(entry.get("difficulty", "unknown")),
                milestones=milestones,
                extensions=tuple(str(e) for e in entry.get("extensions", [])),
            )

        model = cls(concepts=concepts, projects=projects)
        model.validate(valid_lesson_ids)
        return model

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def validate(self, valid_lesson_ids: set[str] | None = None) -> None:
        """Raise if the model is internally inconsistent."""
        if not self.concepts:
            raise ConceptModelError("No concepts defined.")

        for concept in self.concepts.values():
            if concept.id in concept.prerequisites:
                raise ConceptModelError(f"Concept '{concept.id}' requires itself.")
            for prerequisite in concept.prerequisites:
                if prerequisite not in self.concepts:
                    raise ConceptModelError(
                        f"Concept '{concept.id}' requires unknown concept "
                        f"'{prerequisite}'."
                    )
            if valid_lesson_ids is not None and concept.lesson_id:
                if concept.lesson_id not in valid_lesson_ids:
                    raise ConceptModelError(
                        f"Concept '{concept.id}' points at unknown lesson "
                        f"'{concept.lesson_id}'."
                    )

        cycle = self.find_cycle()
        if cycle:
            raise ConceptModelError(
                "Prerequisite cycle detected: " + " -> ".join(cycle)
            )

        for project in self.projects.values():
            for concept_id in project.concepts:
                if concept_id not in self.concepts:
                    raise ConceptModelError(
                        f"Project '{project.id}' references unknown concept "
                        f"'{concept_id}'."
                    )
            if not project.milestones:
                raise ConceptModelError(
                    f"Project '{project.id}' has no milestones."
                )
            for milestone in project.milestones:
                if not milestone.acceptance_criteria:
                    raise ConceptModelError(
                        f"Project '{project.id}' milestone "
                        f"'{milestone.title}' has no acceptance criteria."
                    )

    def find_cycle(self) -> list[str] | None:
        """Return a prerequisite cycle as a path, or ``None`` if acyclic."""
        WHITE, GREY, BLACK = 0, 1, 2
        colour = {concept_id: WHITE for concept_id in self.concepts}

        def visit(node: str, path: list[str]) -> list[str] | None:
            colour[node] = GREY
            for neighbour in self.concepts[node].prerequisites:
                if neighbour not in colour:      # already validated to exist
                    continue
                if colour[neighbour] == GREY:
                    index = path.index(neighbour) if neighbour in path else 0
                    return path[index:] + [neighbour]
                if colour[neighbour] == WHITE:
                    found = visit(neighbour, path + [neighbour])
                    if found:
                        return found
            colour[node] = BLACK
            return None

        for concept_id in self.concepts:
            if colour[concept_id] == WHITE:
                cycle = visit(concept_id, [concept_id])
                if cycle:
                    return cycle
        return None

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def get(self, concept_id: str) -> Concept | None:
        return self.concepts.get(concept_id)

    def ordered_ids(self) -> list[str]:
        """Concept ids in prerequisite order (prerequisites first)."""
        ordered: list[str] = []
        seen: set[str] = set()

        def visit(concept_id: str, stack: tuple[str, ...] = ()) -> None:
            if concept_id in seen or concept_id in stack:
                return
            for prerequisite in self.concepts[concept_id].prerequisites:
                visit(prerequisite, stack + (concept_id,))
            seen.add(concept_id)
            ordered.append(concept_id)

        for concept_id in self.concepts:
            visit(concept_id)
        return ordered

    def dependents(self, concept_id: str) -> list[str]:
        """Concepts that directly require ``concept_id``."""
        return [
            other.id
            for other in self.concepts.values()
            if concept_id in other.prerequisites
        ]

    def missing_prerequisites(self, concept_id: str, mastered: set[str]) -> list[str]:
        """Prerequisites of ``concept_id`` the learner has not mastered."""
        concept = self.concepts.get(concept_id)
        if concept is None:
            return []
        return [p for p in concept.prerequisites if p not in mastered]

    def all_error_categories(self) -> list[str]:
        categories: set[str] = set()
        for concept in self.concepts.values():
            categories.update(concept.error_categories)
        return sorted(categories)

    def concepts_for_lesson(self, lesson_id: str) -> list[str]:
        return [c.id for c in self.concepts.values() if c.lesson_id == lesson_id]

    def projects_using(self, concept_id: str) -> list[str]:
        return [p.id for p in self.projects.values() if concept_id in p.concepts]

    def summary(self) -> dict:
        return {
            "concepts": len(self.concepts),
            "projects": len(self.projects),
            "milestones": sum(len(p.milestones) for p in self.projects.values()),
            "error_categories": len(self.all_error_categories()),
        }


_DEFAULT_MODEL: ConceptModel | None = None


def load_model(refresh: bool = False, valid_lesson_ids: set[str] | None = None) -> ConceptModel:
    """Load the concept model, caching it for the process lifetime.

    Pass ``refresh=True`` after editing the JSON during development.
    """
    global _DEFAULT_MODEL
    if _DEFAULT_MODEL is None or refresh:
        _DEFAULT_MODEL = ConceptModel.load(valid_lesson_ids=valid_lesson_ids)
    return _DEFAULT_MODEL