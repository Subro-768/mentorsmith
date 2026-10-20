"""Exam preparation: courses, topics and questions, with honest provenance.

Why this module exists
----------------------
The rest of MentorSmith teaches programming. Exam preparation has a
different requirement: a student has to be able to tell, at a glance,
whether a question is a real past paper, an official sample, something the
project wrote, or something the project predicted. Conflating those is not
a cosmetic problem - a student who believes a predicted question is a past
question is being told something false about an exam.

So the central idea here is that **a question's origin and a question's
verification are two different things**, and both are stored:

``source_type``
    What kind of material the question came from. One of
    :data:`SOURCE_TYPES`.

``verification_status``
    Whether a human has checked that the extraction is faithful and that
    the answer is right. One of :data:`VERIFICATION_STATUSES`.

A question extracted from a past paper is ``source_type=VERIFIED_PYQ`` and
``verification_status=PENDING_REVIEW`` until somebody reads it against the
paper. It is only *labelled* a verified past question once that has
happened - see :attr:`ExamQuestion.display_label`.

The rules the data must obey
----------------------------
* A course cannot claim to be verified without the source metadata that
  makes the claim checkable.
* A question cannot be labelled a verified past question without a source
  file, a page and a question number, and without a human having verified
  it.
* An original or predicted question can never be presented as a past
  question, whatever else is true about it.
* Nothing in this module invents a course code, a syllabus, an exam
  pattern, a mark allocation or a source. Where a fact is not known, the
  field is empty and says so.

Where the data lives
--------------------
The **catalogue** - courses, their format, their unit/topic outline - is
in the repository, because it is metadata and a topic outline, not the
questions.

The **question bank** is not in the repository. Past papers and question
banks are the user's own material and are not ours to redistribute, so the
bank is written to the app's own data directory and never committed. The
importer puts it there.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

# ── The four source types ──────────────────────────────────────────────
#
# The brief this module implements names exactly these four. Adding a fifth
# would mean inventing a category nobody asked for.

#: A question taken from a verified past question paper.
VERIFIED_PYQ = "VERIFIED_PYQ"
#: A question from an officially published sample paper or question bank.
OFFICIAL_SAMPLE = "OFFICIAL_SAMPLE"
#: A question written for this project, by a person.
ORIGINAL_PRACTICE = "ORIGINAL_PRACTICE"
#: A question generated from the syllabus and observed patterns. A
#: prediction, and labelled as one.
PREDICTED_PRACTICE = "PREDICTED_PRACTICE"

SOURCE_TYPES: tuple[str, ...] = (
    VERIFIED_PYQ,
    OFFICIAL_SAMPLE,
    ORIGINAL_PRACTICE,
    PREDICTED_PRACTICE,
)

#: The labels shown in the UI. Deliberately not short: a student has to be
#: able to tell the difference at a glance.
SOURCE_LABELS: dict[str, str] = {
    VERIFIED_PYQ: "Verified past question",
    OFFICIAL_SAMPLE: "Official sample question",
    ORIGINAL_PRACTICE: "Original practice question",
    PREDICTED_PRACTICE: "Predicted practice — not a guaranteed exam question",
}

# ── Verification status ────────────────────────────────────────────────

#: Extracted by a machine, not yet read by a human.
PENDING_REVIEW = "PENDING_REVIEW"
#: A human has checked it against the source.
VERIFIED = "VERIFIED"
#: A human has looked at it and rejected it.
REJECTED = "REJECTED"

VERIFICATION_STATUSES: tuple[str, ...] = (PENDING_REVIEW, VERIFIED, REJECTED)

VERIFICATION_LABELS: dict[str, str] = {
    PENDING_REVIEW: "Pending human review",
    VERIFIED: "Verified by a human",
    REJECTED: "Rejected",
}

# ── Question types ─────────────────────────────────────────────────────

MCQ = "MCQ"
SHORT_ANSWER = "SHORT_ANSWER"
LONG_ANSWER = "LONG_ANSWER"
NUMERICAL = "NUMERICAL"
CODE_TRACING = "CODE_TRACING"
DEBUGGING = "DEBUGGING"
PROGRAMMING = "PROGRAMMING"
TRUE_FALSE = "TRUE_FALSE"

QUESTION_TYPES: tuple[str, ...] = (
    MCQ,
    SHORT_ANSWER,
    LONG_ANSWER,
    NUMERICAL,
    CODE_TRACING,
    DEBUGGING,
    PROGRAMMING,
    TRUE_FALSE,
)

#: Types that can be graded by comparing an answer, with no AI involved.
DETERMINISTIC_TYPES: tuple[str, ...] = (
    MCQ,
    NUMERICAL,
    TRUE_FALSE,
)


class ExamDataError(RuntimeError):
    """The exam data is missing, malformed or internally inconsistent."""


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# ── Topics ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Topic:
    """One unit or topic in a course's outline."""

    id: str
    title: str
    unit: int = 1
    #: Where this outline came from. Empty means the app's own structure.
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "unit": self.unit,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Topic":
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            unit=int(data.get("unit", 1) or 1),
            source=str(data.get("source", "")),
        )


