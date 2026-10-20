"""Code questions: tracing, debugging and programming tasks.

The 2025 CT papers are not multiple-choice papers. Their Part-A questions ask
what a snippet prints or where its fault is; Part B and Part-C ask for a
program to a specification, with the test inputs stated in the question.

That is what makes them gradeable honestly. The paper says *here is the
input*, so the expected output is a **fact** - produced by compiling and
running the reference solution - rather than an opinion stored in a string.

These tests hold to that:

* every bundled question's reference solution compiles, and produces exactly
  the output stored with it;
* the grader accepts a correct program and rejects a wrong one;
* a question whose reference solution does not compile is a failure in the
  bank, not something to ship with a guessed answer.
"""

from __future__ import annotations

import json

import pytest

from mentorsmith.core.exam import (
    CODE_TYPES,
    DEBUG,
    PROGRAM,
    TRACE,
    ExamQuestion,
    load_bundled_questions,
)
from mentorsmith.services.code_grader import (
    grade,
    grade_text,
    is_code_question,
    normalise_output,
)

COURSE = "26cse1002j-pps"


@pytest.fixture(scope="module")
def bundled():
    questions = load_bundled_questions(COURSE)
    if not questions:
        pytest.skip("no bundled question bank")
    return questions


@pytest.fixture(scope="module")
def adapter():
    import tempfile
    from pathlib import Path

    from mentorsmith.execution.c import CAdapter

    work = Path(tempfile.mkdtemp())
    return CAdapter(work, sandbox=False)


class TestTheBundledBank:
    def test_it_ships_with_the_app(self) -> None:
        """Unlike imported papers, these are ours and can be redistributed."""
        path = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "mentorsmith" / "data" / "exam" / "questions.json"
        )
        assert path.exists(), "the bundled question bank is missing"

    def test_it_has_questions_in_every_part(self, bundled) -> None:
        parts = {q.part for q in bundled}
        assert parts == {"A", "B", "C"}, f"parts present: {parts}"

    def test_the_marks_match_the_paper(self, bundled) -> None:
        """Part A is 2 marks, Part B 4, Part C 12."""
        expected = {"A": 2, "B": 4, "C": 12}
        for question in bundled:
            assert question.marks == expected[question.part], (
                f"{question.id} carries {question.marks} marks, "
                f"the paper uses {expected[question.part]}"
            )

    def test_every_question_is_one_of_the_code_kinds(self, bundled) -> None:
        for question in bundled:
            assert question.question_type in CODE_TYPES

    def test_every_question_has_a_task(self, bundled) -> None:
        for question in bundled:
            assert question.task.strip(), f"{question.id} has no task"

    def test_every_part_a_question_shows_code(self, bundled) -> None:
        """Part A is about a snippet, so it has to show one."""
        for question in bundled:
            if question.part == "A" and question.question_type != PROGRAM:
                assert question.code.strip(), f"{question.id} shows no code"

    def test_every_question_has_a_reference_solution(self, bundled) -> None:
        for question in bundled:
            assert question.reference_solution.strip(), (
                f"{question.id} has no reference solution"
            )

    def test_every_question_has_at_least_one_test_case(self, bundled) -> None:
        for question in bundled:
            assert question.test_cases, f"{question.id} has no test case"

    def test_every_question_carries_the_papers_marking(self, bundled) -> None:
        for question in bundled:
            assert question.bloom_level, f"{question.id} has no Bloom level"
            assert question.co, f"{question.id} has no course outcome"
            assert question.po, f"{question.id} has no programme outcome"

    def test_the_questions_are_original(self, bundled) -> None:
        """They are ours, not a paper's - so they may ship."""
        for question in bundled:
            assert question.source_type == "ORIGINAL_PRACTICE"

    def test_the_constrained_question_says_so(self, bundled) -> None:
        constrained = [q for q in bundled if q.constraints]
        assert constrained, "no question carries a constraint"


