"""Concept model: structure, prerequisites and validation."""

from __future__ import annotations

import json

import pytest

from mentorsmith.core.concepts import (
    ConceptModel,
    ConceptModelError,
    load_model,
)


@pytest.fixture(scope="module")
def model() -> ConceptModel:
    from mentorsmith.core.curriculum import load_lessons

    return load_model(valid_lesson_ids={l.id for l in load_lessons()})


# ----------------------------------------------------------------------
# Structure
# ----------------------------------------------------------------------
def test_model_loads(model: ConceptModel) -> None:
    assert len(model.concepts) >= 13
    assert len(model.projects) >= 1


def test_every_concept_has_a_lesson_link(model: ConceptModel) -> None:
    for concept in model.concepts.values():
        assert concept.lesson_id


def test_prerequisite_graph_is_acyclic(model: ConceptModel) -> None:
    assert model.find_cycle() is None


def test_ordered_ids_put_prerequisites_first(model: ConceptModel) -> None:
    ordered = model.ordered_ids()
    position = {concept_id: index for index, concept_id in enumerate(ordered)}
    for concept in model.concepts.values():
        for prerequisite in concept.prerequisites:
            assert position[prerequisite] < position[concept.id]


def test_dependents_are_symmetric_with_prerequisites(model: ConceptModel) -> None:
    for concept_id, concept in model.concepts.items():
        for prerequisite in concept.prerequisites:
            assert concept_id in model.dependents(prerequisite)


def test_error_categories_are_declared(model: ConceptModel) -> None:
    categories = model.all_error_categories()
    assert "off_by_one" in categories
    assert "null_dereference" in categories


def test_concepts_for_lesson_maps_back(model: ConceptModel) -> None:
    ids = model.concepts_for_lesson("09-pointers")
    assert "pointers" in ids


def test_projects_use_real_concepts(model: ConceptModel) -> None:
    for project in model.projects.values():
        assert project.concepts
        for concept_id in project.concepts:
            assert concept_id in model.concepts


def test_every_project_milestone_has_acceptance_criteria(model: ConceptModel) -> None:
    for project in model.projects.values():
        assert project.milestones
        for milestone in project.milestones:
            assert milestone.acceptance_criteria
            assert milestone.requirements


def test_concepts_have_the_required_topics(model: ConceptModel) -> None:
    """The handoff names these explicitly."""
    required = {
        "variables", "types", "conditions", "loops", "functions", "arrays",
        "strings", "pointers", "references", "memory", "classes", "files",
        "exceptions",
    }
    assert required <= set(model.concepts)


# ----------------------------------------------------------------------
# Prerequisite queries
# ----------------------------------------------------------------------
def test_missing_prerequisites_when_none_mastered(model: ConceptModel) -> None:
    missing = model.missing_prerequisites("memory", set())
    assert "pointers" in missing
    assert "references" in missing


def test_missing_prerequisites_when_all_mastered(model: ConceptModel) -> None:
    assert model.missing_prerequisites("memory", {"pointers", "references"}) == []


def test_missing_prerequisites_for_unknown_concept(model: ConceptModel) -> None:
    assert model.missing_prerequisites("nope", set()) == []


def test_projects_using_a_concept(model: ConceptModel) -> None:
    assert model.projects_using("loops")


# ----------------------------------------------------------------------
# Validation of malformed data
# ----------------------------------------------------------------------
def _write(tmp_path, data):
    path = tmp_path / "concepts.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_missing_file_raises(tmp_path) -> None:
    with pytest.raises(ConceptModelError):
        ConceptModel.load(tmp_path / "absent.json")


def test_invalid_json_raises(tmp_path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(ConceptModelError):
        ConceptModel.load(path)


def test_empty_model_raises(tmp_path) -> None:
    with pytest.raises(ConceptModelError):
        ConceptModel.load(_write(tmp_path, {"concepts": []}))


def test_unknown_prerequisite_raises(tmp_path) -> None:
    data = {"concepts": [{"id": "a", "prerequisites": ["ghost"], "lesson_id": ""}]}
    with pytest.raises(ConceptModelError, match="unknown concept"):
        ConceptModel.load(_write(tmp_path, data))


def test_self_prerequisite_raises(tmp_path) -> None:
    data = {"concepts": [{"id": "a", "prerequisites": ["a"], "lesson_id": ""}]}
    with pytest.raises(ConceptModelError, match="requires itself"):
        ConceptModel.load(_write(tmp_path, data))


def test_prerequisite_cycle_is_detected(tmp_path) -> None:
    data = {
        "concepts": [
            {"id": "a", "prerequisites": ["b"], "lesson_id": ""},
            {"id": "b", "prerequisites": ["a"], "lesson_id": ""},
        ]
    }
    path = _write(tmp_path, data)
    with pytest.raises(ConceptModelError, match="cycle"):
        ConceptModel.load(path)


def test_longer_cycle_is_detected(tmp_path) -> None:
    data = {
        "concepts": [
            {"id": "a", "prerequisites": ["b"], "lesson_id": ""},
            {"id": "b", "prerequisites": ["c"], "lesson_id": ""},
            {"id": "c", "prerequisites": ["a"], "lesson_id": ""},
        ]
    }
    with pytest.raises(ConceptModelError, match="cycle"):
        ConceptModel.load(_write(tmp_path, data))


def test_unknown_lesson_link_raises(tmp_path) -> None:
    data = {"concepts": [{"id": "a", "lesson_id": "99-nope", "prerequisites": []}]}
    with pytest.raises(ConceptModelError, match="unknown lesson"):
        ConceptModel.load(_write(tmp_path, data), valid_lesson_ids={"01-real"})


def test_duplicate_concept_id_raises(tmp_path) -> None:
    data = {
        "concepts": [
            {"id": "a", "prerequisites": []},
            {"id": "a", "prerequisites": []},
        ]
    }
    with pytest.raises(ConceptModelError, match="Duplicate"):
        ConceptModel.load(_write(tmp_path, data))


def test_project_without_milestones_raises(tmp_path) -> None:
    data = {
        "concepts": [{"id": "a", "prerequisites": [], "lesson_id": ""}],
        "projects": [{"id": "p", "concepts": ["a"], "milestones": []}],
    }
    with pytest.raises(ConceptModelError, match="no milestones"):
        ConceptModel.load(_write(tmp_path, data))


def test_milestone_without_acceptance_criteria_raises(tmp_path) -> None:
    data = {
        "concepts": [{"id": "a", "prerequisites": [], "lesson_id": ""}],
        "projects": [
            {
                "id": "p",
                "concepts": ["a"],
                "milestones": [{"title": "t", "requirements": "r"}],
            }
        ],
    }
    with pytest.raises(ConceptModelError, match="acceptance criteria"):
        ConceptModel.load(_write(tmp_path, data))


def test_project_with_unknown_concept_raises(tmp_path) -> None:
    data = {
        "concepts": [{"id": "a", "prerequisites": [], "lesson_id": ""}],
        "projects": [
            {
                "id": "p",
                "concepts": ["ghost"],
                "milestones": [
                    {"title": "t", "requirements": "r", "acceptance_criteria": ["c"]}
                ],
            }
        ],
    }
    with pytest.raises(ConceptModelError, match="unknown concept"):
        ConceptModel.load(_write(tmp_path, data))


def test_summary_counts(model: ConceptModel) -> None:
    summary = model.summary()
    assert summary["concepts"] == len(model.concepts)
    assert summary["projects"] == len(model.projects)
    assert summary["milestones"] > 0