# ── Courses ────────────────────────────────────────────────────────────


@dataclass
class Course:
    """One course, with every fact about it traceable to a source.

    Nothing here is inferred. A field the source did not state is empty,
    and :meth:`verification_status` says the course is only as verified as
    its own metadata allows.
    """

    id: str
    title: str
    institution: str = ""
    campus: str = ""
    programme: str = ""
    branch: str = ""
    semester: str = ""
    #: Only when the source states it.
    course_code: str = ""
    #: Earlier codes for the same course, when the regulation changed.
    previous_course_codes: list[str] = field(default_factory=list)
    #: The regulations this course record is taken from.
    regulation: str = ""
    academic_council: str = ""
    #: The syllabus or course outline this was built from.
    syllabus_source: str = ""
    syllabus_version: str = ""
    department: str = ""
    category: str = ""
    credits: int | None = None
    lecture_hours: int | None = None
    tutorial_hours: int | None = None
    practical_hours: int | None = None
    sessions_per_unit: int | None = None
    #: The exam pattern, only when a source states it.
    exam_pattern: str = ""
    marks: int | None = None
    duration_minutes: int | None = None
    #: The assessment split, as the syllabus states it.
    assessment: dict = field(default_factory=dict)
    #: The course learning outcomes, verbatim.
    outcomes: list[str] = field(default_factory=list)
    rationale: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    #: Provenance for the course record itself.
    source_files: list[str] = field(default_factory=list)
    verification_status: str = PENDING_REVIEW
    last_reviewed: str = ""
    notes: str = ""
    topics: list[Topic] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "institution": self.institution,
            "campus": self.campus,
            "programme": self.programme,
            "branch": self.branch,
            "semester": self.semester,
            "course_code": self.course_code,
            "previous_course_codes": list(self.previous_course_codes),
            "regulation": self.regulation,
            "academic_council": self.academic_council,
            "syllabus_source": self.syllabus_source,
            "syllabus_version": self.syllabus_version,
            "department": self.department,
            "category": self.category,
            "credits": self.credits,
            "lecture_hours": self.lecture_hours,
            "tutorial_hours": self.tutorial_hours,
            "practical_hours": self.practical_hours,
            "sessions_per_unit": self.sessions_per_unit,
            "exam_pattern": self.exam_pattern,
            "marks": self.marks,
            "duration_minutes": self.duration_minutes,
            "assessment": dict(self.assessment),
            "outcomes": list(self.outcomes),
            "rationale": list(self.rationale),
            "references": list(self.references),
            "source_files": list(self.source_files),
            "verification_status": self.verification_status,
            "last_reviewed": self.last_reviewed,
            "notes": self.notes,
            "topics": [t.to_dict() for t in self.topics],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Course":
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            institution=str(data.get("institution", "")),
            campus=str(data.get("campus", "")),
            programme=str(data.get("programme", "")),
            branch=str(data.get("branch", "")),
            semester=str(data.get("semester", "")),
            course_code=str(data.get("course_code", "")),
            previous_course_codes=[
                str(c) for c in data.get("previous_course_codes", [])
            ],
            regulation=str(data.get("regulation", "")),
            academic_council=str(data.get("academic_council", "")),
            syllabus_source=str(data.get("syllabus_source", "")),
            syllabus_version=str(data.get("syllabus_version", "")),
            department=str(data.get("department", "")),
            category=str(data.get("category", "")),
            credits=data.get("credits"),
            lecture_hours=data.get("lecture_hours"),
            tutorial_hours=data.get("tutorial_hours"),
            practical_hours=data.get("practical_hours"),
            sessions_per_unit=data.get("sessions_per_unit"),
            exam_pattern=str(data.get("exam_pattern", "")),
            marks=data.get("marks"),
            duration_minutes=data.get("duration_minutes"),
            assessment=dict(data.get("assessment", {})),
            outcomes=[str(o) for o in data.get("outcomes", [])],
            rationale=[str(r) for r in data.get("rationale", [])],
            references=[str(r) for r in data.get("references", [])],
            source_files=[str(f) for f in data.get("source_files", [])],
            verification_status=str(
                data.get("verification_status", PENDING_REVIEW)
            ),
            last_reviewed=str(data.get("last_reviewed", "")),
            notes=str(data.get("notes", "")),
            topics=[Topic.from_dict(t) for t in data.get("topics", [])],
        )

    @property
    def units(self) -> list[int]:
        return sorted({t.unit for t in self.topics})

    def topics_in_unit(self, unit: int) -> list[Topic]:
        return [t for t in self.topics if t.unit == unit]

    def validate(self) -> None:
        """Check the course against the rules.

        A course may not claim to be verified without the metadata that
        makes the claim checkable: a course code, and at least one source
        file, and something to say about which syllabus it follows.
        """
        if not self.id:
            raise ExamDataError("A course must have an id.")
        if not self.title:
            raise ExamDataError(f"Course '{self.id}' has no title.")
        if self.verification_status not in VERIFICATION_STATUSES:
            raise ExamDataError(
                f"Course '{self.id}' has an unknown verification status "
                f"{self.verification_status!r}."
            )
        if self.verification_status == VERIFIED:
            missing = [
                name
                for name, value in (
                    ("course_code", self.course_code),
                    ("syllabus_source", self.syllabus_source),
                    ("source_files", self.source_files),
                )
                if not value
            ]
            if missing:
                raise ExamDataError(
                    f"Course '{self.id}' claims to be verified but has no "
                    f"{', '.join(missing)}. A verified course needs the "
                    f"metadata that makes the claim checkable."
                )
        seen: set[str] = set()
        for topic in self.topics:
            if not topic.id:
                raise ExamDataError(f"Course '{self.id}' has a topic with no id.")
            if topic.id in seen:
                raise ExamDataError(
                    f"Course '{self.id}' has two topics with the id "
                    f"{topic.id!r}."
                )
            seen.add(topic.id)


