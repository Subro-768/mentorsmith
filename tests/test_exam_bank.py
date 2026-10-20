"""Exam preparation: provenance, validation, grading and the review report.

The whole point of this module is that a student can tell what a question
is. These tests hold three things to that:

* a question cannot be *labelled* a verified past question without a
  human having checked it against a source;
* a course cannot claim to be verified without the metadata that makes the
  claim checkable;
* an attempt that could not be graded is never counted as a mistake.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mentorsmith.core.exam import (
    ExamDataError,
    ExamQuestion,
    OFFICIAL_SAMPLE,
    ORIGINAL_PRACTICE,
    PENDING_REVIEW,
    PREDICTED_PRACTICE,
    Course,
    Topic,
    VERIFIED,
    VERIFIED_PYQ,
    load_courses,
    merge_questions,
    normalise_text,
    review_report,
    save_questions,
)


def _question(**kwargs) -> ExamQuestion:
    base = {
        "id": "q1",
        "course_id": "c1",
        "question_text": "Which of the following is a valid C variable name?",
        "question_type": "MCQ",
        "options": ["int age;", "float rate;", "int $x;"],
        "answer": "int age;",
        "source_type": ORIGINAL_PRACTICE,
        "verification_status": PENDING_REVIEW,
    }
    base.update(kwargs)
    return ExamQuestion(**base)


class TestTheSourceTypeIsNeverConflated:
    def test_a_pending_past_question_is_not_labelled_verified(self) -> None:
        question = _question(source_type=VERIFIED_PYQ)
        assert question.display_label != "Verified past question"
        assert "pending human review" in question.display_label.lower()

    def test_a_verified_past_question_is_labelled_as_one(self) -> None:
        question = _question(
            source_type=VERIFIED_PYQ,
            verification_status=VERIFIED,
            source_file="CT 1 Set 3.pdf",
            source_page=1,
            source_question_number="3",
        )
        assert question.display_label == "Verified past question"

    def test_a_pending_sample_is_not_labelled_official(self) -> None:
        question = _question(source_type=OFFICIAL_SAMPLE)
        assert question.display_label != "Official sample question"
        assert "pending" in question.display_label.lower()

    def test_an_original_question_never_says_past(self) -> None:
        question = _question(source_type=ORIGINAL_PRACTICE)
        assert "past" not in question.display_label.lower()
        assert question.is_past_question is False

    def test_a_predicted_question_says_it_is_a_prediction(self) -> None:
        question = _question(source_type=PREDICTED_PRACTICE)
        label = question.display_label.lower()
        assert "predicted" in label
        assert "not a guaranteed" in label

    def test_a_predicted_question_is_never_a_past_question(self) -> None:
        assert _question(source_type=PREDICTED_PRACTICE).is_past_question is False

    def test_a_rejected_question_says_so(self) -> None:
        question = _question(
            source_type=VERIFIED_PYQ, verification_status="REJECTED"
        )
        assert "rejected" in question.display_label.lower()

    def test_only_a_past_question_is_a_past_question(self) -> None:
        assert _question(source_type=VERIFIED_PYQ).is_past_question is True
        assert _question(source_type=OFFICIAL_SAMPLE).is_past_question is False


class TestQuestionValidation:
    def test_a_question_with_no_text_is_rejected(self) -> None:
        with pytest.raises(ExamDataError):
            _question(question_text="   ").validate()

    def test_an_unknown_source_type_is_rejected(self) -> None:
        with pytest.raises(ExamDataError):
            _question(source_type="MAYBE").validate()

    def test_an_unknown_verification_status_is_rejected(self) -> None:
        with pytest.raises(ExamDataError):
            _question(verification_status="PROBABLY").validate()

    def test_a_verified_past_question_needs_its_source(self) -> None:
        question = _question(
            source_type=VERIFIED_PYQ, verification_status=VERIFIED,
        )
        with pytest.raises(ExamDataError) as excinfo:
            question.validate()
        assert "source_file" in str(excinfo.value)

    def test_a_verified_past_question_with_a_source_passes(self) -> None:
        _question(
            source_type=VERIFIED_PYQ, verification_status=VERIFIED,
            source_file="CT 1 Set 3.pdf", source_page=1,
            source_question_number="3",
        ).validate()

    def test_a_predicted_question_needs_a_reason(self) -> None:
        question = _question(
            source_type=PREDICTED_PRACTICE, verification_status=VERIFIED,
        )
        with pytest.raises(ExamDataError) as excinfo:
            question.validate()
        assert "reason" in str(excinfo.value)

    def test_a_multiple_choice_question_needs_options(self) -> None:
        with pytest.raises(ExamDataError):
            _question(options=["only one"]).validate()

    def test_an_answer_outside_the_options_is_allowed_but_flagged(self) -> None:
        """The reviewer is establishing the truth, not filling in a form.

        An answer that is not among the *extracted* options usually means
        the extraction garbled the options, not that the answer is wrong.
        So it is accepted and flagged, and the question cannot be graded
        until the options are put right.
        """
        question = _question(answer="not an option")
        question.validate()
        assert question.answer_matches_an_option is False
        assert question.gradable is False

    def test_an_answer_outside_the_options_still_fails_when_verified(self) -> None:
        """A checked question with a key nobody could pick is not usable."""
        question = _question(
            answer="not an option",
            verification_status=VERIFIED,
            source_file="CT 1 Set 3.pdf", source_page=1,
            source_question_number="3",
        )
        question.validate()  # allowed, and flagged
        assert question.gradable is False

    def test_a_missing_answer_is_allowed_while_awaiting_review(self) -> None:
        """The papers do not print a key, so this has to be legal."""
        _question(answer="", verification_status=PENDING_REVIEW).validate()

    def test_a_verified_question_must_have_an_answer(self) -> None:
        question = _question(
            answer="", verification_status=VERIFIED, source_type=ORIGINAL_PRACTICE
        )
        with pytest.raises(ExamDataError) as excinfo:
            question.validate()
        assert "answer" in str(excinfo.value)

    def test_negative_marks_are_rejected(self) -> None:
        with pytest.raises(ExamDataError):
            _question(marks=-1).validate()


class TestCourseValidation:
    def _course(self, **kwargs) -> Course:
        base = {
            "id": "c1",
            "title": "Programming for Problem Solving",
            "course_code": "21CSS101J",
            "syllabus_source": "course material",
            "source_files": ["CT 1 Set 3.pdf"],
        }
        base.update(kwargs)
        return Course(**base)

    def test_a_verified_course_needs_its_metadata(self) -> None:
        course = self._course(
            verification_status=VERIFIED, course_code="", source_files=[]
        )
        with pytest.raises(ExamDataError) as excinfo:
            course.validate()
        assert "course_code" in str(excinfo.value)

    def test_a_verified_course_with_metadata_passes(self) -> None:
        self._course(verification_status=VERIFIED).validate()

    def test_a_pending_course_needs_nothing(self) -> None:
        self._course(verification_status=PENDING_REVIEW, course_code="").validate()

    def test_two_topics_with_the_same_id_are_rejected(self) -> None:
        course = self._course(topics=[
            Topic(id="u1", title="One"),
            Topic(id="u1", title="Also one"),
        ])
        with pytest.raises(ExamDataError):
            course.validate()

    def test_the_units_are_the_distinct_topic_units(self) -> None:
        course = self._course(topics=[
            Topic(id="a", title="A", unit=1),
            Topic(id="b", title="B", unit=1),
            Topic(id="c", title="C", unit=2),
        ])
        assert course.units == [1, 2]


class TestTheCatalogue:
    def test_it_loads(self) -> None:
        courses = load_courses()
        assert courses, "the catalogue is empty"

    def test_the_shipped_course_is_the_one_in_the_papers(self) -> None:
        """Course code and title, read from the official syllabus."""
        courses = load_courses()
        course = courses[0]
        assert course.course_code == "26CSE1002J"
        assert course.title == "Programming for Problem Solving"
        assert course.institution.startswith("SRM Institute")
        assert course.semester == "I / I"

    def test_it_records_the_earlier_code_the_papers_carry(self) -> None:
        """The papers predate the 2026 regulation, and the code changed."""
        course = load_courses()[0]
        assert "21CSS101J" in course.previous_course_codes
        assert course.course_code != "21CSS101J"

    def test_it_names_the_regulation_and_its_approval(self) -> None:
        course = load_courses()[0]
        assert "2026" in course.regulation
        assert course.academic_council

    def test_it_records_the_course_structure(self) -> None:
        course = load_courses()[0]
        assert course.credits == 3
        assert course.lecture_hours == 2
        assert course.tutorial_hours == 0
        assert course.practical_hours == 2
        assert course.sessions_per_unit == 12

    def test_it_records_the_assessment_split(self) -> None:
        """The syllabus states it, so it is not left blank."""
        course = load_courses()[0]
        assessment = course.assessment
        assert assessment["continuous_assessment_percent"] == 50
        assert assessment["summative_final_percent"] == 50
        assert assessment["ca1_written_test_percent"] == 15
        assert assessment["ca2_written_test_or_examination_percent"] == 15
        assert assessment["ca3_practice_percent"] == 20
        assert assessment["final_theory_percent"] == 30
        assert assessment["final_practice_percent"] == 30

    def test_it_records_the_learning_outcomes(self) -> None:
        course = load_courses()[0]
        assert len(course.outcomes) == 5
        assert all(o.startswith("CLO-") for o in course.outcomes)

    def test_it_records_the_references(self) -> None:
        course = load_courses()[0]
        assert course.references
        assert any("NPTEL" in r for r in course.references)

    def test_it_is_verified_because_the_syllabus_verifies_it(self) -> None:
        """An official syllabus is what a verified course needs."""
        course = load_courses()[0]
        assert course.verification_status == VERIFIED

    def test_its_topics_have_sources(self) -> None:
        for topic in load_courses()[0].topics:
            assert topic.source, f"{topic.id} has no source"

    def test_a_broken_catalogue_is_reported(self, tmp_path) -> None:
        path = tmp_path / "courses.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ExamDataError):
            load_courses(path)


class TestTheBank:
    def test_the_bank_is_not_in_the_repository(self) -> None:
        """Past papers are the learner's, and are not ours to ship."""
        root = Path(__file__).resolve().parent.parent
        assert not (root / "mentorsmith" / "data" / "exam" / "questions.json").exists()

    def test_saving_writes_to_the_data_directory(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        path = exam.save_questions([_question()])
        assert path.exists()
        assert path.parent.name == "exam"

    def test_the_bank_is_not_world_readable(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        path = exam.save_questions([_question()])
        assert path.stat().st_mode & 0o077 == 0, "the bank is readable by others"

    def test_loading_a_broken_bank_is_reported(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        path = exam.bank_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(ExamDataError):
            exam.load_questions()


class TestMerging:
    def _bank(self, tmp_path, monkeypatch):
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        return exam

    def test_a_new_question_is_added(self, tmp_path, monkeypatch) -> None:
        exam = self._bank(tmp_path, monkeypatch)
        result = exam.merge_questions([_question()])
        assert result["added"] == 1
        assert len(exam.load_questions()) == 1

    def test_the_same_question_twice_is_added_once(self, tmp_path, monkeypatch) -> None:
        exam = self._bank(tmp_path, monkeypatch)
        exam.merge_questions([_question()])
        result = exam.merge_questions([_question()])
        assert result["added"] == 0
        assert result["already_present"] == 1
        assert len(exam.load_questions()) == 1

    def test_the_same_text_under_another_id_is_a_duplicate(
        self, tmp_path, monkeypatch
    ) -> None:
        """The course's own banks overlap, and the importer must not."""
        exam = self._bank(tmp_path, monkeypatch)
        exam.merge_questions([_question(id="a")])
        result = exam.merge_questions([_question(id="b")])
        assert result["duplicates"] == 1
        assert result["added"] == 0
        assert len(exam.load_questions()) == 1

    def test_whitespace_does_not_defeat_duplicate_detection(
        self, tmp_path, monkeypatch
    ) -> None:
        exam = self._bank(tmp_path, monkeypatch)
        exam.merge_questions([_question(id="a")])
        result = exam.merge_questions([
            _question(id="b", question_text="Which  of the following   is a valid C variable name?")
        ])
        assert result["duplicates"] == 1


class TestTheReviewReport:
    def test_it_lists_what_needs_a_human(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        exam.save_questions([
            _question(id="a", answer=""),
            _question(id="b", source_type=VERIFIED_PYQ, answer=""),
        ])
        report = exam.review_report()
        assert report["total"] == 2
        assert len(report["pending_review"]) == 2
        assert len(report["no_answer"]) == 2

    def test_it_finds_duplicates(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam

        exam.save_questions([_question(id="a"), _question(id="b")])
        report = exam.review_report()
        assert report["duplicate_groups"]


class TestNormaliseText:
    def test_case_and_spacing_are_ignored(self) -> None:
        assert normalise_text("Hello   World") == normalise_text("hello world")
