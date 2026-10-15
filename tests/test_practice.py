"""End-to-end practice sessions: hint tracking, grading and recording.

These exercise the real toolchain against a real compiler. They are the tests
that prove the Phase 2 loop actually works rather than merely composing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mentorsmith.compiler.toolchain import Toolchain
from mentorsmith.core.db import Database
from mentorsmith.core.exercises import load_bank
from mentorsmith.services.insights import build_report
from mentorsmith.services.practice import PracticeSession
from mentorsmith.core.concepts import load_model
from mentorsmith.core.curriculum import load_lessons

pytestmark = pytest.mark.skipif(
    not Toolchain().detect().available, reason="no C++ compiler"
)


@pytest.fixture()
def bank():
    lessons = {l.id for l in load_lessons()}
    model = load_model(valid_lesson_ids=lessons)
    return load_bank(known_concepts=set(model.concepts), valid_lesson_ids=lessons)


@pytest.fixture()
def session_for(bank, database, toolchain):
    def make(exercise_id: str, is_review: bool = False) -> PracticeSession:
        exercise = bank.get(exercise_id)
        assert exercise is not None, f"unknown exercise {exercise_id}"
        return PracticeSession(
            database=database, toolchain=toolchain, exercise=exercise,
            is_review=is_review,
        )

    return make


WORKING = "#include <iostream>\nint main(){ int t=5,c=2; std::cout << (double)t/c << \"\\n\"; return 0; }\n"
BROKEN = "#include <iostream>\nint main(){ int t=5,c=2; std::cout << t/c << \"\\n\"; return 0; }\n"
NOT_COMPILING = "int main() { int x = ; }\n"


# ======================================================================
# Deterministic path
# ======================================================================
def test_correct_code_is_graded_correct(session_for, database) -> None:
    outcome = session_for("types-fix-division").submit(WORKING)
    assert outcome.correct
    assert outcome.grade.graded_by == "deterministic"
    assert outcome.session.stage == "resolved"


def test_wrong_output_is_not_correct(session_for) -> None:
    outcome = session_for("types-fix-division").submit(BROKEN)
    assert not outcome.correct
    assert outcome.grade.error_category == "wrong_output"
    assert outcome.grade.diff


def test_non_compiling_code_reports_a_compile_failure(session_for) -> None:
    outcome = session_for("types-fix-division").submit(NOT_COMPILING)
    assert not outcome.correct
    assert outcome.grade.error_category == "compile_failure"
    assert outcome.diagnosis is not None


def test_predict_output_grades_real_output(session_for, bank) -> None:
    """Run the exercise's own code and compare its real output."""
    exercise = bank.get("types-int-division")
    outcome = session_for("types-int-division").submit(exercise.code)
    assert outcome.correct, outcome.grade.diff


def test_attempt_is_recorded_with_concept(session_for, database) -> None:
    session_for("types-fix-division").submit(WORKING)
    attempts = database.attempts_for_concept("types")
    assert len(attempts) == 1
    assert attempts[0]["correct"] == 1
    assert attempts[0]["exercise_type"] == "find-a-bug"
    assert attempts[0]["independent"] == 1


def test_repeat_attempts_accumulate(session_for, database) -> None:
    session = session_for("types-fix-division")
    session.submit(BROKEN)
    session.submit(WORKING)
    assert len(database.attempts_for_concept("types")) == 2


# ======================================================================
# Hint tracking
# ======================================================================
def test_hint_is_counted(session_for) -> None:
    session = session_for("types-fix-division")
    session.submit(NOT_COMPILING)
    session.hint()
    assert session.session.hints_used == 1


def test_hints_mark_an_attempt_as_assisted(session_for, database) -> None:
    session = session_for("types-fix-division")
    session.submit(NOT_COMPILING)
    session.hint()
    session.submit(WORKING)
    # attempts_for_concept returns newest first.
    attempt = database.attempts_for_concept("types")[0]
    assert attempt["correct"] == 1
    assert attempt["hints_used"] == 1
    assert attempt["independent"] == 0


def test_solve_without_ai_refuses_hints(session_for) -> None:
    session = session_for("io-solve-no-ai")
    assert not session.can_hint()
    message = session.hint()
    assert "without" in message.lower()
    assert session.session.hints_used == 0


def test_hints_do_not_count_for_forbidden_exercises(session_for) -> None:
    session = session_for("io-solve-no-ai")
    for _ in range(3):
        session.hint()
    assert session.session.hints_used == 0


# ======================================================================
# Guided debugging flow
# ======================================================================
def test_first_failure_offers_a_hint(session_for) -> None:
    session = session_for("types-fix-division")
    outcome = session.submit(NOT_COMPILING)
    assert outcome.session.stage == "hint"
    hint = session.hint()
    assert hint
    assert outcome.session.stage == "retry"


