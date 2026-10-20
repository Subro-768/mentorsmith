"""The Exam Prep screen.

Two things this screen must never do: call an unverified extraction a
verified past question, and count an attempt it could not grade as a
mistake. The tests below hold it to both, and check that the empty state
appears when there is no course content rather than something invented.
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


def _question(**kwargs) -> ExamQuestion:
    base = {
        "id": "q1",
        "course_id": "26cse1002j-pps",
        "question_text": "Which of the following is a valid C variable name?",
        "question_type": "MCQ",
        "options": ["int age;", "float rate;", "int $x;"],
        "answer": "int age;",
        "unit": 1,
        "source_type": VERIFIED_PYQ,
        "source_file": "CT 1 Set 3.pdf",
        "source_page": 1,
        "source_question_number": "3",
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


@pytest.fixture(scope="module")
def qapp():
    from PyQt6.QtWidgets import QApplication

    existing = QApplication.instance()
    app = existing or QApplication([])
    yield app


@pytest.fixture()
def view(qapp, database, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    import mentorsmith.core.exam as exam
    exam.save_questions([
        _question(id="q1"),
        _question(id="q2", source_type=ORIGINAL_PRACTICE, answer=""),
    ])

    from mentorsmith.ui.exam_view import ExamPrepView

    widget = ExamPrepView(database)
    yield widget
    widget.deleteLater()


class TestTheLabels:
    def test_the_course_is_listed(self, view) -> None:
        assert view.course_combo.count() >= 1
        assert "26CSE1002J" in view.course_combo.currentText()

    def test_the_official_course_details_are_shown(self, view) -> None:
        """The syllabus facts, so a student can check them against it."""
        info = view.course_info.text()
        assert "26CSE1002J" in info
        assert "21CSS101J" in info, "the code the papers carry is not shown"
        assert "2026" in info

    def test_the_verified_course_does_not_say_it_is_unverified(self, view) -> None:
        assert "not yet verified" not in view.course_combo.currentText()

    def test_the_questions_are_listed(self, view) -> None:
        assert view.question_list.count() == 2

    def test_an_unverified_question_does_not_look_verified(self, view) -> None:
        body = view.body.toPlainText()
        assert "Verified past question" not in body
        assert "pending human review" in body.lower()

    def test_the_source_is_shown(self, view) -> None:
        body = view.body.toPlainText()
        assert "CT 1 Set 3.pdf" in body
        assert "p. 1" in body

    def test_the_summary_says_how_many_await_review(self, view) -> None:
        summary = view.bank_summary.text()
        assert "awaiting a human check" in summary
        assert "2" in summary


class TestASession:
    def test_a_session_can_be_started(self, view) -> None:
        view.start_practice()
        assert view.session is not None
        assert view.session_label.text()

    def test_the_options_are_offered(self, view) -> None:
        view.start_practice()
        assert len(view.choice_buttons) == 3

    def test_a_graded_answer_is_marked_right(self, view) -> None:
        view.start_practice()
        # The first question has a key.
        view.choice_buttons[0].setChecked(True)
        view._on_submit()
        assert "Correct" in view.body.toPlainText()

    def test_a_wrong_answer_says_so_and_gives_the_answer(self, view) -> None:
        view.start_practice()
        view.choice_buttons[1].setChecked(True)
        view._on_submit()
        body = view.body.toPlainText()
        assert "Not quite" in body
        assert "int age;" in body

    def test_an_ungraded_answer_says_so(self, view) -> None:
        """The second question has no key, because the paper prints none."""
        view.start_practice()
        view._on_submit()          # first question
        view._on_next()
        view.choice_buttons[0].setChecked(True)
        view._on_submit()
        body = view.body.toPlainText()
        assert "not graded" in body.lower()
        assert "answer key" in body.lower()

    def test_an_ungraded_answer_points_at_the_paper(self, view) -> None:
        view.start_practice()
        view._on_submit()
        view._on_next()
        view.choice_buttons[0].setChecked(True)
        view._on_submit()
        assert "Check it on" in view.body.toPlainText()

    def test_the_results_report_no_score_when_nothing_was_graded(
        self, view
    ) -> None:
        """Both questions lose their key, so nothing in the session grades."""
        import mentorsmith.core.exam as exam

        questions = exam.load_questions("26cse1002j-pps")
        for question in questions:
            question.answer = ""
        exam.save_questions(questions)
        view.refresh_questions()

        view.start_practice()
        view.choice_buttons[0].setChecked(True)
        view._on_submit()
        view._on_next()
        view.choice_buttons[0].setChecked(True)
        view._on_submit()
        view._on_next()
        body = view.body.toPlainText()
        assert "no question in this session could be graded" in body.lower()


class TestMistakes:
    def test_mistakes_need_a_graded_wrong_answer(self, view) -> None:
        view.start_practice()
        view.choice_buttons[1].setChecked(True)   # wrong, and it has a key
        view._on_submit()
        view._on_next()
        view.choice_buttons[0].setChecked(True)   # no key
        view._on_submit()
        view._on_next()
        body = view.body.toPlainText()
        assert "1 mistake" in body
        assert "not counted as mistakes" in body


class TestTheEmptyState:
    def test_no_course_means_no_invented_content(self, qapp, database, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam
        exam.save_questions([])

        from mentorsmith.ui.exam_view import ExamPrepView

        widget = ExamPrepView(database)
        try:
            # The catalogue still has a course, but the bank is empty.
            assert widget.question_list.count() == 0
            assert "0 of 0" in widget.bank_summary.text()
        finally:
            widget.deleteLater()

    def test_the_importer_is_explained_in_the_empty_state(
        self, qapp, database, tmp_path, monkeypatch
    ) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam
        exam.save_questions([])

        from mentorsmith.ui.exam_view import ExamPrepView

        widget = ExamPrepView(database)
        try:
            widget._show_empty()
            body = widget.body.toPlainText()
            assert "import_exam_papers" in body
            assert "not ours to redistribute" in body
        finally:
            widget.deleteLater()
