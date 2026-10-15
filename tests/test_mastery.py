"""Mastery labels and the evidence that must back every one of them."""

from __future__ import annotations

from mentorsmith.core.mastery import (
    LABEL_ORDER,
    REVIEW_PREFIX,
    assess,
    assess_many,
    is_review_attempt,
    label_rank,
    mastered_concepts,
)


def evidence(**kwargs) -> dict:
    """An evidence dict with sensible zero defaults."""
    base = {
        "attempts": 0,
        "correct": 0,
        "incorrect": 0,
        "hints_used": 0,
        "independent": 0,
        "first_try_correct": 0,
        "freeform_attempts": 0,
        "freeform_correct": 0,
        "novel_attempts": 0,
        "error_categories": {},
        "exercise_types": {},
    }
    base.update(kwargs)
    return base


# ----------------------------------------------------------------------
# Labels
# ----------------------------------------------------------------------
def test_no_attempts_is_not_started_not_needs_review() -> None:
    """Doing nothing and struggling are different states."""
    result = assess("c", evidence())
    assert result.label == "not_started"
    assert result.score == 0.0
    assert "No graded attempts" in " ".join(result.evidence)


def test_all_correct_with_several_attempts_is_strong() -> None:
    result = assess(
        "c",
        evidence(attempts=4, correct=4, incorrect=0, first_try_correct=1),
    )
    assert result.label == "strong"
    assert result.is_mastered


def test_single_correct_attempt_is_not_strong() -> None:
    """One lucky correct answer proves very little."""
    result = assess("c", evidence(attempts=1, correct=1, first_try_correct=1))
    assert result.label != "strong"
    assert not result.is_mastered


def test_all_wrong_is_needs_review() -> None:
    result = assess("c", evidence(attempts=3, correct=0, incorrect=3))
    assert result.label == "needs_review"
    assert not result.is_mastered


def test_mixed_results_are_developing() -> None:
    result = assess(
        "c",
        evidence(attempts=4, correct=3, incorrect=1, first_try_correct=1),
    )
    assert result.label in {"developing", "strong"}
    assert result.label != "needs_review"


# ----------------------------------------------------------------------
# Evidence requirements
# ----------------------------------------------------------------------
def test_every_label_carries_evidence() -> None:
    cases = [
        evidence(),
        evidence(attempts=1, correct=1, first_try_correct=1),
        evidence(attempts=3, correct=0, incorrect=3),
        evidence(attempts=4, correct=3, incorrect=1, first_try_correct=1),
    ]
    for case in cases:
        result = assess("c", case)
        assert result.evidence, f"{result.label} produced no evidence"


def test_evidence_names_the_actual_counts() -> None:
    result = assess("c", evidence(attempts=5, correct=3, incorrect=2))
    joined = " ".join(result.evidence)
    assert "3 of 5" in joined


def test_score_is_clamped_to_zero_one() -> None:
    heavy_hints = assess(
        "c",
        evidence(attempts=10, correct=0, incorrect=10, hints_used=50,
                 freeform_attempts=3, freeform_correct=0),
    )
    assert 0.0 <= heavy_hints.score <= 1.0
    assert heavy_hints.score == 0.0


# ----------------------------------------------------------------------
# Repeated errors
# ----------------------------------------------------------------------
def test_repeated_error_category_downgrades_a_strong_label() -> None:
    """A recurring misunderstanding outweighs a high overall score."""
    result = assess(
        "c",
        evidence(
            attempts=5,
            correct=5,
            first_try_correct=1,
            error_categories={"off_by_one": 3},
        ),
    )
    assert result.label == "needs_review"
    assert any("repeating problem" in item for item in result.evidence)
    assert any("Downgraded" in item for item in result.evidence)


def test_two_occurrences_do_not_downgrade() -> None:
    result = assess(
        "c",
        evidence(
            attempts=5,
            correct=5,
            first_try_correct=1,
            error_categories={"off_by_one": 2},
        ),
    )
    assert result.label == "strong"


# ----------------------------------------------------------------------
# Free-form explanation signal
# ----------------------------------------------------------------------
def test_correct_explanation_helps() -> None:
    result = assess(
        "c",
        evidence(attempts=4, correct=4, first_try_correct=1,
                 freeform_attempts=2, freeform_correct=2),
    )
    assert any("own words" in item for item in result.evidence)
    assert result.score >= 0.75


def test_failed_explanation_counts_against_mastery() -> None:
    """Code that works but cannot be explained is not understanding."""
    without = assess("c", evidence(attempts=4, correct=4, first_try_correct=1))
    with_bad = assess(
        "c",
        evidence(attempts=4, correct=4, first_try_correct=1,
                 freeform_attempts=2, freeform_correct=0),
    )
    assert with_bad.score < without.score


# ----------------------------------------------------------------------
# Hints and novelty
# ----------------------------------------------------------------------
def test_hints_reduce_confidence() -> None:
    unaided = assess("c", evidence(attempts=4, correct=4, first_try_correct=1))
    aided = assess(
        "c", evidence(attempts=4, correct=4, first_try_correct=1, hints_used=3)
    )
    assert aided.score < unaided.score


def test_novel_variation_gives_a_small_boost() -> None:
    # Headroom needed: the score is clamped to 1.0, so a perfect record would
    # hide the difference.
    plain = assess("c", evidence(attempts=4, correct=3, incorrect=1, first_try_correct=1))
    novel = assess(
        "c",
        evidence(attempts=4, correct=3, incorrect=1, first_try_correct=1,
                 novel_attempts=1),
    )
    assert novel.score > plain.score
    assert any("unfamiliar variation" in item for item in novel.evidence)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def test_review_attempts_are_recognised() -> None:
    assert is_review_attempt(f"{REVIEW_PREFIX}predict-output")
    assert not is_review_attempt("predict-output")


def test_review_attempts_are_mentioned_in_evidence() -> None:
    result = assess(
        "c",
        evidence(
            attempts=4,
            correct=4,
            first_try_correct=1,
            exercise_types={f"{REVIEW_PREFIX}find-a-bug": 1, "predict-output": 3},
        ),
    )
    assert any("deliberate review" in item for item in result.evidence)


def test_label_order_and_rank() -> None:
    assert LABEL_ORDER[0] == "not_started"
    assert LABEL_ORDER[-1] == "strong"
    assert label_rank("not_started") < label_rank("strong")
    assert label_rank("unknown") == -1


def test_assess_many_and_mastered_set() -> None:
    assessments = assess_many(
        {
            "a": evidence(attempts=4, correct=4, first_try_correct=1),
            "b": evidence(attempts=2, correct=0, incorrect=2),
            "c": evidence(),
        }
    )
    assert set(assessments) == {"a", "b", "c"}
    assert mastered_concepts(assessments) == {"a"}


def test_explain_renders_readable_text() -> None:
    result = assess("c", evidence(attempts=2, correct=1, incorrect=1))
    text = result.explain()
    assert "c:" in text
    assert "  - " in text


def test_to_dict_is_serialisable() -> None:
    import json

    result = assess("c", evidence(attempts=2, correct=1, incorrect=1))
    json.dumps(result.to_dict())


def test_blocking_prerequisites_are_carried() -> None:
    result = assess("memory", evidence(attempts=2, correct=2, first_try_correct=1))
    result.blocking_prerequisites = ["pointers"]
    assert result.to_dict()["blocking_prerequisites"] == ["pointers"]