def test_repeated_failure_escalates(session_for) -> None:
    session = session_for("types-fix-division")
    session.submit(NOT_COMPILING)
    outcome = session.submit(NOT_COMPILING)
    assert outcome.session.stage == "escalate"
    assert outcome.session.escalations == 1


def test_second_hint_asks_the_learner_for_reasoning(session_for) -> None:
    session = session_for("types-fix-division")
    session.submit(NOT_COMPILING)
    session.hint()
    second = session.hint()
    assert "evidence" in second.lower()


def test_fix_produces_a_follow_up_question(session_for) -> None:
    session = session_for("types-fix-division")
    session.submit(NOT_COMPILING)
    outcome = session.submit(WORKING)
    assert outcome.correct
    assert "?" in outcome.follow_up


def test_substantial_help_is_flagged_when_escalated(session_for) -> None:
    session = session_for("types-fix-division")
    session.submit(NOT_COMPILING)
    session.submit(NOT_COMPILING)
    assert session.session.needed_substantial_help


def test_state_snapshot_is_serialisable(session_for) -> None:
    import json

    session = session_for("types-fix-division")
    session.submit(NOT_COMPILING)
    json.dumps(session.state())


# ======================================================================
# Review variants
# ======================================================================
def test_review_attempt_is_marked_in_the_type(session_for, database) -> None:
    session = session_for("types-fix-division", is_review=True)
    session.submit(WORKING)
    attempt = database.attempts_for_concept("types")[0]
    assert attempt["exercise_type"].startswith("review:")


def test_review_attempt_feeds_the_regression_detector(
    session_for, database
) -> None:
    from mentorsmith.core.revision import compute_review_regressions

    normal = session_for("types-fix-division")
    normal.submit(WORKING)
    review = session_for("types-fix-division", is_review=True)
    review.submit(BROKEN)

    history = list(reversed(database.attempts_for_concept("types")))
    regressions = compute_review_regressions(history)
    assert regressions.get("types", 0) >= 1


# ======================================================================
# Interpretive path
# ======================================================================
def test_rubric_prompt_contains_the_rubric(session_for) -> None:
    session = session_for("types-explain-division")
    prompt = session.rubric_prompt("because integers truncate")
    assert "mentions integer division" in prompt
    assert "because integers truncate" in prompt


def test_interpretive_record_is_labelled_and_counted(session_for, database) -> None:
    session = session_for("types-explain-division")
    outcome = session.record_interpretive(
        "because integer division truncates", verdict="correct", feedback="yes"
    )
    assert outcome.correct
    assert outcome.grade.graded_by == "interpretive"
    attempt = database.attempts_for_concept("types")[0]
    assert attempt["graded_by"] == "interpretive"
    assert attempt["exercise_type"] == "explain-code"


def test_partial_explanation_does_not_count_as_correct(session_for) -> None:
    session = session_for("types-explain-division")
    outcome = session.record_interpretive("sort of", verdict="partial", feedback="close")
    assert not outcome.correct
    assert outcome.grade.error_category == "explanation_incomplete"


# ======================================================================
# It all feeds the dashboard
# ======================================================================
def test_history_changes_the_dashboard_report(session_for, database) -> None:
    lessons = {l.id for l in load_lessons()}
    model = load_model(valid_lesson_ids=lessons)
    bank = load_bank(known_concepts=set(model.concepts), valid_lesson_ids=lessons)

    before = build_report(database, model, bank)
    assert before.total_attempts == 0
    assert before.next_activity_reason

    session_for("types-fix-division").submit(BROKEN)
    session_for("types-fix-division").submit(WORKING)

    after = build_report(database, model, bank)
    assert after.total_attempts == 2
    # One wrong then one right is genuine progress, not a mastery claim and
    # not a "never started" concept.
    types_row = next(c for c in after.concepts if c.concept_id == "types")
    assert types_row.attempts == 2
    assert types_row.correct == 1
    assert types_row.label in {"developing", "needs_review"}
    assert types_row.label != "strong"
    assert types_row.label != "not_started"
    assert after.recommendations
    assert "graded attempts" in after.next_activity_reason


def test_dashboard_excludes_chats_and_time(session_for, database) -> None:
    lessons = {l.id for l in load_lessons()}
    model = load_model(valid_lesson_ids=lessons)
    bank = load_bank(known_concepts=set(model.concepts), valid_lesson_ids=lessons)

    # Record activity that must NOT count as evidence of learning.
    database.record_activity("chat", "types", "sent a message")
    report = build_report(database, model, bank)
    assert report.total_attempts == 0
    assert report.label_counts.get("not_started") == len(model.concepts)
    assert "not counted" in report.not_evidence_note