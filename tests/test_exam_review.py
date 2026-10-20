"""The human-check workflow.

This is the step that makes the whole labelling scheme mean something. A
question extracted from a paper says "pending human review" until somebody
compares it with their own copy and marks it checked. After that it can be
called a verified past question, it can be graded, and it can count as a
mistake.

The tests below also cover the awkward case the workflow runs into: the
answer the student reads in the paper is sometimes *not* among the options
the importer extracted, because the extraction garbled them. That has to
be flagged, not silently accepted and not silently rejected.
"""

from __future__ import annotations

import pytest

from mentorsmith.core.db import Database
from mentorsmith.core.exam import (
    ExamDataError,
    ExamQuestion,
    PENDING_REVIEW,
    VERIFIED,
    VERIFIED_PYQ,
    mark_verified,
    pending_questions,
    review_report,
    set_answer,
)
from mentorsmith.services.exam_prep import ExamPrepService


def _question(**kwargs) -> ExamQuestion:
    base = {
        "id": "q1",
        # The course id the catalogue actually uses, so the screen's
        # review queue finds these questions.
        "course_id": "26cse1002j-pps",
        "question_text": "Which of the following is valid?",
        "question_type": "MCQ",
        "options": ["int age;", "float rate;"],
        "answer": "",
        "source_type": VERIFIED_PYQ,
        "source_file": "CT 1 Set 3.pdf",
        "source_page": 1,
        "source_question_number": "3",
        "verification_status": PENDING_REVIEW,
    }
    base.update(kwargs)
    return ExamQuestion(**base)


