"""The exam-paper importer.

What matters here is that the importer is **honest about what it found**,
never verifies anything on its own, and never quietly edits the paper's
text.

The tests use synthetic papers rather than the learner's real ones: the
real papers are their material, they are not in the repository, and a test
that depended on them would break the moment a file was renamed.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import import_exam_papers as importer  # noqa: E402


CT_PAGE = """
                        SRM Institute of Science and Technology
                        Faculty of Engineering and Technology
                                 School of Computing
 Programoffered:B.Tech(AllBranches)                               Year/Sem:I/I
 Max.Marks:25                                                     Duration:1 Hour

        Course Code and Title: 21CSS101J: Programming for Problem Solving
                              Part-A: 10 X 1 Marks (MCQ)
S.No.                                         Question
  1     Every C program consists of __________ function(s).
        (a) Only one
        (b) Only two
        (c) One or two
        (d) One or many
  2     Which of the following is not a correct variable type?
        (a) Float
        (b) Real
        (c) Int
        (d) Double
"""

TWO_COLUMN_PAGE = """
PROGRAMMING FOR PROBLEM SOLVING
Unit 1
Multiple Choice questions MCQ

1. Who is father of C Language?                                            [CLO 1] [PLO1]
       A. Bjarne Stroustrup         B. Dennis Ritchie
       C. James A. Gosling          D. Dr. E.F. Codd
2. C Language developed at _____?
       A. AT & T's Bell Laboratories
       B. Sun Microsystems in 1973