# ── Questions ──────────────────────────────────────────────────────────


@dataclass
class ExamQuestion:
    """One question in an exam-preparation bank.

    Every field the brief asks for is here, and the ones that would be
    invented are optional and empty by default.
    """

    id: str
    course_id: str
    question_text: str
    question_type: str = MCQ
    #: Topic and concept identifiers, matched to the course outline.
    topic_ids: list[str] = field(default_factory=list)
    #: The unit, for grouping.
    unit: int = 0
    #: Options for a multiple-choice question.
    options: list[str] = field(default_factory=list)
    #: The correct option's text, for a multiple-choice question.
    answer: str = ""
    #: A worked explanation, shown after an answer.
    explanation: str = ""
    #: A marking rubric for free-text answers.
    rubric: list[str] = field(default_factory=list)
    #: Marks, only when a source states them. Otherwise a practice
    #: estimate, and ``marks_is_estimate`` says so.
    marks: int | None = None
    marks_is_estimate: bool = False
    difficulty: str = ""
    estimated_minutes: int = 0
    #: Where the question came from.
    source_type: str = ORIGINAL_PRACTICE
    source_title: str = ""
    source_file: str = ""
    source_page: int | None = None
    source_question_number: str = ""
    #: The exam this came from, when known.
    exam_name: str = ""
    exam_session: str = ""
    exam_date: str = ""
    #: Whether a human has checked the extraction and the answer.
    verification_status: str = PENDING_REVIEW
    verified_by: str = ""
    verified_at: str = ""
    #: Why this question was generated, for a predicted one.
    generation_reason: str = ""
    #: How many verified papers the pattern behind it came from.
    pattern_sample_size: int = 0
    #: Whether the content may be redistributed. Past papers usually may
    #: not, which is why the bank is kept on the learner's own disk.
    redistribution_status: str = "not_for_redistribution"
    tags: list[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    version: int = 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "course_id": self.course_id,
            "question_text": self.question_text,
            "question_type": self.question_type,
            "topic_ids": list(self.topic_ids),
            "unit": self.unit,
            "options": list(self.options),
            "answer": self.answer,
            "explanation": self.explanation,
            "rubric": list(self.rubric),
            "marks": self.marks,
            "marks_is_estimate": self.marks_is_estimate,
            "difficulty": self.difficulty,
            "estimated_minutes": self.estimated_minutes,
            "source_type": self.source_type,
            "source_title": self.source_title,
            "source_file": self.source_file,
            "source_page": self.source_page,
            "source_question_number": self.source_question_number,
            "exam_name": self.exam_name,
            "exam_session": self.exam_session,
            "exam_date": self.exam_date,
            "verification_status": self.verification_status,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at,
            "generation_reason": self.generation_reason,
            "pattern_sample_size": self.pattern_sample_size,
            "redistribution_status": self.redistribution_status,
            "tags": list(self.tags),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ExamQuestion":
        return cls(
            id=str(data.get("id", "")),
            course_id=str(data.get("course_id", "")),
            question_text=str(data.get("question_text", "")),
            question_type=str(data.get("question_type", MCQ)),
            topic_ids=[str(t) for t in data.get("topic_ids", [])],
            unit=int(data.get("unit", 0) or 0),
            options=[str(o) for o in data.get("options", [])],
            answer=str(data.get("answer", "")),
            explanation=str(data.get("explanation", "")),
            rubric=[str(r) for r in data.get("rubric", [])],
            marks=data.get("marks"),
            marks_is_estimate=bool(data.get("marks_is_estimate", False)),
            difficulty=str(data.get("difficulty", "")),
            estimated_minutes=int(data.get("estimated_minutes", 0) or 0),
            source_type=str(data.get("source_type", ORIGINAL_PRACTICE)),
            source_title=str(data.get("source_title", "")),
            source_file=str(data.get("source_file", "")),
            source_page=data.get("source_page"),
            source_question_number=str(data.get("source_question_number", "")),
            exam_name=str(data.get("exam_name", "")),
            exam_session=str(data.get("exam_session", "")),
            exam_date=str(data.get("exam_date", "")),
            verification_status=str(
                data.get("verification_status", PENDING_REVIEW)
            ),
            verified_by=str(data.get("verified_by", "")),
            verified_at=str(data.get("verified_at", "")),
            generation_reason=str(data.get("generation_reason", "")),
            pattern_sample_size=int(data.get("pattern_sample_size", 0) or 0),
            redistribution_status=str(
                data.get("redistribution_status", "not_for_redistribution")
            ),
            tags=[str(t) for t in data.get("tags", [])],
            created_at=str(data.get("created_at", "")),
            updated_at=str(data.get("updated_at", "")),
            version=int(data.get("version", 1) or 1),
        )

    # -- labels -------------------------------------------------------
    @property
    def display_label(self) -> str:
        """The badge shown next to the question.

        A question from a past paper is only labelled a *verified* past
        question once a human has read it. Until then the badge says so,
        because the difference is the whole point of the labelling.
        """
        if self.source_type == VERIFIED_PYQ:
            if self.verification_status == VERIFIED:
                return SOURCE_LABELS[VERIFIED_PYQ]
            if self.verification_status == REJECTED:
                return "Rejected past question"
            return "Past question — extraction pending human review"
        if self.source_type == OFFICIAL_SAMPLE:
            if self.verification_status == VERIFIED:
                return SOURCE_LABELS[OFFICIAL_SAMPLE]
            if self.verification_status == REJECTED:
                return "Rejected sample question"
            return "Sample question — pending human review"
        return SOURCE_LABELS[self.source_type]

    @property
    def is_past_question(self) -> bool:
        """Whether this is *sourced* from a past paper, verified or not."""
        return self.source_type == VERIFIED_PYQ

    @property
    def needs_review(self) -> bool:
        return self.verification_status == PENDING_REVIEW

    @property
    def answer_matches_an_option(self) -> bool:
        """Whether the answer is one of the options as extracted.

        False means the extraction of the options is suspect: a student
        could not pick it, so the question cannot be graded automatically.
        """
        if not self.answer.strip():
            return False
        return normalise_text(self.answer) in {
            normalise_text(option) for option in self.options
        }

    @property
    def gradable(self) -> bool:
        """Whether this question can be marked automatically.

        Needs a key, and - for a multiple-choice question - a key that is
        one of the options, because a student picks an option and nothing
        else.
        """
        if not self.answer.strip():
            return False
        if self.question_type == MCQ:
            return self.answer_matches_an_option
        return True

    @property
    def source_reference(self) -> str:
        """A human-readable pointer back to the source.

        Enough for somebody to open the paper and find the question.
        """
        parts = [self.source_title or self.source_file or "unknown source"]
        if self.source_page is not None:
            parts.append(f"p. {self.source_page}")
        if self.source_question_number:
            parts.append(f"Q{self.source_question_number}")
        if self.exam_date or self.exam_session:
            bits = [b for b in (self.exam_session, self.exam_date) if b]
            if bits:
                parts.append(" ".join(bits))
        return " · ".join(parts)

    def validate(self) -> None:
        """Check the question against the rules."""
        if not self.id:
            raise ExamDataError("A question must have an id.")
        if not self.course_id:
            raise ExamDataError(f"Question '{self.id}' has no course.")
        if not self.question_text.strip():
            raise ExamDataError(f"Question '{self.id}' has no text.")
        if self.source_type not in SOURCE_TYPES:
            raise ExamDataError(
                f"Question '{self.id}' has an unknown source type "
                f"{self.source_type!r}. Valid types: {', '.join(SOURCE_TYPES)}"
            )
        if self.verification_status not in VERIFICATION_STATUSES:
            raise ExamDataError(
                f"Question '{self.id}' has an unknown verification status "
                f"{self.verification_status!r}."
            )
        if self.question_type not in QUESTION_TYPES:
            raise ExamDataError(
                f"Question '{self.id}' has an unknown type "
                f"{self.question_type!r}."
            )

        # A question that is going to be *called* a verified past question
        # needs the source details that make the claim checkable.
        if self.verification_status == VERIFIED:
            if self.source_type in (VERIFIED_PYQ, OFFICIAL_SAMPLE):
                missing = [
                    name
                    for name, value in (
                        ("source_file", self.source_file),
                        ("source_page", self.source_page),
                        ("source_question_number", self.source_question_number),
                    )
                    if not value
                ]
                if missing:
                    raise ExamDataError(
                        f"Question '{self.id}' is marked verified but has no "
                        f"{', '.join(missing)}. A verified question needs to "
                        f"point at the exact place in the source."
                    )
            if self.source_type == PREDICTED_PRACTICE and not self.generation_reason:
                raise ExamDataError(
                    f"Question '{self.id}' is a predicted question with no "
                    f"reason. A prediction has to say why it was predicted."
                )

        # A multiple-choice question without options cannot be answered.
        if self.question_type == MCQ:
            if len(self.options) < 2:
                raise ExamDataError(
                    f"Question '{self.id}' is multiple choice but has fewer "
                    f"than two options."
                )
            # An answer that is not among the extracted options is allowed,
            # because the *extraction* may be what is wrong: the paper's
            # options can be garbled, or split across two columns and read
            # as one. The question is flagged rather than rejected - see
            # :attr:`gradable`.
            # A missing answer is only allowed while the question is still
            # awaiting review. A paper does not always print a key, and
            # inventing one from a pattern would be worse than having none;
            # but a question that is *verified* must have been checked
            # against an answer.
            if not self.answer.strip() and self.verification_status == VERIFIED:
                raise ExamDataError(
                    f"Question '{self.id}' is marked verified but has no "
                    f"answer. A verified question has been checked against "
                    f"an answer key."
                )

        if self.marks is not None and self.marks < 0:
            raise ExamDataError(f"Question '{self.id}' has negative marks.")


# ── Loading and saving ─────────────────────────────────────────────────

CATALOGUE_PATH = Path(__file__).resolve().parent.parent / "data" / "exam" / "courses.json"


def exam_data_dir() -> Path:
    """Where the local question bank lives.

    Never the repository: past papers and question banks are the user's own
    material, and redistributing them is not ours to do.
    """
    base = os.environ.get("XDG_DATA_HOME", "").strip()
    root = Path(base) if base else Path.home() / ".local" / "share"
    return root / "mentorsmith" / "exam"


def load_courses(path: Path | None = None) -> list[Course]:
    """Load the course catalogue. Empty list if there is none."""
    source = Path(path) if path else CATALOGUE_PATH
    if not source.exists():
        return []
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExamDataError(
            f"Course catalogue is not valid JSON: {exc}"
        ) from None
    courses = [Course.from_dict(c) for c in raw.get("courses", [])]
    for course in courses:
        course.validate()
    return courses


def get_course(course_id: str, path: Path | None = None) -> Course | None:
    for course in load_courses(path):
        if course.id == course_id:
            return course
    return None


def bank_path() -> Path:
    return exam_data_dir() / "questions.json"


def load_questions(course_id: str | None = None) -> list[ExamQuestion]:
    """Load the local question bank.

    Returns an empty list when there is none, which is the normal case for
    a fresh install: the learner imports their own papers.
    """
    path = bank_path()
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ExamDataError(f"Question bank is not valid JSON: {exc}") from None
    questions = [ExamQuestion.from_dict(q) for q in raw.get("questions", [])]
    if course_id is not None:
        questions = [q for q in questions if q.course_id == course_id]
    return questions


def save_questions(questions: list[ExamQuestion]) -> Path:
    """Write the question bank to the app's data directory."""
    for question in questions:
        question.validate()
    path = bank_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_comment": (
            "Local question bank. Not part of the repository: it holds the "
            "learner's own papers, which are not ours to redistribute."
        ),
        "questions": [q.to_dict() for q in questions],
    }
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:  # pragma: no cover - platform dependent
        pass
    return path


