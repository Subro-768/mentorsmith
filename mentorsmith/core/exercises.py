"""The adaptive exercise bank and how exercises are graded.

Exercises live in ``mentorsmith/data/exercises.json`` and are validated on
load, so a typo fails immediately instead of producing an exercise that can
never be graded.

Two grading philosophies are kept strictly apart:

* **Deterministic** exercises carry ``expected_stdout``. They are graded by
  compiling and running the learner's code and comparing real program output.
  No AI is involved, and ``graded_by`` is recorded as ``deterministic``.
* **Interpretive** exercises (``explain-code``, ``compare-implementations``)
  carry a ``rubric`` instead. A free-form answer cannot be checked by string
  comparison, so these are graded by the tutor and every result is labelled
  interpretive. Phase 2 is explicit that such grades are opinion, not proof.

The distinction is recorded in the database, so the UI can always tell the
learner which kind of judgement they are looking at.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from difflib import unified_diff
from pathlib import Path

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "exercises.json"

#: Graded by compiling and running; output must match.
DETERMINISTIC_TYPES = (
    "predict-output",
    "find-a-bug",
    "complete-code",
    "write-a-function",
    "modify-code",
    "solve-without-AI",
    "compare-implementations",
)

#: Graded by the tutor against a rubric; always labelled interpretive.
INTERPRETIVE_TYPES = ("explain-code",)

EXERCISE_TYPES = DETERMINISTIC_TYPES + INTERPRETIVE_TYPES

#: Marks an attempt that must be solved without asking the tutor.
NO_HINT_TYPES = ("solve-without-AI",)

#: Marks a deliberate review of an already-studied concept.
REVIEW_PREFIX = "review:"


class ExerciseBankError(RuntimeError):
    """The exercise bank is missing, malformed or internally inconsistent."""


@dataclass(frozen=True)
class Exercise:
    """One exercise in the bank."""

    id: str
    concept_id: str
    lesson_id: str
    type: str
    title: str
    prompt: str
    code: str = ""
    starter_code: str = ""
    expected_stdout: str = ""
    stdin: str = ""
    rubric: tuple[str, ...] = ()
    novel: bool = False
    tags: tuple[str, ...] = ()
    hint: str = ""

    @property
    def is_deterministic(self) -> bool:
        return self.type in DETERMINISTIC_TYPES

    @property
    def is_interpretive(self) -> bool:
        return self.type in INTERPRETIVE_TYPES

    @property
    def forbids_hints(self) -> bool:
        """Whether this exercise must be attempted unaided."""
        return self.type in NO_HINT_TYPES

    @property
    def initial_code(self) -> str:
        """What the learner starts with: their starter, else the example."""
        return self.starter_code or self.code

    def review_variant_id(self) -> str:
        """Id used when this exercise is re-asked as a delayed review."""
        return f"{REVIEW_PREFIX}{self.id}"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "concept_id": self.concept_id,
            "lesson_id": self.lesson_id,
            "type": self.type,
            "title": self.title,
            "prompt": self.prompt,
            "expected_stdout": self.expected_stdout,
            "novel": self.novel,
            "tags": list(self.tags),
        }


@dataclass
class ExerciseBank:
    """All exercises, indexed for fast lookup."""

    exercises: list[Exercise] = field(default_factory=list)

    @classmethod
    def load(
        cls,
        path: Path | None = None,
        known_concepts: set[str] | None = None,
        valid_lesson_ids: set[str] | None = None,
    ) -> "ExerciseBank":
        source = Path(path) if path else DATA_PATH
        try:
            raw = json.loads(source.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ExerciseBankError(f"Exercise bank not found: {source}") from exc
        except json.JSONDecodeError as exc:
            raise ExerciseBankError(f"Exercise bank is not valid JSON: {exc}") from exc

        entries = raw.get("exercises") if isinstance(raw, dict) else raw
        if not isinstance(entries, list) or not entries:
            raise ExerciseBankError("Exercise bank contains no exercises.")

        exercises: list[Exercise] = []
        seen: set[str] = set()
        for entry in entries:
            exercise_id = str(entry.get("id", "")).strip()
            if not exercise_id:
                raise ExerciseBankError("Every exercise needs a non-empty 'id'.")
            if exercise_id in seen:
                raise ExerciseBankError(f"Duplicate exercise id: {exercise_id}")
            seen.add(exercise_id)

            exercise_type = str(entry.get("type", "")).strip()
            if exercise_type not in EXERCISE_TYPES:
                raise ExerciseBankError(
                    f"Exercise '{exercise_id}' has unknown type '{exercise_type}'. "
                    f"Valid types: {', '.join(EXERCISE_TYPES)}"
                )

            expected = str(entry.get("expected_stdout", ""))
            rubric = tuple(str(r) for r in entry.get("rubric", []))
            if exercise_type in DETERMINISTIC_TYPES and not expected:
                raise ExerciseBankError(
                    f"Deterministic exercise '{exercise_id}' needs 'expected_stdout'."
                )
            if exercise_type in INTERPRETIVE_TYPES and not rubric:
                raise ExerciseBankError(
                    f"Interpretive exercise '{exercise_id}' needs a 'rubric'."
                )

            concept_id = str(entry.get("concept_id", ""))
            if not concept_id:
                raise ExerciseBankError(f"Exercise '{exercise_id}' has no concept_id.")
            if known_concepts is not None and concept_id not in known_concepts:
                raise ExerciseBankError(
                    f"Exercise '{exercise_id}' references unknown concept "
                    f"'{concept_id}'."
                )
            lesson_id = str(entry.get("lesson_id", ""))
            if valid_lesson_ids is not None and lesson_id and lesson_id not in valid_lesson_ids:
                raise ExerciseBankError(
                    f"Exercise '{exercise_id}' references unknown lesson '{lesson_id}'."
                )

            exercises.append(
                Exercise(
                    id=exercise_id,
                    concept_id=concept_id,
                    lesson_id=lesson_id,
                    type=exercise_type,
                    title=str(entry.get("title", exercise_id)),
                    prompt=str(entry.get("prompt", "")),
                    code=str(entry.get("code", "")),
                    starter_code=str(entry.get("starter_code", "")),
                    expected_stdout=expected,
                    stdin=str(entry.get("stdin", "")),
                    rubric=rubric,
                    novel=bool(entry.get("novel", False)),
                    tags=tuple(str(t) for t in entry.get("tags", [])),
                    hint=str(entry.get("hint", "")),
                )
            )

        bank = cls(exercises=exercises)
        return bank

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------
    def get(self, exercise_id: str) -> Exercise | None:
        for exercise in self.exercises:
            if exercise.id == exercise_id:
                return exercise
        return None

    def for_concept(self, concept_id: str) -> list[Exercise]:
        return [e for e in self.exercises if e.concept_id == concept_id]

    def for_lesson(self, lesson_id: str) -> list[Exercise]:
        return [e for e in self.exercises if e.lesson_id == lesson_id]

    def types_present(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for exercise in self.exercises:
            counts[exercise.type] = counts.get(exercise.type, 0) + 1
        return counts

    def concepts_covered(self) -> set[str]:
        return {e.concept_id for e in self.exercises}

    def unattempted(self, concept_id: str, attempted_ids: set[str]) -> list[Exercise]:
        """Exercises for a concept the learner has not tried yet."""
        return [e for e in self.for_concept(concept_id) if e.id not in attempted_ids]


# ----------------------------------------------------------------------
# Deterministic grading
# ----------------------------------------------------------------------
def normalise_output(text: str) -> str:
    """Normalise program output for comparison.

    Strips trailing whitespace on each line and collapses the ends, so a
    missing final newline is not reported as a wrong answer.
    """
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").split("\n")]
    return "\n".join(lines).strip()


def outputs_match(actual: str, expected: str) -> bool:
    return normalise_output(actual) == normalise_output(expected)


@dataclass
class GradeResult:
    """Outcome of grading one attempt."""

    correct: bool
    graded_by: str
    detail: str = ""
    diff: str = ""
    error_category: str = ""
    error_category_explanation: str = ""

    @property
    def is_interpretive(self) -> bool:
        return self.graded_by == "interpretive"


def grade_deterministic(
    exercise: Exercise,
    *,
    compiled: bool,
    compile_stderr: str,
    stdout: str,
    exit_code: int | None,
    run_timed_out: bool = False,
) -> GradeResult:
    """Grade a deterministic exercise against real program output.

    Failure categories are deliberately coarse. They exist to point at the
    next question to ask, not to diagnose the bug.
    """
    if not compiled:
        return GradeResult(
            correct=False,
            graded_by="deterministic",
            detail="The code did not compile, so it was not graded against output.",
            error_category="compile_failure",
            error_category_explanation=_first_error_line(compile_stderr),
        )

    if run_timed_out:
        return GradeResult(
            correct=False,
            graded_by="deterministic",
            detail="The program was stopped for running too long.",
            error_category="runtime_timeout",
            error_category_explanation="The loop or recursion did not terminate.",
        )

    if exit_code not in (0, None):
        return GradeResult(
            correct=False,
            graded_by="deterministic",
            detail=f"The program exited with code {exit_code}.",
            error_category="runtime_error",
            error_category_explanation=_first_error_line(stdout),
        )

    if outputs_match(stdout, exercise.expected_stdout):
        return GradeResult(
            correct=True,
            graded_by="deterministic",
            detail="The program's real output matched the expected output.",
        )

    return GradeResult(
        correct=False,
        graded_by="deterministic",
        detail="The program ran but its output did not match what was expected.",
        error_category="wrong_output",
        error_category_explanation="Logic problem, not a crash: the code compiled and ran.",
        diff=build_diff(exercise.expected_stdout, stdout),
    )


def build_diff(expected: str, actual: str) -> str:
    """A unified diff between expected and actual output."""
    diff = unified_diff(
        normalise_output(expected).splitlines(),
        normalise_output(actual).splitlines(),
        fromfile="expected",
        tofile="actual",
        lineterm="",
    )
    return "\n".join(diff)


def _first_error_line(text: str) -> str:
    """The most useful line of a compiler diagnostic."""
    for line in (text or "").splitlines():
        if "error:" in line:
            return line.strip()[:200]
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


def build_rubric_prompt(exercise: Exercise, answer: str) -> str:
    """Prompt for grading a free-form answer.

    Kept here so the phrasing is versioned with the bank, and so tests can
    assert the rubric is actually included.
    """
    points = "\n".join(f"- {item}" for item in exercise.rubric)
    return (
        f"Question:\n{exercise.prompt}\n\n"
        f"Code under discussion:\n```cpp\n{exercise.code}\n```\n\n"
        f"The learner's explanation:\n{answer}\n\n"
        f"Check the explanation against these points:\n{points}\n\n"
        "Judge whether the explanation is right. Answer with exactly one line:\n"
        "VERDICT: correct or partial or incorrect\n"
        "REASON: one sentence on what was right or missing"
    )


_BANK: ExerciseBank | None = None


def load_bank(refresh: bool = False, **kwargs) -> ExerciseBank:
    """Load the exercise bank, caching it for the process lifetime."""
    global _BANK
    if _BANK is None or refresh:
        _BANK = ExerciseBank.load(**kwargs)
    return _BANK