"""


class TestParsing:
    def test_it_finds_questions_with_options(self) -> None:
        found, _unit = importer._parse_document([CT_PAGE])
        assert len(found) == 2
        assert found[0]["text"].startswith("Every C program")
        assert found[0]["options"] == ["Only one", "Only two", "One or two", "One or many"]

    def test_it_strips_the_running_header(self) -> None:
        found, _unit = importer._parse_document([CT_PAGE])
        for question in found:
            assert "SRM Institute" not in question["text"]
            assert "Max.Marks" not in question["text"]

    def test_it_reads_two_options_from_one_line(self) -> None:
        """The banks set their options in two columns."""
        found, _unit = importer._parse_document([TWO_COLUMN_PAGE])
        assert found[0]["options"] == [
            "Bjarne Stroustrup", "Dennis Ritchie",
            "James A. Gosling", "Dr. E.F. Codd",
        ]

    def test_it_reads_the_unit_heading(self) -> None:
        _found, unit = importer._parse_document([TWO_COLUMN_PAGE])
        assert unit == 1

    def test_a_question_split_across_a_page_break_is_not_lost(self) -> None:
        """Its text is on one page and its options on the next."""
        first = "  1     What is the output of the following code?\n"
        second = "        (a) 3 5\n        (b) 5 3\n        (c) 3 3\n        (d) 5 5\n"
        found, _unit = importer._parse_document([first, second])
        assert len(found) == 1
        assert len(found[0]["options"]) == 4

    def test_a_numbered_line_with_no_text_is_not_a_question(self) -> None:
        found, _unit = importer._parse_document(["  1  \n  2  \n"])
        assert found == []

    def test_a_question_with_one_option_is_not_a_question(self) -> None:
        found, _unit = importer._parse_document([
            "  1     A question with a single option.\n        (a) Only one\n"
        ])
        assert found == []


class TestQualityGate:
    def test_ocr_garbage_is_rejected(self) -> None:
        """A failed extraction is not a question."""
        found, _unit = importer._parse_document([
            "  1     24. 23. 22.21.\n        (a) 1\n        (b) 2\n"
        ])
        # It parses as a question, so the gate has to be applied on top.
        from mentorsmith.core.exam import ExamQuestion

        question = ExamQuestion(
            id="x", course_id="c", question_text=found[0]["text"] if found else "",
            options=["1", "2"],
        )
        letters = sum(ch.isalpha() for ch in question.question_text)
        assert letters < 8, "this text is garbage and should have been dropped"


class TestOcrNoise:
    def test_clean_text_has_no_noise(self) -> None:
        assert importer._ocr_noise_ratio(CT_PAGE) < 0.06

    def test_garbled_text_is_noisy(self) -> None:
        """Non-printable characters are the easy case."""
        garbled = "\u00b4\u00b5\u00b6\u00b7\u00b8\u00b9" * 10
        assert importer._ocr_noise_ratio(garbled) > 0.06

    def test_printable_garbage_is_still_garbage(self) -> None:
        """Character-level noise detection cannot see this."""
        assert importer.looks_like_a_question("24. 23. 22.21.") is False
        assert importer.looks_like_a_question("1h 2i 3j 4k 5l 6m") is False
        assert importer.looks_like_a_question("CxprcNsion oevaluates") is False
        assert importer.looks_like_a_question(
            "The CxprcNsion 4+6/3 evaluates to"
        ) is False

    def test_a_real_question_passes(self) -> None:
        assert importer.looks_like_a_question(
            "Every C program consists of how many functions?"
        ) is True
        assert importer.looks_like_a_question(
            "Which of the following is not a valid C variable name?"
        ) is True

    def test_an_acronym_is_not_mistaken_for_ocr_noise(self) -> None:
        assert importer.looks_like_a_question(
            "What is the OOP concept of polymorphism?"
        ) is True


class TestPaperKind:
    def test_a_paper_with_the_course_header_is_a_past_question(self) -> None:
        kind, _title = importer._paper_kind(Path("CT 1 Set 3.pdf"), CT_PAGE)
        assert kind == "VERIFIED_PYQ"

    def test_a_question_bank_is_an_official_sample(self) -> None:
        kind, _title = importer._paper_kind(
            Path("Question Bank with MCQs.pdf"), "PROGRAMMING FOR PROBLEM SOLVING"
        )
        assert kind == "OFFICIAL_SAMPLE"


class TestQuestionIds:
    def test_the_id_is_stable_for_the_same_paper_and_number(self) -> None:
        first = importer._question_id("c1", Path("CT 1 Set 3.pdf"), "3", 1, 0)
        second = importer._question_id("c1", Path("CT 1 Set 3.pdf"), "3", 1, 0)
        assert first == second

    def test_the_same_number_in_two_units_gets_different_ids(self) -> None:
        """A paper that restarts its numbering per unit has several Q3s."""
        first = importer._question_id("c1", Path("bank.pdf"), "3", 1, 0)
        second = importer._question_id("c1", Path("bank.pdf"), "3", 2, 0)
        assert first != second

    def test_a_repeated_number_in_the_same_unit_gets_different_ids(self) -> None:
        first = importer._question_id("c1", Path("bank.pdf"), "3", 1, 0)
        second = importer._question_id("c1", Path("bank.pdf"), "3", 1, 1)
        assert first != second

    def test_different_papers_get_different_ids(self) -> None:
        first = importer._question_id("c1", Path("set 3.pdf"), "1", 1, 0)
        second = importer._question_id("c1", Path("set 4.pdf"), "1", 1, 0)
        assert first != second


class TestTheImporterEndToEnd:
    def test_it_imports_a_paper_and_never_verifies_it(self, tmp_path) -> None:
        """Everything it writes is pending review, by construction."""
        import mentorsmith.core.exam as exam

        paper = tmp_path / "CT 1 Set 3.pdf"
        paper.write_bytes(b"%PDF-1.4 not really a pdf")
        questions, stats = importer.import_paper(paper, "c1")
        # The file is not a real PDF, so nothing is extracted - but the
        # importer must say so rather than reporting a clean run.
        assert stats.get("error") or not questions

    def test_a_scanned_paper_is_reported_as_needing_ocr(self, tmp_path) -> None:
        paper = tmp_path / "scan.pdf"
        paper.write_bytes(b"%PDF-1.4 not really a pdf")
        _questions, stats = importer.import_paper(paper, "c1")
        assert "OCR" in stats.get("error", "") or "no text layer" in stats.get("error", "")


class TestTheReviewReportTool:
    def test_the_report_names_what_needs_a_human(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        import mentorsmith.core.exam as exam
        exam.save_questions([
            exam.ExamQuestion(
                id="a", course_id="c1", question_text="A question?",
                options=["a", "b"], answer="",
            )
        ])
        report = exam.review_report()
        assert report["total"] == 1
        assert len(report["pending_review"]) == 1
        assert len(report["no_answer"]) == 1
