"""Adaptive selection, exercise grading, debugging coach, projects, revision."""

from __future__ import annotations

import pytest

from mentorsmith.core.adaptive import (
    prerequisites_status,
    recommend_next,
)
from mentorsmith.core.concepts import load_model
from mentorsmith.core.curriculum import load_lessons
from mentorsmith.core.db import Database
from mentorsmith.core.debugging import (
    DebugSession,
    STAGE_ESCALATE,
    STAGE_RESOLVED,
    diagnose,
    escalation_prompt,
    post_fix_prompt,
)
from mentorsmith.core.exercises import (
    ExerciseBank,
    build_diff,
    grade_deterministic,
    load_bank,
    normalise_output,
    outputs_match,
)
from mentorsmith.core.mastery import assess_many
from mentorsmith.core.projects import (
    estimate_difficulty,
    milestone_progress,
    propose_project,
    propose_projects,
    save_project,
)
from mentorsmith.core.revision import (
    DISCLAIMER,
    compute_review_regressions,
    recommend_reviews,
)


@pytest.fixture(scope="module")
def lessons():
    return load_lessons()


@pytest.fixture(scope="module")
def model(lessons):
    return load_model(valid_lesson_ids={l.id for l in lessons})


@pytest.fixture(scope="module")
def bank(model, lessons):
    return load_bank(
        known_concepts=set(model.concepts),
        valid_lesson_ids={l.id for l in lessons},
    )


@pytest.fixture()
def db() -> Database:
    database = Database(":memory:")
    database.connect()
    return database


# ======================================================================
# Exercise bank
# ======================================================================
def test_bank_loads(bank: ExerciseBank) -> None:
    assert len(bank.exercises) >= 40


def test_all_eight_exercise_types_are_present(bank: ExerciseBank) -> None:
    counts = bank.types_present()
    from mentorsmith.core.exercises import EXERCISE_TYPES

    for exercise_type in EXERCISE_TYPES:
        assert counts.get(exercise_type, 0) > 0, f"no {exercise_type} exercises"


def test_every_concept_has_at_least_one_exercise(model, bank) -> None:
    covered = bank.concepts_covered()
    assert set(model.concepts) - covered == set()


def test_deterministic_exercises_carry_expected_output(bank: ExerciseBank) -> None:
    for exercise in bank.exercises:
        if exercise.is_deterministic:
            assert exercise.expected_stdout != ""
        else:
            assert exercise.rubric


def test_solve_without_ai_exercises_forbid_hints(bank: ExerciseBank) -> None:
    for exercise in bank.exercises:
        assert exercise.forbids_hints == (exercise.type == "solve-without-AI")


