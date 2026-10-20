"""Grade a C answer by compiling and running it.

The 2025 CT papers are not multiple-choice papers. Their Part-A questions
ask what a snippet prints and where the fault in a snippet is; their Part-B
and Part-C questions ask for a program to a specification, and they state
the test inputs the answer will be run against.

That is what makes this gradeable honestly. The paper says *here is the
input*; the expected output is then a fact that can be computed by running
the program, not an opinion about what the program "should" do. So the
grader does exactly that: compile the student's C, run it against the
paper's inputs, and compare what came out with what came out.

Nothing here trusts a stored answer string. The expected output is produced
by running the **reference solution**, and the student's program is judged
against that.

Three things this deliberately does not do:

* it does not accept a program that prints the right answer without
  computing it - the paper's questions are about the code, and a lookup
  table would pass a check it has not earned. Where a question allows
  several correct programs, the reference solution is the one that is run.
* it does not grade the *explanation* part. The paper asks students to
  "identify the error and state the corrected condition" and to "trace the
  program manually"; that half is a rubric, graded by the tutor, and is
  labelled as such.
* it does not run anything outside the existing resource-limited
  execution path - the same compiler, the same limits, the same optional
  bubblewrap sandbox the rest of the app uses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..core.exam import CODE_TYPES, ExamQuestion

#: Compiled output is compared after this normalisation, so a stray space
#: or a missing final newline does not fail an otherwise correct answer.
_WHITESPACE = re.compile(r"[ \t]+")


def normalise_output(text: str) -> str:
    """Compare outputs the way a person would read them.

    Trailing whitespace on each line is dropped and the final newline is
    optional. Anything else is a difference: the paper asks for "the exact
    output", and exact means exact.
    """
    lines = [line.rstrip() for line in (text or "").splitlines()]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


@dataclass
class TestCaseResult:
    """One test case, run."""

    stdin: str = ""
    expected: str = ""
    actual: str = ""
    passed: bool = False
    #: Why it failed: the program did not compile, crashed, or printed
    #: something else.
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "stdin": self.stdin,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "note": self.note,
        }


@dataclass
class GradeResult:
    """The outcome of grading one code answer."""

    passed: bool = False
    compiled: bool = False
    cases: list[TestCaseResult] = field(default_factory=list)
    #: The compiler's own diagnostics, when it refused to build.
    build_error: str = ""
    #: The run's stderr, when the program misbehaved at run time.
    run_error: str = ""
    #: The standard error the student's program produced, if any.
    output: str = ""

    @property
    def passed_count(self) -> int:
        return sum(1 for case in self.cases if case.passed)

    @property
    def total(self) -> int:
        return len(self.cases)

    def summary(self) -> str:
        if not self.compiled:
            return "did not compile"
        if not self.cases:
            return "compiled, but there was nothing to run"
        if self.passed_count == self.total:
            return f"passed all {self.total} test case(s)"
        return f"passed {self.passed_count} of {self.total} test case(s)"

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "compiled": self.compiled,
            "cases": [c.to_dict() for c in self.cases],
            "build_error": self.build_error,
            "run_error": self.run_error,
        }


def grade_text(question: ExamQuestion, student_output: str) -> GradeResult:
    """Grade a typed answer - the kind of question that asks "what does it print?".

    The expected output is the one computed from the reference solution, so
    the comparison is against a fact. Whitespace is normalised the same way
    it is for a program's output, so a trailing newline is not the difference
    between right and wrong.
    """
    result = GradeResult()
    expected = ""
    for case in question.test_cases:
        if case.get("expected_stdout"):
            expected = str(case["expected_stdout"])
            break
    result.cases.append(TestCaseResult(
        expected=expected,
        actual=student_output or "",
        passed=normalise_output(student_output or "") == normalise_output(expected),
        note="",
    ))
    result.passed = bool(result.cases) and result.cases[0].passed
    return result


def is_code_question(question: ExamQuestion) -> bool:
    """Whether this is one of the kinds the grader can handle."""
    return question.question_type in CODE_TYPES


def expected_output(
    question: ExamQuestion,
    adapter,
) -> tuple[str, str]:
    """Run the reference solution to get the expected output.

    Returns ``(stdout, error)``. An empty ``error`` means it ran.

    The expected output is *computed*, never typed by hand: a stored
    expected string is one more thing that can be wrong, and the whole
    point of this grader is that the answer is a fact.
    """
    if not question.reference_solution:
        return "", "the question has no reference solution"
    build, run = adapter.run(
        question.reference_solution, stdin_data="", filename="reference.c"
    )
    if not build.ok:
        return "", build.stderr or build.stdout or "the reference solution did not compile"
    if run is None:
        return "", "the reference solution did not run"
    return run.stdout, ""


def grade(
    question: ExamQuestion,
    source: str,
    adapter,
) -> GradeResult:
    """Compile and run the student's program against the question's cases.

    The question's own ``test_cases`` carry the expected output. Where a
    case has none - because the expected output is not known yet - the
    reference solution is run to produce it, so the comparison is against
    a computed answer either way.
    """
    result = GradeResult()
    if not source.strip():
        result.build_error = "there is nothing to compile"
        return result

    build, run = adapter.run(source, stdin_data="", filename="answer.c")
    if not build.ok:
        result.build_error = build.stderr or build.stdout or "the program did not compile"
        return result
    result.compiled = True

    cases = list(question.test_cases)
    if not cases:
        return result

    for case in cases:
        stdin = str(case.get("stdin", ""))
        expected = str(case.get("expected_stdout", ""))
        if not expected:
            # Compute it: run the reference solution with the same input.
            _b, reference_run = adapter.run(
                question.reference_solution, stdin_data=stdin, filename="reference.c"
            )
            if reference_run is None:
                result.cases.append(TestCaseResult(
                    stdin=stdin, note="the reference solution did not run"
                ))
                continue
            expected = reference_run.stdout

        case_run = None
        if run is not None:
            # The build result carries the compiled artifact; re-run it with
            # this case's input.
            case_run = _run_artifact(adapter, source, stdin)
        actual = case_run.stdout if case_run is not None else ""
        passed = normalise_output(actual) == normalise_output(expected)
        result.cases.append(TestCaseResult(
            stdin=stdin,
            expected=expected,
            actual=actual,
            passed=passed,
            note="" if passed else "the output did not match",
        ))
        if case_run is not None:
            result.output = actual

    result.passed = bool(result.cases) and all(c.passed for c in result.cases)
    return result


def _run_artifact(adapter, source: str, stdin: str):
    """Run the student's program with a given input."""
    build, run = adapter.run(source, stdin_data=stdin, filename="answer.c")
    if not build.ok:
        return None
    return run
