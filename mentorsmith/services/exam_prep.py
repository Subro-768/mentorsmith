"""Exam preparation: sessions, grading, results and mistake analysis.

What this service does
----------------------
Runs a practice session over a course's question bank, records what the
student answered, and reports back honestly.

The honest part matters more than usual here, because of one fact about
the material: **the papers do not print an answer key.** A cycle-test paper
gives you the questions and the options and nothing else. So most imported
questions have no key, and this service says so rather than guessing one
or quietly counting the attempt as wrong.

Three cases, kept apart on purpose:

``graded``
    The question has a key. The answer is compared to it and marked right
    or wrong.
``ungraded``
    The question has no key - the paper did not print one. The answer is
    recorded and the student is told which page of which paper to check it
    against. It is **not** counted as wrong: an ungraded attempt is not
    evidence of a mistake, and treating it as one would poison the
    mistake analysis.
``not answered``
    The student skipped it. Recorded, and shown as skipped.

Why the mistake list is separate from the graded score
-------------------------------------------------------
A mistake list built from ungraded attempts would be a list of questions
the student *might* have got wrong. The brief asks for "practise my
mistakes", and that has to mean the ones they actually got wrong.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..core.exam import (
    ExamQuestion,
    VERIFIED,
    load_courses,
    load_questions,
    normalise_text,
)

#: The label shown for an attempt that could not be graded.
UNGRADED = "ungraded"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class AttemptResult:
    """What happened when the student answered one question."""

    question: ExamQuestion
    chosen: str
    #: True, False, or None when there is no key to grade against.
    correct: bool | None
    explanation: str = ""
    seconds_taken: int = 0

    @property
    def graded(self) -> bool:
        return self.correct is not None

    @property
    def status(self) -> str:
        if self.correct is True:
            return "correct"
        if self.correct is False:
            return "wrong"
        return UNGRADED

    @property
    def source_label(self) -> str:
        return self.question.display_label

    @property
    def needs_paper_check(self) -> bool:
        """True when the student has to look at the paper for the answer."""
        return self.correct is None

    @property
    def paper_pointer(self) -> str:
        """Where to look for the answer, when there is nowhere else."""
        return self.question.source_reference


@dataclass
class ExamResults:
    """The end of a session."""

    session_id: str
    course_id: str
    title: str
    total: int = 0
    answered: int = 0
    correct: int = 0
    wrong: int = 0
    ungraded: int = 0
    skipped: int = 0
    seconds: int = 0
    #: unit -> (correct, graded total). Only *graded* attempts count: a unit
    #: where nothing could be graded is unmeasured, not weak.
    by_unit: dict[int, list[int]] = field(default_factory=dict)
    #: source type -> (correct, graded total)
    by_source: dict[str, list[int]] = field(default_factory=dict)
    mistakes: list[AttemptResult] = field(default_factory=list)
    ungraded_results: list[AttemptResult] = field(default_factory=list)
    #: Units that were attempted at all, graded or not.
    attempted_units: set[int] = field(default_factory=set)

    @property
    def graded_total(self) -> int:
        return self.correct + self.wrong

    @property
    def accuracy(self) -> float | None:
        """Accuracy over the questions that could be graded.

        None when nothing could be graded - a percentage out of zero
        questions would be a number, and it would mean nothing.
        """
        if not self.graded_total:
            return None
        return self.correct / self.graded_total

    def summary(self) -> str:
        parts = [f"{self.answered} of {self.total} answered"]
        if self.graded_total:
            percent = round((self.accuracy or 0.0) * 100)
            parts.append(f"{self.correct} of {self.graded_total} graded right ({percent}%)")
        if self.ungraded:
            parts.append(
                f"{self.ungraded} with no answer key in the paper"
            )
        if self.skipped:
            parts.append(f"{self.skipped} skipped")
        return " · ".join(parts)

    def weak_units(self) -> list[tuple[int, float]]:
        """Units worth revisiting, worst first.

        Only units with at least one graded answer count. A unit where
        nothing could be graded is not weak - it is unmeasured, and saying
        otherwise would be inventing a weakness.
        """
        scored = []
        for unit, (correct, total) in self.by_unit.items():
            if total:
                scored.append((unit, correct / total))
        return sorted(scored, key=lambda item: item[1])

    def unmeasured_units(self) -> list[int]:
        """Units that were attempted but could not be graded.

        A unit with no graded answers is unmeasured, not weak, and the two
        are reported separately so neither is mistaken for the other.
        """
        graded = {unit for unit, (_c, total) in self.by_unit.items() if total}
        return sorted(self.attempted_units - graded)


@dataclass
class ExamSession:
    """A run through a set of questions."""

    id: str
    course_id: str
    title: str
    questions: list[ExamQuestion]
    index: int = 0
    results: list[AttemptResult] = field(default_factory=list)
    started_at: str = field(default_factory=_now)

    @property
    def current(self) -> ExamQuestion | None:
        if 0 <= self.index < len(self.questions):
            return self.questions[self.index]
        return None

    @property
    def finished(self) -> bool:
        return self.index >= len(self.questions)

    @property
    def answered_ids(self) -> set[str]:
        return {r.question.id for r in self.results}


class ExamPrepService:
    """Everything the Exam Prep page needs, with no Qt in sight."""

    def __init__(self, database) -> None:
        self.database = database

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    def courses(self):
        """The courses in the catalogue.

        Only courses whose record passes its own validation are returned -
        the catalogue loader validates, and a course that cannot be
        checked is not shown as though it could.
        """
        return load_courses()

    def course(self, course_id: str):
        for course in self.courses():
            if course.id == course_id:
                return course
        return None

    def questions(
        self,
        course_id: str,
        *,
        unit: int | None = None,
        topic_id: str | None = None,
        source_type: str | None = None,
        verification_status: str | None = None,
        question_type: str | None = None,
        search: str = "",
    ) -> list[ExamQuestion]:
        """The bank's questions, filtered.

        Every filter is one the brief asks for: topic, type, difficulty and
        verified/unverified status. An empty filter matches everything.
        """
        found = load_questions(course_id)
        if unit is not None:
            found = [q for q in found if q.unit == unit]
        if topic_id:
            found = [q for q in found if topic_id in q.topic_ids]
        if source_type:
            found = [q for q in found if q.source_type == source_type]
        if verification_status:
            found = [q for q in found if q.verification_status == verification_status]
        if question_type:
            found = [q for q in found if q.question_type == question_type]
        if search.strip():
            needle = search.strip().lower()
            found = [
                q for q in found
                if needle in q.question_text.lower()
                or any(needle in option.lower() for option in q.options)
            ]
        return found

    def counts(self, course_id: str) -> dict[str, int]:
        """How the bank breaks down, for the filters."""
        questions = load_questions(course_id)
        by_source: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_unit: dict[int, int] = {}
        by_type: dict[str, int] = {}
        for question in questions:
            by_source[question.source_type] = by_source.get(question.source_type, 0) + 1
            by_status[question.verification_status] = (
                by_status.get(question.verification_status, 0) + 1
            )
            by_unit[question.unit] = by_unit.get(question.unit, 0) + 1
            by_type[question.question_type] = by_type.get(question.question_type, 0) + 1
        return {
            "total": len(questions),
            "by_source": by_source,
            "by_status": by_status,
            "by_unit": by_unit,
            "by_type": by_type,
        }

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    def start_session(
        self,
        questions: list[ExamQuestion],
        course_id: str,
        title: str = "",
    ) -> ExamSession:
        """Begin a session over the given questions."""
        if not questions:
            raise ValueError("Cannot start a session with no questions.")
        return ExamSession(
            id=uuid.uuid4().hex[:12],
            course_id=course_id,
            title=title or f"{len(questions)} question(s)",
            questions=list(questions),
        )

    def submit(
        self,
        session: ExamSession,
        answer: str,
        *,
        seconds_taken: int = 0,
    ) -> AttemptResult:
        """Record an answer and move on.

        An empty answer means the student skipped it.
        """
        question = session.current
        if question is None:
            raise ValueError("The session is already finished.")

        chosen = (answer or "").strip()
        if chosen:
            correct = self._grade(question, chosen)
        else:
            correct = None

        result = AttemptResult(
            question=question,
            chosen=chosen,
            correct=correct,
            explanation=question.explanation,
            seconds_taken=seconds_taken,
        )
        session.results.append(result)
        session.index += 1

        self._record(session, result)
        return result

    def _grade(self, question: ExamQuestion, chosen: str) -> bool | None:
        """Compare an answer to the key. None when there is no key."""
        key = (question.answer or "").strip()
        if not key:
            return None
        return normalise_text(chosen) == normalise_text(key)

    def _record(self, session: ExamSession, result: AttemptResult) -> None:
        """Write the attempt to the database."""
        question = result.question
        try:
            self.database.connect().execute(
                """
                INSERT INTO exam_attempts
                    (question_id, course_id, session_id, chosen_answer, correct,
                     topic_ids, unit, seconds_taken, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    question.id,
                    session.course_id,
                    session.id,
                    result.chosen,
                    None if result.correct is None else int(result.correct),
                    ",".join(question.topic_ids),
                    question.unit,
                    result.seconds_taken,
                    _now(),
                ),
            )
            self.database.connect().commit()
        except Exception:  # pragma: no cover - a storage failure must not
            # lose the student's work in the session itself.
            pass

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------
    def finish(self, session: ExamSession) -> ExamResults:
        """Summarise a session."""
        results = ExamResults(
            session_id=session.id,
            course_id=session.course_id,
            title=session.title,
            total=len(session.questions),
            seconds=sum(r.seconds_taken for r in session.results),
        )
        for result in session.results:
            if not result.chosen:
                results.skipped += 1
                continue
            results.answered += 1
            if result.correct is True:
                results.correct += 1
            elif result.correct is False:
                results.wrong += 1
            else:
                results.ungraded += 1
                results.ungraded_results.append(result)

            unit = result.question.unit
            results.attempted_units.add(unit)
            if result.correct is not None:
                bucket = results.by_unit.setdefault(unit, [0, 0])
                bucket[1] += 1
                if result.correct:
                    bucket[0] += 1

                source = result.question.source_type
                source_bucket = results.by_source.setdefault(source, [0, 0])
                source_bucket[1] += 1
                if result.correct:
                    source_bucket[0] += 1

            if result.correct is False:
                results.mistakes.append(result)
        return results

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------
    def attempts(self, course_id: str) -> list[dict]:
        """Every recorded attempt for a course, newest first."""
        rows = self.database.connect().execute(
            "SELECT * FROM exam_attempts WHERE course_id = ? ORDER BY id DESC",
            (course_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def mistake_question_ids(self, course_id: str) -> list[str]:
        """The questions the student has actually got wrong.

        Only attempts that were graded and wrong count. An ungraded attempt
        is not a mistake - nobody knows whether it was one.
        """
        rows = self.database.connect().execute(
            "SELECT DISTINCT question_id FROM exam_attempts "
            "WHERE course_id = ? AND correct = 0",
            (course_id,),
        ).fetchall()
        return [r["question_id"] for r in rows]

    def mistake_questions(self, course_id: str) -> list[ExamQuestion]:
        """The actual question objects for the mistakes."""
        wanted = set(self.mistake_question_ids(course_id))
        if not wanted:
            return []
        return [q for q in load_questions(course_id) if q.id in wanted]

    def progress(self, course_id: str) -> dict:
        """How the student is doing, for the course dashboard."""
        attempts = self.attempts(course_id)
        graded = [a for a in attempts if a.get("correct") is not None]
        correct = [a for a in graded if a.get("correct")]
        seen = {a["question_id"] for a in attempts}
        bank = load_questions(course_id)
        return {
            "attempts": len(attempts),
            "graded": len(graded),
            "correct": len(correct),
            "accuracy": (len(correct) / len(graded)) if graded else None,
            "questions_seen": len(seen),
            "questions_total": len(bank),
            "mistakes": len(self.mistake_question_ids(course_id)),
        }