def normalise_text(text: str) -> str:
    """A comparable form of a question, for duplicate detection.

    Whitespace and case are ignored, because the same question typeset in
    two columns of two different banks differs in spacing and nothing else
    that matters.
    """
    return " ".join(text.lower().split())


def merge_questions(new: list[ExamQuestion]) -> dict[str, int]:
    """Add questions to the bank, skipping anything already there.

    Two kinds of duplicate are caught:

    * the **same id** - re-importing the same paper, which the importer is
      expected to be run more than once;
    * the **same text** under a different id - the same question appearing
      in two different banks, which is exactly what happened between the
      course's own question bank and its alternate one.

    Returns a count of what happened: ``added``, ``already_present`` and
    ``duplicates``.
    """
    existing = load_questions()
    by_id = {q.id: q for q in existing}
    by_text = {normalise_text(q.question_text): q.id for q in existing}

    added = 0
    already_present = 0
    duplicates = 0

    for question in new:
        if question.id in by_id:
            already_present += 1
            continue
        key = normalise_text(question.question_text)
        if key and key in by_text:
            duplicates += 1
            continue
        if not question.created_at:
            question.created_at = _now()
        by_id[question.id] = question
        if key:
            by_text[key] = question.id
        added += 1

    save_questions(list(by_id.values()))
    return {
        "added": added,
        "already_present": already_present,
        "duplicates": duplicates,
    }