@pytest.fixture()
def bank(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    import mentorsmith.core.exam as exam

    exam.save_questions([
        _question(id="q1"),
        _question(id="q2", question_text="Another one?"),
    ])
    return exam


class TestMarkingVerified:
    def test_it_marks_the_question_verified(self, bank) -> None:
        updated = mark_verified("q1", answer="int age;")
        assert updated is not None
        assert updated.verification_status == VERIFIED
        assert updated.verified_by
        assert updated.verified_at

    def test_it_records_the_answer_at_the_same_time(self, bank) -> None:
        mark_verified("q1", answer="int age;")
        stored = [q for q in bank.load_questions() if q.id == "q1"][0]
        assert stored.answer == "int age;"

    def test_it_records_the_explanation(self, bank) -> None:
        mark_verified("q1", answer="int age;", explanation="Because a name.")
        stored = [q for q in bank.load_questions() if q.id == "q1"][0]
        assert stored.explanation == "Because a name."

    def test_it_bumps_the_version(self, bank) -> None:
        before = [q for q in bank.load_questions() if q.id == "q1"][0]
        mark_verified("q1", answer="int age;")
        after = [q for q in bank.load_questions() if q.id == "q1"][0]
        assert after.version == before.version + 1

    def test_an_unknown_question_is_not_silently_ignored(self, bank) -> None:
        assert mark_verified("nope", answer="x") is None

    def test_it_leaves_the_others_alone(self, bank) -> None:
        mark_verified("q1", answer="int age;")
        other = [q for q in bank.load_questions() if q.id == "q2"][0]
        assert other.verification_status == PENDING_REVIEW

    def test_the_pending_list_shrinks(self, bank) -> None:
        assert len(pending_questions()) == 2
        mark_verified("q1", answer="int age;")
        assert len(pending_questions()) == 1


class TestSettingAnAnswer:
    def test_it_sets_the_answer_without_verifying(self, bank) -> None:
        updated = set_answer("q1", "int age;")
        assert updated is not None
        assert updated.answer == "int age;"
        assert updated.verification_status == PENDING_REVIEW


class TestGradability:
    def test_a_question_with_no_key_is_not_gradable(self, bank) -> None:
        question = [q for q in bank.load_questions() if q.id == "q1"][0]
        assert question.gradable is False

    def test_a_question_whose_key_is_an_option_is_gradable(self, bank) -> None:
        mark_verified("q1", answer="int age;")
        question = [q for q in bank.load_questions() if q.id == "q1"][0]
        assert question.gradable is True

    def test_a_key_that_is_not_an_option_is_not_gradable(self, bank) -> None:
        """The extraction of the options is suspect, so it cannot be marked."""
        mark_verified("q1", answer="int $x;")
        question = [q for q in bank.load_questions() if q.id == "q1"][0]
        assert question.answer_matches_an_option is False
        assert question.gradable is False

    def test_matching_ignores_case_and_spacing(self, bank) -> None:
        mark_verified("q1", answer="  INT   age; ")
        question = [q for q in bank.load_questions() if q.id == "q1"][0]
        assert question.answer_matches_an_option is True

    def test_it_is_not_an_error_to_save_such_an_answer(self, bank) -> None:
        """The reviewer is establishing the truth, not filling in a form."""
        mark_verified("q1", answer="something else entirely")
        question = [q for q in bank.load_questions() if q.id == "q1"][0]
        assert question.answer == "something else entirely"


class TestTheServiceRefusesToMarkAnUngradableQuestion:
    def test_it_reports_no_grade(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        exam.save_questions([_question(id="q1")])
        mark_verified("q1", answer="not an option")

        db = Database(":memory:")
        db.connect()
        service = ExamPrepService(db)
        session = service.start_session(
            service.questions("26cse1002j-pps", local_only=True), "26cse1002j-pps"
        )
        result = service.submit(session, "int age;")
        assert result.correct is None
        assert result.graded is False

    def test_a_graded_question_still_marks(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        exam.save_questions([_question(id="q1")])
        mark_verified("q1", answer="int age;")

        db = Database(":memory:")
        db.connect()
        service = ExamPrepService(db)
        session = service.start_session(
            service.questions("26cse1002j-pps", local_only=True),
            "26cse1002j-pps",
        )
        result = service.submit(session, "int age;")
        assert result.correct is True


class TestTheReport:
    def test_it_lists_the_ungradable_questions(self, bank) -> None:
        mark_verified("q1", answer="not an option")
        report = review_report()
        assert len(report["ungradable"]) == 1
        assert report["ungradable"][0].id == "q1"


class TestTheScreen:
    @pytest.fixture(scope="module")
    def qapp(self):
        from PyQt6.QtWidgets import QApplication

        existing = QApplication.instance()
        app = existing or QApplication([])
        yield app

    @pytest.fixture()
    def view(self, qapp, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        exam.save_questions([
            _question(id="q1"),
            _question(id="q2", question_text="Another one?"),
        ])

        from mentorsmith.ui.exam_view import ExamPrepView

        db = Database(":memory:")
        db.connect()
        widget = ExamPrepView(db)
        yield widget
        widget.deleteLater()

    def test_the_queue_is_the_pending_questions(self, view) -> None:
        view.start_review()
        assert "of 2" in view.session_label.text()

    def test_it_shows_that_the_question_is_not_checked(self, view) -> None:
        view.start_review()
        assert "not yet checked" in view.body.toPlainText()

    def test_it_shows_the_source_to_check_against(self, view) -> None:
        view.start_review()
        body = view.body.toPlainText()
        assert "CT 1 Set 3.pdf" in body
        assert "p. 1" in body

    def test_saving_marks_it_checked_and_moves_on(self, view) -> None:
        view.start_review()
        view.review_answer.setText("int age;")
        view._on_review_save()
        assert "of 2" in view.session_label.text()
        assert "question 2 of" in view.session_label.text()

        import mentorsmith.core.exam as exam

        stored = [q for q in exam.load_questions() if q.id == "q1"][0]
        assert stored.verification_status == VERIFIED

    def test_skipping_leaves_it_pending(self, view) -> None:
        view.start_review()
        view._on_review_skip()
        import mentorsmith.core.exam as exam

        stored = [q for q in exam.load_questions() if q.id == "q1"][0]
        assert stored.verification_status == PENDING_REVIEW

    def test_an_empty_queue_says_so(self, view) -> None:
        import mentorsmith.core.exam as exam

        # The review queue covers the imported bank only, so clearing it is
        # enough to empty the queue.
        for question in exam.load_questions(local_only=True):
            mark_verified(question.id, answer=question.options[0])
        view.start_review()
        assert "Nothing waiting" in view.session_label.text()