class TestTheReferenceSolutions:
    def test_every_one_compiles_and_produces_the_stored_output(
        self, bundled, adapter
    ) -> None:
        """The key is computed, and it must agree with what was stored.

        If a reference solution stops compiling, or its output changes, the
        stored expectation is wrong - and a key that is wrong is worse than
        no key.
        """
        for question in bundled:
            for case in question.test_cases:
                stdin = str(case.get("stdin", ""))
                build, run = adapter.run(
                    question.reference_solution, stdin_data=stdin, filename="ref.c"
                )
                assert build.ok, (
                    f"{question.id} does not compile:\n{build.stderr[:400]}"
                )
                assert run is not None, f"{question.id} did not run"
                assert normalise_output(run.stdout) == normalise_output(
                    str(case.get("expected_stdout", ""))
                ), (
                    f"{question.id} now produces {run.stdout!r} but the stored "
                    f"expectation is {case.get('expected_stdout')!r}"
                )


class TestGrading:
    def test_a_correct_program_is_accepted(self, bundled, adapter) -> None:
        question = next(q for q in bundled if q.question_type == PROGRAM)
        result = grade(question, question.reference_solution, adapter)
        assert result.compiled is True
        assert result.passed is True, result.summary()
        assert result.passed_count == result.total

    def test_a_wrong_program_is_rejected(self, bundled, adapter) -> None:
        question = next(q for q in bundled if q.question_type == PROGRAM)
        wrong = (
            "#include <stdio.h>\n"
            "int main() { printf(\"something else entirely\\n\"); return 0; }\n"
        )
        result = grade(question, wrong, adapter)
        assert result.compiled is True
        assert result.passed is False

    def test_a_program_that_does_not_compile_is_reported(self, bundled, adapter) -> None:
        question = next(q for q in bundled if q.question_type == PROGRAM)
        result = grade(question, "int main() { this is not C }\n", adapter)
        assert result.compiled is False
        assert result.passed is False
        assert result.build_error

    def test_an_empty_answer_is_refused(self, bundled, adapter) -> None:
        question = next(q for q in bundled if q.question_type == PROGRAM)
        result = grade(question, "   ", adapter)
        assert result.compiled is False

    def test_the_standard_output_is_ignored(self, bundled, adapter) -> None:
        """Only what the program prints on stdout is the answer."""
        question = next(q for q in bundled if q.question_type == PROGRAM)
        noisy = question.reference_solution.replace(
            "#include <stdio.h>", "#include <stdio.h>\n/* a comment */"
        )
        result = grade(question, noisy, adapter)
        assert result.passed is True, result.summary()

    def test_a_traced_answer_is_graded_as_text(self, bundled) -> None:
        question = next(q for q in bundled if q.question_type == TRACE)
        expected = str(question.test_cases[0]["expected_stdout"])
        result = grade_text(question, expected)
        assert result.passed is True
        assert result.passed_count == 1

    def test_a_wrong_traced_answer_is_rejected(self, bundled) -> None:
        question = next(q for q in bundled if q.question_type == TRACE)
        result = grade_text(question, "definitely not the output")
        assert result.passed is False

    def test_a_trailing_newline_does_not_matter(self, bundled) -> None:
        question = next(q for q in bundled if q.question_type == TRACE)
        expected = str(question.test_cases[0]["expected_stdout"])
        result = grade_text(question, expected + "\n\n")
        assert result.passed is True


class TestNormalising:
    def test_trailing_spaces_on_a_line_are_ignored(self) -> None:
        assert normalise_output("a  \nb") == normalise_output("a\nb")

    def test_a_missing_final_newline_is_ignored(self) -> None:
        assert normalise_output("a\n") == normalise_output("a")

    def test_inner_differences_are_not_ignored(self) -> None:
        assert normalise_output("a b") != normalise_output("ab")


class TestTheQuestionKinds:
    def test_code_questions_are_recognised(self) -> None:
        question = ExamQuestion(
            id="x", course_id=COURSE, question_text="t", question_type=DEBUG
        )
        assert is_code_question(question) is True

    def test_multiple_choice_is_not_a_code_question(self) -> None:
        question = ExamQuestion(
            id="x", course_id=COURSE, question_text="t", question_type="MCQ"
        )
        assert is_code_question(question) is False
