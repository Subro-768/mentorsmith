"""The timed mock, and recovering a session after a restart.

Two things the brief asks for that are easy to get wrong:

* the mock format must be one the **learner** chose, or a pattern that is
  actually verified. The catalogue carries the Cycle Test header - 25
  marks, 50 minutes, Part A 10 x 1 - and that is a CT, not the
  end-semester paper. Inventing an end-semester format on no evidence
  would be the exact thing this module exists to prevent.
* a session must survive the app closing, and the clock must keep running
  while it is closed. A timed practice run that quietly gains time when
  the app is shut is not a timed run.
"""

from __future__ import annotations

import time

import pytest

from mentorsmith.core.db import Database
from mentorsmith.core.exam import ExamQuestion, PENDING_REVIEW, VERIFIED_PYQ
from mentorsmith.services.exam_prep import ExamPrepService

COURSE = "26cse1002j-pps"


def _question(index: int) -> ExamQuestion:
    return ExamQuestion(
        id=f"q{index}", course_id=COURSE,
        question_text=f"Question {index}?",
        question_type="MCQ", options=["a", "b"], answer="",
        source_type=VERIFIED_PYQ, verification_status=PENDING_REVIEW,
    )


@pytest.fixture()
def bank(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    import mentorsmith.core.exam as exam

    exam.save_questions([_question(i) for i in range(10)])
    return exam


@pytest.fixture()
def database():
    db = Database(":memory:")
    db.connect()
    yield db
    db.close()


@pytest.fixture()
def service(database, bank):
    return ExamPrepService(database)


class TestTheMock:
    def test_it_builds_a_session_of_the_requested_size(self, service) -> None:
        mock = service.start_mock(COURSE, count=4)
        assert len(mock.questions) == 4
        assert mock.timed is False

    def test_it_can_be_timed(self, service) -> None:
        mock = service.start_mock(COURSE, count=3, minutes=10)
        assert mock.timed is True
        assert mock.time_limit == 600

    def test_the_title_says_it_is_a_practice_format(self, service) -> None:
        mock = service.start_mock(COURSE, count=3, minutes=10)
        assert "practice mock" in mock.title.lower()
        assert "10 minute" in mock.title

    def test_it_can_draw_from_one_source_only(self, service) -> None:
        mock = service.start_mock(COURSE, count=50, source_type=VERIFIED_PYQ)
        assert mock.questions
        assert all(q.source_type == VERIFIED_PYQ for q in mock.questions)

    def test_the_count_is_capped_by_what_exists(self, service) -> None:
        mock = service.start_mock(COURSE, count=500)
        assert len(mock.questions) == 10

    def test_the_clock_counts_down(self, service) -> None:
        mock = service.start_mock(COURSE, count=2, minutes=1)
        assert service.seconds_left(mock) <= 60
        assert service.seconds_left(mock) > 50

    def test_an_expired_session_is_expired(self, service) -> None:
        mock = service.start_mock(COURSE, count=2, minutes=1)
        mock.deadline = time.monotonic() - 1
        assert service.expired(mock) is True

    def test_an_untimed_session_never_expires(self, service) -> None:
        mock = service.start_mock(COURSE, count=2)
        assert service.expired(mock) is False
        assert service.seconds_left(mock) == 0

    def test_a_mock_with_no_questions_is_refused(self, service, bank) -> None:
        bank.save_questions([])
        with pytest.raises(ValueError):
            service.start_mock(COURSE, count=5)


class TestSessionRecovery:
    def test_an_unfinished_session_is_recovered(self, service) -> None:
        mock = service.start_mock(COURSE, count=4)
        service.save_session(mock)
        recovered = service.open_session(COURSE)
        assert recovered is not None
        assert recovered.id == mock.id
        assert len(recovered.questions) == 4

    def test_the_position_is_kept(self, service) -> None:
        mock = service.start_mock(COURSE, count=4)
        service.submit(mock, "a")
        recovered = service.open_session(COURSE)
        assert recovered.index == 1

    def test_a_finished_session_is_not_offered_again(self, service) -> None:
        mock = service.start_mock(COURSE, count=4)
        service.close_session(mock)
        assert service.open_session(COURSE) is None

    def test_the_clock_keeps_running_while_the_app_is_closed(
        self, service
    ) -> None:
        """A timed run must not gain time by being closed."""
        mock = service.start_mock(COURSE, count=4, minutes=10)
        service.save_session(mock)
        # Pretend the session started two minutes ago.
        import sqlite3

        from datetime import datetime, timedelta, timezone

        started = datetime.now(timezone.utc) - timedelta(minutes=2)
        service.database.connect().execute(
            "UPDATE exam_sessions SET started_at = ?", (started.isoformat(),)
        )
        service.database.connect().commit()
        recovered = service.open_session(COURSE)
        assert recovered is not None
        left = service.seconds_left(recovered)
        assert left < 600 - 100, "the clock restarted instead of continuing"

    def test_a_recovered_session_keeps_its_questions(self, service) -> None:
        mock = service.start_mock(COURSE, count=3)
        service.save_session(mock)
        recovered = service.open_session(COURSE)
        assert [q.id for q in recovered.questions] == [q.id for q in mock.questions]

    def test_a_session_for_another_course_is_not_offered(self, service) -> None:
        mock = service.start_mock(COURSE, count=3)
        service.save_session(mock)
        assert service.open_session("some-other-course") is None


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

        exam.save_questions([_question(i) for i in range(5)])

        from mentorsmith.ui.exam_view import ExamPrepView

        db = Database(":memory:")
        db.connect()
        widget = ExamPrepView(db)
        yield widget
        widget.deleteLater()

    def test_the_mock_button_exists(self, view) -> None:
        assert "mock" in view.mock_button.text().lower()

    def test_the_dialog_says_the_format_is_the_learners(self, view) -> None:
        from mentorsmith.ui.exam_view import MockDialog

        dialog = MockDialog(10, view)
        try:
            text = dialog.findChildren(type(dialog))  # not used
            labels = [
                child.text() for child in dialog.findChildren(__import__(
                    "PyQt6.QtWidgets", fromlist=["QLabel"]).QLabel
                )
            ]
            joined = " ".join(labels)
            assert "not the exam" in joined.lower()
            assert "you set" in joined.lower() or "yours to choose" in joined.lower()
        finally:
            dialog.deleteLater()

    def test_the_resume_button_appears_when_there_is_a_session(
        self, view
    ) -> None:
        mock = view.service.start_mock("26cse1002j-pps", count=3)
        view.service.save_session(mock)
        view._offer_resume()
        assert view.resume_button.isVisibleTo(view) is True

    def test_resuming_picks_the_session_up(self, view) -> None:
        mock = view.service.start_mock("26cse1002j-pps", count=3)
        view.service.save_session(mock)
        view.resume_session()
        assert view.session is not None
        assert view.session.id == mock.id

    def test_no_session_means_no_resume_button(self, view) -> None:
        view._offer_resume()
        assert view.resume_button.isVisibleTo(view) is False