def set_answer(question_id: str, answer: str) -> ExamQuestion | None:
    """Record the answer key for a question.

    The papers do not print one, so this is how a question becomes
    gradable: the student looks it up in their own copy of the paper and
    types it in.
    """
    questions = load_questions()
    for question in questions:
        if question.id == question_id:
            question.answer = answer.strip()
            question.updated_at = _now()
            question.version += 1
            save_questions(questions)
            return question
    return None


def mark_verified(
    question_id: str,
    *,
    answer: str = "",
    verified_by: str = "",
    explanation: str = "",
    marks: int | None = None,
) -> ExamQuestion | None:
    """Promote a question to verified, after a human has checked it.

    This is the only way a question becomes a *verified past question*,
    and it is deliberately explicit: the caller says who checked it and
    when. The answer key can be set at the same time, because checking a
    question against the paper means reading its answer too.
    """
    questions = load_questions()
    for question in questions:
        if question.id != question_id:
            continue
        if answer:
            question.answer = answer.strip()
        if explanation:
            question.explanation = explanation
        if marks is not None:
            question.marks = marks
            question.marks_is_estimate = False
        question.verification_status = VERIFIED
        question.verified_by = verified_by or "the learner"
        question.verified_at = _now()
        question.updated_at = question.verified_at
        question.version += 1
        save_questions(questions)
        return question
    return None


