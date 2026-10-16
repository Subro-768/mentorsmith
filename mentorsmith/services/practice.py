"""Running an adaptive exercise end to end, without any Qt dependency.

This is the glue between the exercise bank, the toolchain, the grader and the
database. It is deliberately free of Qt so the whole loop — submit code, run
it, grade it, record it, decide what to say next — can be tested headlessly.

Two grading paths, kept separate and labelled:

* deterministic: compile, run, compare real stdout against ``expected_stdout``
* interpretive: the learner's written answer is sent to the tutor with a
  rubric, and the result is stored with ``graded_by='interpretive'``

Every attempt records how many hints were used and whether the learner solved
it independently, because that distinction is what makes the mastery label
meaningful.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..compiler.toolchain import CommandResult, Toolchain
from ..core.db import Database
from ..core.debugging import DebugDiagnosis, DebugSession, diagnose
from ..core.exercises import (
    Exercise,
    GradeResult,
    build_rubric_prompt,
    grade_deterministic,
)
from ..core.mastery import is_review_attempt

#: Verdicts the tutor may return for a free-form answer.
VERDICTS = ("correct", "partial", "incorrect")


class PracticeError(RuntimeError):
    """Something went wrong while running a practice attempt."""


def parse_verdict(text: str) -> tuple[str, str]:
    """Extract ``(verdict, reason)`` from a tutor reply.

    This is the only place untrusted model output influences state, so it is
    deliberately narrow and cannot fail:

    * The verdict must be one of :data:`VERDICTS`, or it defaults to
      ``incorrect`` — a malformed reply never grants a pass.
    * The reason is plain text, truncated, and returned to the caller for
      display only.
    * Nothing in the reply is ever evaluated, imported, executed or passed to
      a shell. Model output is data, not instructions.

    A reply containing prompt-injection attempts (``VERDICT: correct. Ignore
    previous instructions...``) still only yields a verdict; the injected text
    is inert.
    """
    verdict = "incorrect"
    reason = ""
    for line in (text or "").splitlines():
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("VERDICT:") and verdict == "incorrect":
            value = stripped.split(":", 1)[1].strip().lower()
            for candidate in VERDICTS:
                if candidate in value:
                    verdict = candidate
                    break
        elif upper.startswith("REASON:") and not reason:
            reason = stripped.split(":", 1)[1].strip()
    if not reason:
        reason = (text or "").strip()[:400]
    return verdict, reason[:400]


@dataclass
class PracticeOutcome:
    """The result of one graded attempt."""

    exercise: Exercise
    grade: GradeResult
    compile_result: CommandResult | None = None
    run_result: CommandResult | None = None
    attempt_id: int | None = None
    diagnosis: DebugDiagnosis | None = None
    session: DebugSession | None = None
    follow_up: str = ""

    @property
    def correct(self) -> bool:
        return self.grade.correct

    @property
    def needs_attention(self) -> bool:
        """Whether the debugging coach should speak."""
        return not self.grade.correct

    def to_dict(self) -> dict:
        return {
            "exercise_id": self.exercise.id,
            "correct": self.correct,
            "graded_by": self.grade.graded_by,
            "detail": self.grade.detail,
            "error_category": self.grade.error_category,
            "attempt_id": self.attempt_id,
        }


@dataclass
class PracticeSession:
    """One learner's work on one exercise."""

    database: Database
    toolchain: Toolchain
    exercise: Exercise
    lesson_id: str = ""
    #: Extra evidence recorded on the next attempt.
    is_review: bool = False
    #: Language track this attempt belongs to. Progress never crosses tracks.
    language: str = "cpp"
    session: DebugSession = field(default_factory=DebugSession)

    def __post_init__(self) -> None:
        self.lesson_id = self.lesson_id or self.exercise.lesson_id
        self.session.concept_id = self.exercise.concept_id
        self.session.exercise_id = self.exercise.id

    # ------------------------------------------------------------------
    # Deterministic path
    # ------------------------------------------------------------------
    def submit(self, source: str, *, stdin: str = "") -> PracticeOutcome:
        """Compile, run, grade and record a code attempt.

        The learner's code is compiled and run even for ``solve-without-AI``:
        "without AI" restricts the *tutor*, not the compiler.
        """
        if self.exercise.is_interpretive:
            raise PracticeError(
                f"Exercise '{self.exercise.id}' is graded by explanation, not by "
                "running code. Use record_interpretive() instead."
            )

        compile_result, run_result = self.toolchain.run(
            source,
            stdin_data=stdin or self.exercise.stdin,
            filename=self._source_filename(),
        )

        grade = grade_deterministic(
            self.exercise,
            compiled=compile_result.ok,
            compile_stderr=compile_result.stderr,
            stdout=run_result.stdout if run_result else "",
            exit_code=run_result.exit_code if run_result else None,
            run_timed_out=bool(run_result.timed_out) if run_result else False,
        )

        attempt_id = self._record(
            source=source,
            grade=grade,
            exercise_type=self._attempt_type(),
            correct=grade.correct,
            error_category=grade.error_category,
        )

        diagnosis = None
        follow_up = ""
        if grade.correct:
            follow_up = self.session.on_resolved()
        else:
            diagnosis = diagnose(
                compiled=compile_result.ok,
                compile_stderr=compile_result.stderr,
                stdout=run_result.stdout if run_result else "",
                exit_code=run_result.exit_code if run_result else None,
                timed_out=bool(run_result.timed_out) if run_result else False,
                recorded_category=grade.error_category,
            )
            diagnosis = self.session.on_failure(diagnosis)

        return PracticeOutcome(
            exercise=self.exercise,
            grade=grade,
            compile_result=compile_result,
            run_result=run_result,
            attempt_id=attempt_id,
            diagnosis=diagnosis,
            session=self.session,
            follow_up=follow_up,
        )

    # ------------------------------------------------------------------
    # Interpretive path
    # ------------------------------------------------------------------
    def rubric_prompt(self, answer: str) -> str:
        """Prompt used to grade a free-form answer."""
        return build_rubric_prompt(self.exercise, answer)

    def record_interpretive(
        self,
        answer: str,
        *,
        verdict: str,
        feedback: str,
        hints_used: int = 0,
    ) -> PracticeOutcome:
        """Record a tutor judgement of a written explanation.

        Always stored as ``interpretive``. A verdict of ``partial`` counts as
        incorrect for mastery purposes: an explanation that is partly right has
        not demonstrated understanding.
        """
        verdict = (verdict or "").strip().lower()
        if verdict not in VERDICTS:
            raise PracticeError(
                f"Verdict must be one of {VERDICTS}, got {verdict!r}."
            )

        correct = verdict == "correct"
        grade = GradeResult(
            correct=correct,
            graded_by="interpretive",
            detail=feedback or f"Tutor judged the explanation '{verdict}'.",
            error_category="" if correct else "explanation_incomplete",
            error_category_explanation=(
                "" if correct else "The explanation did not cover the key points."
            ),
        )

        attempt_id = self._record(
            source=answer,
            grade=grade,
            exercise_type=self._attempt_type(),
            correct=correct,
            error_category=grade.error_category,
            hints_used=hints_used,
            graded_by="interpretive",
        )

        follow_up = ""
        diagnosis = None
        if correct:
            follow_up = self.session.on_resolved()
        else:
            diagnosis = diagnose(
                compiled=True, recorded_category=grade.error_category
            )
            diagnosis = self.session.on_failure(diagnosis)

        return PracticeOutcome(
            exercise=self.exercise,
            grade=grade,
            attempt_id=attempt_id,
            diagnosis=diagnosis,
            session=self.session,
            follow_up=follow_up,
        )

    # ------------------------------------------------------------------
    # Hints
    # ------------------------------------------------------------------
    def can_hint(self) -> bool:
        """Some exercises must be attempted unaided."""
        return not self.exercise.forbids_hints

    def hint(self) -> str:
        """Return the next hint, or an explanation of why there is none."""
        if not self.can_hint():
            return (
                f"'{self.exercise.title}' is a solve-without-AI exercise, so no "
                "hints are available. Working it unaided is the whole point — "
                "that is what makes it evidence."
            )
        if self.exercise.hint and self.session.last_diagnosis is None:
            self.session.hints_used += 1
            return self.exercise.hint
        return self.session.give_hint()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _attempt_type(self) -> str:
        """Exercise type, marked when this is a deliberate review."""
        return self.exercise.review_variant_id() if self.is_review else self.exercise.type

    def _source_filename(self) -> str:
        """Source filename using this language's extension."""
        extension = getattr(self.toolchain, "extension", ".cpp")
        return f"practice{extension}"

    def _record(
        self,
        *,
        source: str,
        grade: GradeResult,
        exercise_type: str,
        correct: bool,
        error_category: str,
        hints_used: int | None = None,
        graded_by: str = "deterministic",
    ) -> int:
        hints = self.session.hints_used if hints_used is None else hints_used
        # Independence means solved correctly with no help and no escalation.
        independent = bool(correct and hints == 0 and self.session.escalations == 0)
        return self.database.record_exercise_attempt(
            self.lesson_id,
            self.exercise.id,
            source=source,
            compiled_ok=grade.graded_by != "interpretive" and correct,
            ran_ok=grade.graded_by != "interpretive" and correct,
            result="correct" if correct else (error_category or "incorrect"),
            exercise_type=exercise_type,
            concept_id=self.exercise.concept_id,
            correct=correct,
            hints_used=hints,
            independent=independent,
            error_category=error_category,
            grade=grade.detail,
            novelty=self.exercise.novel,
            graded_by=graded_by,
            language=self.language,
        )

    def state(self) -> dict:
        """Snapshot for the UI."""
        return {
            "exercise_id": self.exercise.id,
            "concept_id": self.exercise.concept_id,
            "language": self.language,
            "type": self.exercise.type,
            "graded_deterministically": self.exercise.is_deterministic,
            "allows_hints": self.can_hint(),
            "is_review": is_review_attempt(self._attempt_type()),
            **self.session.to_dict(),
        }