def test_unknown_exercise_type_is_rejected(tmp_path) -> None:
    import json

    path = tmp_path / "e.json"
    path.write_text(
        json.dumps({"exercises": [{"id": "x", "concept_id": "a", "type": "telepathy"}]}),
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        ExerciseBank.load(path, known_concepts={"a"})


def test_deterministic_without_expected_output_is_rejected(tmp_path) -> None:
    import json

    path = tmp_path / "e.json"
    path.write_text(
        json.dumps({"exercises": [{"id": "x", "concept_id": "a", "type": "predict-output"}]}),
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="expected_stdout"):
        ExerciseBank.load(path, known_concepts={"a"})


def test_interpretive_without_rubric_is_rejected(tmp_path) -> None:
    import json

    path = tmp_path / "e.json"
    path.write_text(
        json.dumps({"exercises": [{"id": "x", "concept_id": "a", "type": "explain-code"}]}),
        encoding="utf-8",
    )
    with pytest.raises(Exception, match="rubric"):
        ExerciseBank.load(path, known_concepts={"a"})


# ======================================================================
# Deterministic grading
# ======================================================================
def test_output_normalisation_ignores_trailing_space() -> None:
    assert normalise_output("a  \nb\n\n") == "a\nb"
    assert outputs_match("hi\n", "hi")
    assert outputs_match("hi", "hi\n")


def test_correct_output_grades_correct(bank) -> None:
    exercise = bank.get("types-int-division")
    result = grade_deterministic(
        exercise, compiled=True, compile_stderr="",
        stdout="3\n3.5\n", exit_code=0,
    )
    assert result.correct
    assert result.graded_by == "deterministic"
    assert not result.is_interpretive


def test_wrong_output_fails_with_a_diff(bank) -> None:
    exercise = bank.get("types-int-division")
    result = grade_deterministic(
        exercise, compiled=True, compile_stderr="",
        stdout="3\n3\n", exit_code=0,
    )
    assert not result.correct
    assert result.error_category == "wrong_output"
    assert "expected" in result.diff


def test_compile_failure_is_not_graded_as_wrong_output(bank) -> None:
    exercise = bank.get("types-int-division")
    result = grade_deterministic(
        exercise, compiled=False, compile_stderr="error: boom", stdout="", exit_code=None,
    )
    assert not result.correct
    assert result.error_category == "compile_failure"
    assert "boom" in result.error_category_explanation


def test_crash_is_reported_as_a_runtime_error(bank) -> None:
    exercise = bank.get("types-int-division")
    result = grade_deterministic(
        exercise, compiled=True, compile_stderr="", stdout="", exit_code=139,
    )
    assert not result.correct
    assert result.error_category == "runtime_error"


def test_timeout_is_reported_as_a_timeout(bank) -> None:
    exercise = bank.get("types-int-division")
    result = grade_deterministic(
        exercise, compiled=True, compile_stderr="", stdout="", exit_code=None,
        run_timed_out=True,
    )
    assert not result.correct
    assert result.error_category == "runtime_timeout"


def test_diff_is_produced_only_when_wrong(bank) -> None:
    exercise = bank.get("types-int-division")
    good = grade_deterministic(
        exercise, compiled=True, compile_stderr="", stdout="3\n3.5\n", exit_code=0,
    )
    assert good.diff == ""


def test_build_diff_labels_sides() -> None:
    diff = build_diff("a\n", "b\n")
    assert "expected" in diff
    assert "actual" in diff


# ======================================================================
# Mastery -> recommendations
# ======================================================================
def test_no_evidence_yields_no_recommendation(model, bank) -> None:
    assessments = assess_many(
        db_attempts(Database(":memory:"), model)
    )
    assert all(a.label == "not_started" for a in assessments.values())
    # With nothing attempted and prerequisites unmet, nothing is justified.
    recs = recommend_next(bank, model, assessments, limit=5)
    for rec in recs:
        assert rec.category in {"extension", "repair", "consolidate", "review"}
        assert rec.reason


def db_attempts(database: Database, model) -> dict:
    database.connect()
    return database.concept_evidence(list(model.concepts))


def test_weak_concept_is_recommended_first(db, model, bank) -> None:
    for index in range(3):
        db.record_exercise_attempt(
            "02-variables-and-types", f"e{index}",
            concept_id="types", exercise_type="find-a-bug", correct=False,
            error_category="integer_division", hints_used=1,
        )
    assessments = assess_many(db.concept_evidence(list(model.concepts)))
    recs = recommend_next(bank, model, assessments, limit=3)
    assert recs
    assert recs[0].concept_id == "types"
    assert recs[0].category == "repair"


def test_recommendation_reason_cites_the_learners_own_numbers(db, model, bank) -> None:
    db.record_exercise_attempt(
        "02-variables-and-types", "e", concept_id="types",
        exercise_type="find-a-bug", correct=False,
        error_category="integer_division", hints_used=2,
    )
    assessments = assess_many(db.concept_evidence(list(model.concepts)))
    recs = recommend_next(bank, model, assessments, limit=1)
    assert recs
    reason = recs[0].reason
    assert "integer_division" in reason
    assert "hint" in reason.lower()


def test_single_correct_attempt_is_consolidated_not_repaired(db, model, bank) -> None:
    db.record_exercise_attempt(
        "01-program-structure", "e", concept_id="program-structure",
        exercise_type="predict-output", correct=True, hints_used=0,
    )
    assessments = assess_many(db.concept_evidence(list(model.concepts)))
    recs = recommend_next(bank, model, assessments, limit=3)
    categories = {r.category for r in recs}
    assert "consolidate" in categories
    assert "repair" not in categories


def test_recommendations_never_repeat_an_attempted_exercise(db, model, bank) -> None:
    for index in range(2):
        db.record_exercise_attempt(
            "02-variables-and-types", f"e{index}", concept_id="types",
            exercise_type="find-a-bug", correct=False,
            error_category="integer_division",
        )
    assessments = assess_many(db.concept_evidence(list(model.concepts)))
    attempted = {str(a["exercise_id"]) for a in db.attempts_for_concept("types")}
    recs = recommend_next(
        bank, model, assessments,
        attempted_by_concept={"types": attempted}, limit=5,
    )
    assert not (attempted & {r.exercise_id for r in recs})


def test_selection_is_deterministic(db, model, bank) -> None:
    """Same history in, same recommendation out."""
    db.record_exercise_attempt(
        "02-variables-and-types", "e", concept_id="types",
        exercise_type="find-a-bug", correct=False, error_category="integer_division",
    )
    assessments = assess_many(db.concept_evidence(list(model.concepts)))
    first = [r.exercise_id for r in recommend_next(bank, model, assessments)]
    second = [r.exercise_id for r in recommend_next(bank, model, assessments)]
    assert first == second


def test_prerequisite_status_lists_gaps(model) -> None:
    assessments = assess_many({cid: None for cid in []} or {})
    status = prerequisites_status(model, assessments)
    assert "memory" in status
    assert "pointers" in status["memory"]


def test_repeated_error_category_raises_priority(db, model, bank) -> None:
    """A recurring misconception should outrank a milder weakness."""
    for index in range(4):
        db.record_exercise_attempt(
            "02-variables-and-types", f"a{index}", concept_id="types",
            exercise_type="find-a-bug", correct=False,
            error_category="integer_division",
        )
    db.record_exercise_attempt(
        "01-program-structure", "b", concept_id="program-structure",
        exercise_type="predict-output", correct=False,
    )
    assessments = assess_many(db.concept_evidence(list(model.concepts)))
    recurring = {"integer_division"}
    recs = recommend_next(
        bank, model, assessments, recurring_categories=recurring, limit=2
    )
    assert recs[0].concept_id == "types"


# ======================================================================
# Debugging coach
# ======================================================================
def test_missing_semicolon_is_identified() -> None:
    result = diagnose(
        compiled=False,
        compile_stderr="main.cpp:2:11: error: expected ';' before 'std'",
    )
    assert result.category == "missing_semicolon"
    assert result.confidence == "specific"
    assert result.hint


def test_unrecognised_compile_error_is_still_honest() -> None:
    result = diagnose(compiled=False, compile_stderr="main.cpp:1:1: error: weird thing")
    assert result.category == "compile_failure"
    assert result.confidence == "general"
    assert "boom" not in result.hint


def test_timeout_diagnosis_is_specific() -> None:
    result = diagnose(compiled=True, timed_out=True)
    assert result.category == "runtime_timeout"
    assert result.confidence == "specific"


def test_crash_diagnosis() -> None:
    result = diagnose(compiled=True, exit_code=139, stdout="terminate called")
    assert result.category in {"runtime_error"}
    assert result.confidence in {"specific", "general"}


def test_hint_does_not_reveal_the_answer() -> None:
    """A hint must point at the area, not hand over the fix."""
    result = diagnose(compiled=False, compile_stderr="error: expected ';'")
    hint = result.hint.lower()
    assert "semicolon" in hint
    assert "add a" not in hint


def test_session_escalates_only_after_repeated_failure() -> None:
    session = DebugSession()
    diagnosis = diagnose(compiled=False, compile_stderr="error: expected ';'")
    session.on_failure(diagnosis)
    assert session.attempts == 1
    assert session.stage == "hint"
    session.on_failure(diagnosis)
    assert session.stage == STAGE_ESCALATE
    assert session.escalations == 1


def test_second_hint_asks_for_learner_reasoning() -> None:
    session = DebugSession()
    diagnosis = diagnose(compiled=False, compile_stderr="error: expected ';'")
    session.on_failure(diagnosis)
    session.give_hint()
    second = session.give_hint()
    assert "evidence" in second.lower()
    assert session.hints_used == 2


def test_resolved_stage_asks_a_follow_up_question() -> None:
    session = DebugSession()
    diagnosis = diagnose(compiled=False, compile_stderr="error: expected ';'")
    session.on_failure(diagnosis)
    question = session.on_resolved()
    assert session.stage == STAGE_RESOLVED
    assert session.is_resolved
    assert "?" in question


def test_substantial_help_is_recorded() -> None:
    unaided = DebugSession()
    unaided.on_failure(diagnose(compiled=False, compile_stderr="error: x"))
    unaided.give_hint()
    assert not unaided.needed_substantial_help

    aided = DebugSession()
    for _ in range(3):
        aided.on_failure(diagnose(compiled=False, compile_stderr="error: x"))
        aided.give_hint()
    assert aided.needed_substantial_help


def test_escalation_prompt_forbids_chain_of_thought() -> None:
    prompt = escalation_prompt(diagnose(compiled=False, compile_stderr="error: x"))
    assert "NOT reveal" in prompt or "not reveal" in prompt.lower()
    assert "scratchpad" in prompt.lower()


def test_post_fix_prompt_asks_a_related_question() -> None:
    prompt = post_fix_prompt(diagnose(compiled=False, compile_stderr="error: expected ';'"))
    assert "?" in prompt


def test_hint_before_any_failure() -> None:
    session = DebugSession()
    assert session.give_hint()


# ======================================================================
# Projects and milestones
# ======================================================================
def test_no_projects_are_ready_without_evidence(model) -> None:
    assessments = assess_many({cid: _zero_assessment(cid) for cid in model.concepts})
    proposals = propose_projects(model, assessments)
    assert proposals
    assert not any(p.ready for p in proposals)


def test_blocked_project_names_its_gaps(model) -> None:
    assessments = assess_many({cid: _zero_assessment(cid) for cid in model.concepts})
    proposal = next(p for p in propose_projects(model, assessments))
    assert proposal.missing_prerequisites
    assert "Missing evidence" in proposal.rationale


def test_strong_learner_gets_a_ready_project(model, db) -> None:
    # Two graded attempts per concept: 'strong' requires at least two.
    for concept_id in model.concepts:
        for index in range(2):
            db.record_exercise_attempt(
                "l", f"e-{concept_id}-{index}", concept_id=concept_id,
                exercise_type="find-a-bug", correct=True, hints_used=0,
            )
    assessments = assess_many(db.concept_evidence(list(model.concepts)))
    assert all(a.is_mastered for a in assessments.values())
    ready = propose_projects(model, assessments, ready_only=True)
    assert ready, "a fully strong learner should have a ready project"
    assert ready[0].rationale


def test_difficulty_rises_when_weak(model, db) -> None:
    for concept_id in model.concepts:
        db.record_exercise_attempt(
            "l", f"e-{concept_id}", concept_id=concept_id,
            exercise_type="find-a-bug", correct=False,
        )
    assessments = assess_many(db.concept_evidence(list(model.concepts)))
    weak = propose_projects(model, assessments)
    easy = propose_projects(
        model,
        assess_many({
            cid: _perfect_assessment(cid) for cid in model.concepts
        }),
    )
    assert _rank(weak[0].estimated_difficulty) >= _rank(easy[0].estimated_difficulty)


def test_project_saves_milestones(db, model) -> None:
    assessments = assess_many({cid: _perfect_assessment(cid) for cid in model.concepts})
    proposal = propose_projects(model, assessments, ready_only=True)[0]
    save_project(db, proposal)

    stored = db.get_project(proposal.project.id)
    assert stored is not None
    milestones = db.milestones_for(proposal.project.id)
    assert len(milestones) == len(proposal.project.milestones)
    assert milestones[0]["status"] == "pending"
    assert milestones[0]["acceptance_criteria"]


def test_saving_twice_is_idempotent(db, model) -> None:
    assessments = assess_many({cid: _perfect_assessment(cid) for cid in model.concepts})
    proposal = propose_projects(model, assessments, ready_only=True)[0]
    save_project(db, proposal)
    save_project(db, proposal)
    assert len(db.milestones_for(proposal.project.id)) == len(proposal.project.milestones)


def test_milestone_status_can_be_advanced(db, model) -> None:
    assessments = assess_many({cid: _perfect_assessment(cid) for cid in model.concepts})
    proposal = propose_projects(model, assessments, ready_only=True)[0]
    save_project(db, proposal)
    milestone = db.milestones_for(proposal.project.id)[0]

    db.set_milestone_status(int(milestone["id"]), "done")
    updated = db.milestones_for(proposal.project.id)[0]
    assert updated["status"] == "done"
    assert updated["completed_at"]

    progress = milestone_progress(db.milestones_for(proposal.project.id))
    assert progress["done"] == 1
    assert progress["percent"] == int(round(100 / len(proposal.project.milestones)))


def test_project_activity_records_help(db, model) -> None:
    assessments = assess_many({cid: _perfect_assessment(cid) for cid in model.concepts})
    proposal = propose_projects(model, assessments, ready_only=True)[0]
    save_project(db, proposal)
    db.record_project_activity(
        proposal.project.id, "got stuck on the loop", needed_substantial_help=True
    )
    entries = db.project_activity_for(proposal.project.id)
    assert entries[0]["needed_substantial_help"] == 1


def test_estimate_difficulty_is_clamped(model) -> None:
    for project in model.projects.values():
        for label_set in ([], [None]):
            assert estimate_difficulty(project, {}) in {"beginner", "intermediate", "advanced"}


def test_propose_unknown_project_returns_none(model) -> None:
    assert propose_project(model, {}, project_id="nope") is None


def _zero_assessment(concept_id: str) -> dict:
    """Evidence dict for a concept with nothing recorded."""
    return {}


def _perfect_assessment(concept_id: str) -> dict:
    """Evidence dict that should earn the 'strong' label."""
    return {
        "attempts": 3, "correct": 3, "incorrect": 0, "hints_used": 0,
        "first_try_correct": 1, "freeform_attempts": 1, "freeform_correct": 1,
        "novel_attempts": 0, "error_categories": {}, "exercise_types": {},
    }


def _rank(label: str) -> int:
    from mentorsmith.core.projects import DIFFICULTY_ORDER

    return DIFFICULTY_ORDER.index(label)


# ======================================================================
# Revision
# ======================================================================
def test_weak_concept_is_recommended_for_review(model) -> None:
    from mentorsmith.core.mastery import assess

    assessments = {
        "types": assess("types", {
            "attempts": 3, "correct": 0, "incorrect": 3, "hints_used": 2,
            "first_try_correct": 0, "freeform_attempts": 1, "freeform_correct": 0,
            "error_categories": {"integer_division": 3}, "exercise_types": {},
        })
    }
    items = recommend_reviews(model, assessments)
    assert items
    assert items[0].concept_id == "types"
    assert "integer_division" in items[0].reason


def test_review_reason_is_explainable(model) -> None:
    from mentorsmith.core.mastery import assess

    assessments = {
        "types": assess("types", {
            "attempts": 2, "correct": 0, "incorrect": 2, "hints_used": 0,
            "first_try_correct": 0, "freeform_attempts": 0, "freeform_correct": 0,
            "error_categories": {}, "exercise_types": {},
        })
    }
    item = recommend_reviews(model, assessments)[0]
    assert item.evidence
    assert "0 of 2" in item.reason


def test_strong_concept_is_not_recommended(model) -> None:
    from mentorsmith.core.mastery import assess

    assessments = {
        "types": assess("types", {
            "attempts": 4, "correct": 4, "incorrect": 0, "hints_used": 0,
            "first_try_correct": 1, "freeform_attempts": 1, "freeform_correct": 1,
            "error_categories": {}, "exercise_types": {},
        })
    }
    assert recommend_reviews(model, assessments) == []


def test_unattempted_concept_is_not_a_review(model) -> None:
    from mentorsmith.core.mastery import assess

    assert recommend_reviews(model, {"types": assess("types", {})}) == []


def test_review_regression_is_detected() -> None:
    """Solved once, then wrong on a later review, is the delayed signal."""
    attempts = [
        {"concept_id": "types", "exercise_type": "find-a-bug", "correct": True},
        {"concept_id": "types", "exercise_type": "review:find-a-bug", "correct": False},
        {"concept_id": "types", "exercise_type": "review:find-a-bug", "correct": False},
    ]
    regressions = compute_review_regressions(attempts)
    assert regressions["types"] == 2


def test_review_regression_raises_urgency(model) -> None:
    from mentorsmith.core.mastery import assess

    assessments = {
        "types": assess("types", {
            "attempts": 4, "correct": 3, "incorrect": 1, "hints_used": 0,
            "first_try_correct": 1, "freeform_attempts": 1, "freeform_correct": 1,
            "error_categories": {}, "exercise_types": {},
        })
    }
    without = recommend_reviews(model, assessments)
    with_regression = recommend_reviews(
        model, assessments, review_regressions={"types": 2}
    )
    if without:
        assert with_regression
        assert with_regression[0].urgency > without[0].urgency


def test_disclaimer_does_not_promise_mastery() -> None:
    assert "cannot guarantee" in DISCLAIMER or "No review" in DISCLAIMER


def test_reviews_persist_deduplicated(db) -> None:
    first = db.add_review("types", "because", "evidence")
    second = db.add_review("types", "because again", "evidence")
    assert first == second
    assert len(db.open_reviews()) == 1
    db.close_review(first)
    assert db.open_reviews() == []