def pending_questions(course_id: str | None = None) -> list[ExamQuestion]:
    """The questions still waiting for a human to check them."""
    return [
        q for q in load_questions(course_id)
        if q.verification_status == PENDING_REVIEW
    ]


def review_report() -> dict:
    """A report of what in the bank still needs a human.

    The brief asks for exactly this: "a report/export of unverified,
    missing-source, duplicate or possibly incorrect questions".
    """
    questions = load_questions()
    pending = [q for q in questions if q.verification_status == PENDING_REVIEW]
    missing_source = [
        q for q in questions
        if q.source_type in (VERIFIED_PYQ, OFFICIAL_SAMPLE)
        and not (q.source_file and q.source_page and q.source_question_number)
    ]
    no_answer = [q for q in questions if not q.answer.strip() and not q.rubric]
    ungradable = [
        q for q in questions
        if q.question_type == MCQ and q.answer.strip() and not q.answer_matches_an_option
    ]
    seen: dict[str, list[str]] = {}
    for question in questions:
        key = " ".join(question.question_text.lower().split())
        seen.setdefault(key, []).append(question.id)
    duplicates = {k: v for k, v in seen.items() if len(v) > 1}
    return {
        "total": len(questions),
        "pending_review": pending,
        "missing_source": missing_source,
        "no_answer": no_answer,
        "ungradable": ungradable,
        "duplicate_groups": duplicates,
    }
