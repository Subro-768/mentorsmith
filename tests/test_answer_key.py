"""The answer key: where it came from, and what it may be used for.

The papers the learner supplied do not print an answer key, so the bank
could not be graded. The key in ``~/.local/share/mentorsmith/exam/`` was
written from the C language definition and the supplied C textbook.

Two things these tests hold to:

* an answer written from a book is **not an official key**, and the app
  says so wherever it shows one;
* an answer the app cannot match to an option is not silently graded - the
  question is reported as ungradable instead, because a key that does not
  line up with the options would mark the wrong thing.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mentorsmith.core.exam import (
    ExamQuestion,
    MCQ,
    ORIGINAL_PRACTICE,
    PENDING_REVIEW,
    answer_source_label,
    load_questions,
    option_label,
    save_questions,
)


@pytest.fixture()
def bank(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    import mentorsmith.core.exam as exam
    return exam


def _question(**kwargs) -> ExamQuestion:
    base = {
        "id": "q1",
        "course_id": "26cse1002j-pps",
        "question_text": "Which of the following is a keyword in C?",
        "question_type": MCQ,
        "options": ["main", "printf", "double"],
        "answer": "",
        "source_type": ORIGINAL_PRACTICE,
        "verification_status": PENDING_REVIEW,
    }
    base.update(kwargs)
    return ExamQuestion(**base)


class TestTheSourceIsNeverHidden:
    def test_a_book_answer_says_it_is_not_official(self) -> None:
        note = answer_source_label("book")
        assert "not an official key" in note.lower()

    def test_an_assistant_answer_says_it_is_not_official(self) -> None:
        note = answer_source_label("assistant")
        assert "not an official key" in note.lower()

    def test_an_official_key_says_so(self) -> None:
        assert "official" in answer_source_label("official").lower()

    def test_an_unknown_source_has_no_note(self) -> None:
        assert answer_source_label("something else") == ""


class TestGrading:
    def test_an_answer_that_is_an_option_matches(self) -> None:
        question = _question(answer="double")
        assert question.answer_matches_an_option is True
        assert question.answer_label() == "c"

    def test_an_answer_that_is_a_label_matches(self) -> None:
        """A paper that prints its key as a bare letter has to be read."""
        question = _question(answer="b")
        assert question.answer_matches_an_option is True
        assert question.answer_label() == "b"

    def test_an_answer_matching_nothing_does_not(self) -> None:
        question = _question(answer="something else entirely")
        assert question.answer_matches_an_option is False
        assert question.gradable is False

    def test_a_question_with_no_key_is_not_gradable(self) -> None:
        question = _question(answer="")
        assert question.gradable is False

    def test_option_labels_run_a_to_z(self) -> None:
        assert option_label(0) == "a"
        assert option_label(3) == "d"


#: The learner's real data directory, captured before the conftest fixture
#: redirects it. The tests below are about the key as it is *installed*, so
#: they have to look at the real one - and skip when there is none.
REAL_DATA_HOME = (
    os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
)


@pytest.fixture()
def installed_key(monkeypatch):
    """The question bank as installed in the learner's own directory."""
    monkeypatch.setenv("XDG_DATA_HOME", REAL_DATA_HOME)
    import mentorsmith.core.exam as exam
    questions = exam.load_questions()
    if not questions:
        pytest.skip("no question bank is installed in the data directory")
    return questions


class TestTheShippedKey:
    """The key as it stands in the learner's own data directory."""

    def test_every_imported_question_has_an_answer(self, installed_key) -> None:
        """The imported bank is keyed; the bundled one is graded by running."""
        from mentorsmith.core.exam import load_questions

        imported = load_questions(local_only=True)
        if not imported:
            pytest.skip("no imported bank is installed")
        unanswered = [q.id for q in imported if not q.answer.strip()]
        assert not unanswered, f"questions with no answer: {unanswered}"

    def test_every_answer_says_where_it_came_from(self, installed_key) -> None:
        from mentorsmith.core.exam import load_questions

        questions = load_questions(local_only=True)
        if not questions:
            pytest.skip("no imported bank is installed")
        missing = [q.id for q in questions if not q.answer_source]
        assert not missing, f"answers with no source: {missing[:5]}"

    def test_no_answer_claims_to_be_official(self, installed_key) -> None:
        """A key written from a book is not an official key."""
        from mentorsmith.core.exam import load_questions

        questions = load_questions(local_only=True)
        if not questions:
            pytest.skip("no imported bank is installed")
        claimed = [q.id for q in questions if q.answer_source == "official"]
        assert not claimed, (
            "an answer is marked as an official key without an official source"
        )

    def test_most_of_the_bank_is_gradable(self, installed_key) -> None:
        """A handful are not, because the paper printed its key inline.

        Those are reported rather than hidden, but the bank as a whole has to
        be usable - a key where almost nothing can be marked is not a key.
        """
        from mentorsmith.core.exam import load_questions

        questions = load_questions(local_only=True)
        if not questions:
            pytest.skip("no imported bank is installed")
        gradable = [q for q in questions if q.gradable]
        assert len(gradable) >= len(questions) * 0.9, (
            f"only {len(gradable)} of {len(questions)} questions are gradable"
        )
