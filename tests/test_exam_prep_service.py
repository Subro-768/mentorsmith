"""The exam-prep service: sessions, grading, results and mistakes.

The fact that shapes this whole module: **the papers do not print an
answer key.** So most questions cannot be marked automatically, and the
service has to be honest about the difference between "wrong" and "we
cannot tell".

The rule that matters: an ungraded attempt is never counted as a mistake.
A mistake list built from attempts nobody could grade would be a list of
questions the student *might* have got wrong, and "practise my mistakes"
has to mean the ones they actually got wrong.
"""

from __future__ import annotations

import pytest

from mentorsmith.core.db import Database
from mentorsmith.core.exam import (
    ExamQuestion,
    ORIGINAL_PRACTICE,
    PENDING_REVIEW,
    VERIFIED,
    VERIFIED_PYQ,
)
from mentorsmith.services.exam_prep import UNGRADED, ExamPrepService


def _question(**kwargs) -> ExamQuestion:
    base = {
        "id": "q1",
        "course_id": "c1",
        "question_text": "Which of the following is valid?",
        "question_type": "MCQ",
        "options": ["int age;", "float rate;"],
        "answer": "int age;",
        "unit": 1,
        "source_type": ORIGINAL_PRACTICE,
        "verification_status": PENDING_REVIEW,
    }
    base.update(kwargs)
    return ExamQuestion(**base)


@pytest.fixture()
def database():
    db = Database(":memory:")
    db.connect()
    yield db
    db.close()


@pytest.fixture()
def service(database):
    return ExamPrepService(database)


def _bank(service, questions):
    """Put questions in the local bank the service reads."""
    import mentorsmith.core.exam as exam

    exam.save_questions(questions)


class TestFiltering:
    def test_it_filters_by_unit(self, service) -> None:
        _bank(service, [
            _question(id="a", unit=1),
            _question(id="b", unit=2),
        ])
        found = service.questions("c1", unit=2)
        assert [q.id for q in found] == ["b"]

    def test_it_filters_by_source_type(self, service) -> None:
        _bank(service, [
            _question(id="a", source_type=VERIFIED_PYQ),
            _question(id="b", source_type=ORIGINAL_PRACTICE),
        ])
        found = service.questions("c1", source_type=VERIFIED_PYQ)
        assert [q.id for q in found] == ["a"]

    def test_it_filters_by_verification_status(self, service) -> None:
        _bank(service, [
            _question(id="a", verification_status=VERIFIED),
            _question(id="b", verification_status=PENDING_REVIEW),
        ])
        found = service.questions("c1", verification_status=VERIFIED)
        assert [q.id for q in found] == ["a"]

    def test_it_searches_the_question_text(self, service) -> None:
        _bank(service, [
            _question(id="a", question_text="What is a token?"),
            _question(id="b", question_text="What is a pointer?"),
        ])
        found = service.questions("c1", search="pointer")
        assert [q.id for q in found] == ["b"]

    def test_it_searches_the_options(self, service) -> None:
        _bank(service, [_question(id="a", options=["int age;", "float x;"])])
        found = service.questions("c1", search="float")
        assert [q.id for q in found] == ["a"]

    def test_no_filter_matches_everything(self, service) -> None:
        _bank(service, [_question(id="a"), _question(id="b", unit=2)])
        assert len(service.questions("c1")) == 2

    def test_the_counts_break_the_bank_down(self, service) -> None:
        _bank(service, [
            _question(id="a", source_type=VERIFIED_PYQ),
            _question(id="b", source_type=ORIGINAL_PRACTICE),
        ])
        counts = service.counts("c1")
        assert counts["total"] == 2
        assert counts["by_source"][VERIFIED_PYQ] == 1
        assert counts["by_status"][PENDING_REVIEW] == 2


