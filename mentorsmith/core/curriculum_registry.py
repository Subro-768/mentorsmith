"""One entry point for "everything about a language".

Phase 4 gave MentorSmith four tracks. Each one is:

* lessons   - Markdown under ``mentorsmith/lessons/<language>/``
* concepts  - the prerequisite graph
* exercises - the adaptive bank

C++ keeps the files it shipped with (``concepts.json`` / ``exercises.json`` at
the top of ``data/``); the newer languages use a single
``data/curriculum/<language>.json``. This module hides that difference so
callers only ever ask for a language id.

Lesson code fences differ per language too (``python``, ``c``, ``javascript``),
so the fence tag is looked up here rather than guessed by each caller.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..config import lessons_dir
from .concepts import ConceptModel
from .curriculum import Lesson, load_lessons
from .exercises import ExerciseBank

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

#: Markdown code-fence tag per language.
CODE_FENCE: dict[str, str] = {
    "cpp": "cpp",
    "python": "python",
    "c": "c",
    "javascript": "javascript",
}

LANGUAGE_IDS: tuple[str, ...] = ("cpp", "python", "c", "javascript")

LANGUAGE_LABELS: dict[str, str] = {
    "cpp": "C++",
    "python": "Python",
    "c": "C",
    "javascript": "JavaScript",
}

#: Languages whose concepts and exercises live in data/curriculum/<id>.json
#: rather than the original top-level files.
_BUNDLED = {"cpp": None}


class CurriculumError(RuntimeError):
    """A language's curriculum could not be loaded or is inconsistent."""


@dataclass
class Track:
    """Everything MentorSmith knows about one language."""

    language: str
    label: str
    lessons: list[Lesson] = field(default_factory=list)
    model: ConceptModel | None = None
    bank: ExerciseBank | None = None

    @property
    def concept_ids(self) -> list[str]:
        return list(self.model.concepts) if self.model else []

    @property
    def exercise_ids(self) -> list[str]:
        return [e.id for e in self.bank.exercises] if self.bank else []

    def summary(self) -> dict:
        return {
            "language": self.language,
            "label": self.label,
            "lessons": len(self.lessons),
            "concepts": len(self.concept_ids),
            "exercises": len(self.exercise_ids),
        }


def display_name(language: str) -> str:
    return LANGUAGE_LABELS.get(language, language.title())


def known(language: str) -> bool:
    return language in LANGUAGE_IDS


def _load_bundled(language: str) -> tuple[ConceptModel, ExerciseBank]:
    """Load a language's concepts and exercises from a single data file."""
    path = DATA_DIR / "curriculum" / f"{language}.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CurriculumError(f"No curriculum data for '{language}': {path}") from exc
    except json.JSONDecodeError as exc:
        raise CurriculumError(f"Curriculum data for '{language}' is not valid JSON: {exc}") from exc

    # Reuse the C++ loader by writing the two shapes into temporary files it
    # already understands, rather than duplicating its validation rules.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        concepts_file = tmp_path / "concepts.json"
        exercises_file = tmp_path / "exercises.json"
        concepts_file.write_text(
            json.dumps({"concepts": raw.get("concepts", []),
                        "projects": raw.get("projects", [])}),
            encoding="utf-8",
        )
        exercises_file.write_text(
            json.dumps({"exercises": raw.get("exercises", [])}), encoding="utf-8"
        )
        lesson_ids = {lesson.id for lesson in load_lessons(
            language=language, code_fence=CODE_FENCE.get(language, language)
        )}
        model = ConceptModel.load(concepts_file, valid_lesson_ids=lesson_ids)
        bank = ExerciseBank.load(
            exercises_file, known_concepts=set(model.concepts), valid_lesson_ids=lesson_ids
        )
    return model, bank


@lru_cache(maxsize=None)
def load_track(language: str) -> Track:
    """Load and cache one language's lessons, concepts and exercises."""
    if not known(language):
        raise CurriculumError(
            f"Unknown language '{language}'. Known: {', '.join(LANGUAGE_IDS)}"
        )

    lessons = load_lessons(
        language=language, code_fence=CODE_FENCE.get(language, language)
    )

    if language == "cpp":
        # Phase 1/2 shipped these two files separately.
        lesson_ids = {lesson.id for lesson in lessons}
        model = ConceptModel.load(
            DATA_DIR / "concepts.json", valid_lesson_ids=lesson_ids
        )
        bank = ExerciseBank.load(
            DATA_DIR / "exercises.json",
            known_concepts=set(model.concepts),
            valid_lesson_ids=lesson_ids,
        )
    else:
        model, bank = _load_bundled(language)

    return Track(
        language=language,
        label=display_name(language),
        lessons=lessons,
        model=model,
        bank=bank,
    )


def load_all() -> dict[str, Track]:
    """Every language that can be loaded."""
    tracks: dict[str, Track] = {}
    for language in LANGUAGE_IDS:
        try:
            tracks[language] = load_track(language)
        except (CurriculumError, OSError) as exc:
            # One broken track must not stop the others.
            print(f"warning: skipping '{language}': {exc}")
    return tracks


def summaries() -> list[dict]:
    """One summary per loadable language, for the settings and About screens."""
    return [track.summary() for track in load_all().values()]


def total_counts() -> dict[str, int]:
    tracks = load_all()
    return {
        "languages": len(tracks),
        "lessons": sum(len(t.lessons) for t in tracks.values()),
        "concepts": sum(len(t.concept_ids) for t in tracks.values()),
        "exercises": sum(len(t.exercise_ids) for t in tracks.values()),
    }


def clear_cache() -> None:
    """Drop cached tracks, so edited data files are picked up."""
    load_track.cache_clear()