class TestGrading:
    def test_a_correct_answer_is_marked_correct(self, service) -> None:
        _bank(service, [_question(id="a", answer="int age;")])
        session = service.start_session(service.questions("c1"), "c1")
        result = service.submit(session, "int age;")
        assert result.correct is True
        assert result.status == "correct"
        assert result.graded is True

    def test_a_wrong_answer_is_marked_wrong(self, service) -> None:
        _bank(service, [_question(id="a", answer="int age;")])
        session = service.start_session(service.questions("c1"), "c1")
        result = service.submit(session, "float rate;")
        assert result.correct is False
        assert result.status == "wrong"

    def test_comparison_ignores_case_and_spacing(self, service) -> None:
        _bank(service, [_question(id="a", answer="int age;")])
        session = service.start_session(service.questions("c1"), "c1")
        result = service.submit(session, "  INT   age; ")
        assert result.correct is True

    def test_a_question_with_no_key_is_ungraded(self, service) -> None:
        """The papers do not print one, and a guess is not a key."""
        _bank(service, [_question(id="a", answer="")])
        session = service.start_session(service.questions("c1"), "c1")
        result = service.submit(session, "int age;")
        assert result.correct is None
        assert result.status == UNGRADED
        assert result.graded is False

    def test_an_ungraded_result_points_at_the_paper(self, service) -> None:
        _bank(service, [
            _question(id="a", answer="", source_file="CT 1 Set 3.pdf",
                      source_page=2, source_question_number="4")
        ])
        session = service.start_session(service.questions("c1"), "c1")
        result = service.submit(session, "int age;")
        assert result.needs_paper_check is True
        assert "CT 1 Set 3.pdf" in result.paper_pointer
        assert "p. 2" in result.paper_pointer

    def test_skipping_records_nothing_graded(self, service) -> None:
        _bank(service, [_question(id="a", answer="int age;")])
        session = service.start_session(service.questions("c1"), "c1")
        result = service.submit(session, "")
        assert result.correct is None
        assert result.chosen == ""


class TestResults:
    def _run(self, service, answers):
        session = service.start_session(service.questions("c1"), "c1")
        for answer in answers:
            service.submit(session, answer)
        return service.finish(session)

    def test_it_counts_right_and_wrong(self, service) -> None:
        _bank(service, [
            _question(id="a", answer="int age;"),
            _question(id="b", answer="int age;"),
        ])
        results = self._run(service, ["int age;", "float rate;"])
        assert results.correct == 1
        assert results.wrong == 1
        assert results.answered == 2
        assert results.accuracy == 0.5

    def test_ungraded_attempts_are_not_counted_as_wrong(self, service) -> None:
        _bank(service, [_question(id="a", answer="")])
        results = self._run(service, ["int age;"])
        assert results.wrong == 0
        assert results.ungraded == 1
        assert results.accuracy is None

    def test_a_session_with_nothing_gradable_reports_no_accuracy(
        self, service
    ) -> None:
        """A percentage out of zero questions would be a number and no fact."""
        _bank(service, [_question(id="a", answer="")])
        results = self._run(service, ["int age;"])
        assert results.accuracy is None
        assert "not graded" in results.summary() or "no answer key" in results.summary()

    def test_skipped_questions_are_counted_separately(self, service) -> None:
        _bank(service, [
            _question(id="a", answer="int age;"),
            _question(id="b", answer="int age;"),
        ])
        results = self._run(service, ["int age;", ""])
        assert results.skipped == 1
        assert results.answered == 1

    def test_it_breaks_the_result_down_by_unit(self, service) -> None:
        _bank(service, [
            _question(id="a", unit=1, answer="int age;"),
            _question(id="b", unit=2, answer="int age;"),
        ])
        results = self._run(service, ["int age;", "float rate;"])
        assert results.by_unit[1] == [1, 1]
        assert results.by_unit[2] == [0, 1]

    def test_a_unit_with_nothing_graded_is_unmeasured_not_weak(
        self, service
    ) -> None:
        """This is the difference the whole design turns on."""
        _bank(service, [_question(id="a", unit=1, answer="")])
        results = self._run(service, ["int age;"])
        assert results.weak_units() == []
        assert results.unmeasured_units() == [1]

    def test_the_mistakes_are_the_ones_actually_got_wrong(self, service) -> None:
        _bank(service, [
            _question(id="a", answer="int age;"),
            _question(id="b", answer="int age;"),
        ])
        results = self._run(service, ["int age;", "float rate;"])
        assert [m.question.id for m in results.mistakes] == ["b"]

    def test_an_ungraded_attempt_is_not_a_mistake(self, service) -> None:
        _bank(service, [_question(id="a", answer="")])
        results = self._run(service, ["int age;"])
        assert results.mistakes == []


class TestPersistence:
    def test_an_attempt_is_saved(self, service, database) -> None:
        _bank(service, [_question(id="a", answer="int age;")])
        session = service.start_session(service.questions("c1"), "c1")
        service.submit(session, "int age;")
        rows = database.connect().execute(
            "SELECT * FROM exam_attempts"
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["question_id"] == "a"
        assert rows[0]["correct"] == 1

    def test_an_ungraded_attempt_is_saved_as_unknown(self, service, database) -> None:
        _bank(service, [_question(id="a", answer="")])
        session = service.start_session(service.questions("c1"), "c1")
        service.submit(session, "int age;")
        row = database.connect().execute(
            "SELECT * FROM exam_attempts"
        ).fetchone()
        assert row["correct"] is None, "an ungraded attempt must not be 0"

    def test_the_mistake_list_survives_a_restart(self, service, database) -> None:
        _bank(service, [_question(id="a", answer="int age;")])
        session = service.start_session(service.questions("c1"), "c1")
        service.submit(session, "float rate;")
        assert service.mistake_question_ids("c1") == ["a"]
        # A fresh service over the same database - the restart case.
        assert ExamPrepService(database).mistake_question_ids("c1") == ["a"]

    def test_progress_reports_what_was_seen(self, service) -> None:
        _bank(service, [
            _question(id="a", answer="int age;"),
            _question(id="b", answer="int age;"),
        ])
        session = service.start_session(service.questions("c1"), "c1")
        service.submit(session, "int age;")
        progress = service.progress("c1")
        assert progress["attempts"] == 1
        assert progress["questions_seen"] == 1
        assert progress["questions_total"] == 2
        assert progress["accuracy"] == 1.0

    def test_progress_with_nothing_graded_has_no_accuracy(self, service) -> None:
        _bank(service, [_question(id="a", answer="")])
        session = service.start_session(service.questions("c1"), "c1")
        service.submit(session, "int age;")
        assert service.progress("c1")["accuracy"] is None


class TestSessions:
    def test_a_session_cannot_start_empty(self, service) -> None:
        with pytest.raises(ValueError):
            service.start_session([], "c1")

    def test_the_session_walks_the_questions(self, service) -> None:
        _bank(service, [_question(id="a"), _question(id="b")])
        session = service.start_session(service.questions("c1"), "c1")
        assert session.current.id == "a"
        service.submit(session, "int age;")
        assert session.current.id == "b"
        service.submit(session, "int age;")
        assert session.finished is True
        assert session.current is None


class TestTheSchema:
    def test_the_attempt_table_exists_after_connecting(self, database) -> None:
        """Migration 5 creates it; a fresh database runs every migration."""
        names = {
            row["name"] for row in database.connect().execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert "exam_attempts" in names

    def test_an_attempt_can_have_no_grade(self, database) -> None:
        """The column has to allow NULL, or 'ungraded' becomes 'wrong'."""
        database.connect().execute(
            """
            INSERT INTO exam_attempts
                (question_id, course_id, chosen_answer, correct, created_at)
            VALUES ('q', 'c', 'a', NULL, '2026-01-01T00:00:00+00:00')
            """
        )
        database.connect().commit()
        row = database.connect().execute(
            "SELECT correct FROM exam_attempts"
        ).fetchone()
        assert row["correct"] is None
