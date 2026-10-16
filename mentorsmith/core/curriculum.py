"""Lesson loading and the on-disk lesson format.

Lessons live as Markdown files under ``mentorsmith/lessons``. Keeping the
curriculum out of the UI means content can be edited, reviewed and versioned
without touching Python.

File format
-----------
Simple ``---`` front matter followed by ``##`` sections::

    ---
    id: 01-program-structure
    title: Program Structure
    order: 1
    ---

    ## Objectives
    - Bullet points

    ## Example
    ```cpp
    int main() { return 0; }
    ```

    ## Knowledge checks
    Q: What does ``main`` return?
    A: An exit status.

    ## Exercise
    ```cpp starter
    int main() { /* your code */ }
    ```

Sections are matched case-insensitively and normalised to the keys used by
:class:`Lesson` (``objectives``, ``explanation``, ``example``,
``knowledge_checks``, ``exercise``, ``common_mistakes``, ``recap``). Any
unrecognised section is still parsed and kept, so a lesson can add content
without needing a code change.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..config import LESSONS_DIR, lessons_dir

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"^```(\w*)(?:\s+(\w+))?\s*$")
QA_RE = re.compile(r"^\s*Q:\s*(.+?)\s*$", re.IGNORECASE)
ANS_RE = re.compile(r"^\s*A:\s*(.+?)\s*$", re.IGNORECASE)

#: Canonical section names, in the order they are displayed.
CANONICAL_SECTIONS = (
    "objectives",
    "explanation",
    "example",
    "knowledge_checks",
    "exercise",
    "common_mistakes",
    "recap",
)


def _slug_to_title(slug: str) -> str:
    return " ".join(word.capitalize() for word in slug.replace("_", "-").split("-") if word)


def _normalise_key(raw: str) -> str:
    """``'Common Mistakes'`` -> ``'common_mistakes'``."""
    return re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")


@dataclass
class Lesson:
    """A single curriculum entry."""

    id: str
    title: str
    order: int
    sections: dict[str, str] = field(default_factory=dict)
    example_code: str = ""
    starter_code: str = ""
    checks: list[tuple[str, str]] = field(default_factory=list)
    source_path: Path | None = None
    #: Language this lesson belongs to. Defaults to ``cpp`` so Phase 1 and 2
    #: call sites that never knew about languages keep working.
    language: str = "cpp"

    @property
    def key(self) -> str:
        """Globally unique identity: a lesson id can repeat across languages."""
        return f"{self.language}:{self.id}"

    def section(self, name: str) -> str:
        """Raw Markdown body of a section, or an empty string."""
        return self.sections.get(name, "")

    def has_section(self, name: str) -> bool:
        return bool(self.sections.get(name, "").strip())

    @property
    def display_title(self) -> str:
        """Title prefixed with the lesson number, e.g. ``'3. Input / Output'``."""
        return f"{self.order}. {self.title}" if self.order else self.title


class CurriculumError(RuntimeError):
    """Raised when the lessons directory cannot be loaded."""


def _parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    """Split ``---`` front matter from the body without a YAML dependency."""
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        meta[key.strip().lower()] = value.strip().strip("'\"")
    return meta, text[match.end():]


def _parse_sections(body: str) -> dict[str, str]:
    """Split a lesson body into ``{normalised_key: markdown}``."""
    parts: list[tuple[str, str]] = []
    matches = list(HEADING_RE.finditer(body))
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        parts.append((match.group(1), body[start:end].strip("\n")))
    sections: dict[str, str] = {}
    for raw_title, content in parts:
        key = _normalise_key(raw_title)
        # A repeated heading appends rather than replaces, so a lesson can
        # split a long explanation across two same-named headings.
        if key in sections and sections[key]:
            sections[key] = sections[key] + "\n\n" + content
        else:
            sections[key] = content
    return sections


def _extract_fenced_code(section: str, language: str) -> str:
    """Return the body of the first fenced block matching ``language``.

    An optional tag after the language (``cpp starter``) is allowed.
    """
    lines = section.splitlines()
    collecting = False
    buffer: list[str] = []
    current_lang = ""
    for line in lines:
        fence = FENCE_RE.match(line.strip())
        if fence and not collecting:
            current_lang = (fence.group(1) or "").lower()
            collecting = current_lang == language
            continue
        if fence and collecting:
            break
        if collecting:
            buffer.append(line)
    return "\n".join(buffer).strip("\n")


def _extract_checks(section: str) -> list[tuple[str, str]]:
    """Parse ``Q:`` / ``A:`` pairs into (question, answer) tuples.

    A question with no ``A:`` line still yields a tuple so the UI can prompt
    for a free-text answer instead of silently dropping it.
    """
    checks: list[tuple[str, str]] = []
    question: str | None = None
    answers: list[str] = []
    for line in section.splitlines():
        if not line.strip():
            continue
        q_match = QA_RE.match(line)
        if q_match:
            if question is not None:
                checks.append((question, " ".join(answers).strip()))
            question = q_match.group(1)
            answers = []
            continue
        a_match = ANS_RE.match(line)
        if a_match and question is not None:
            answers.append(a_match.group(1))
            continue
        # Continuation of a multi-line answer.
        if question is not None and answers and line.startswith((" ", "\t")):
            answers.append(line.strip())
    if question is not None:
        checks.append((question, " ".join(answers).strip()))
    return checks


def parse_lesson(path: Path, language: str = "cpp") -> Lesson:
    """Read and parse one lesson Markdown file."""
    text = path.read_text(encoding="utf-8")
    meta, body = _parse_front_matter(text)
    sections = _parse_sections(body)

    lesson_id = meta.get("id") or path.stem
    title = meta.get("title") or _slug_to_title(lesson_id)
    try:
        order = int(meta.get("order", "0"))
    except ValueError:
        order = 0

    exercise = sections.get("exercise", "")
    return Lesson(
        id=lesson_id,
        title=title,
        order=order,
        sections=sections,
        example_code=_extract_fenced_code(sections.get("example", ""), "cpp"),
        starter_code=_extract_fenced_code(exercise, "cpp"),
        checks=_extract_checks(sections.get("knowledge_checks", "")),
        source_path=path,
        language=language,
    )


def load_lessons(
    directory: Path | None = None,
    language: str = "cpp",
    code_fence: str = "cpp",
) -> list[Lesson]:
    """Load every ``*.md`` lesson for a language, sorted by order then title.

    ``code_fence`` is the language tag used inside the Markdown for code
    blocks. C++ lessons use ``cpp``; Python and JavaScript lessons use their
    own tags so the renderer can highlight appropriately.
    """
    root = Path(directory) if directory is not None else lessons_dir(language)
    if not root.exists():
        raise CurriculumError(f"Lessons directory not found: {root}")
    lessons: list[Lesson] = []
    for path in sorted(root.glob("*.md")):
        try:
            lesson = parse_lesson(path, language=language)
            # Re-extract using this language's fence tag when it differs.
            if code_fence != "cpp":
                exercise = lesson.sections.get("exercise", "")
                lesson.example_code = _extract_fenced_code(
                    lesson.sections.get("example", ""), code_fence
                ) or lesson.example_code
                lesson.starter_code = (
                    _extract_fenced_code(exercise, code_fence) or lesson.starter_code
                )
            lessons.append(lesson)
        except OSError as exc:
            raise CurriculumError(f"Could not read lesson {path}: {exc}") from exc
    if not lessons:
        raise CurriculumError(f"No lessons found in {root}")
    lessons.sort(key=lambda item: (item.order, item.title))
    return lessons


def lesson_index(lessons: list[Lesson]) -> dict[str, int]:
    """Map lesson id to its position, for 'next lesson' navigation."""
    return {lesson.id: index for index, lesson in enumerate(lessons)}


def adjacent_lesson(lessons: list[Lesson], lesson_id: str, step: int) -> Lesson | None:
    """Return the lesson ``step`` positions away, or ``None`` at either end."""
    index = lesson_index(lessons).get(lesson_id)
    if index is None:
        return None
    target = index + step
    if 0 <= target < len(lessons):
        return lessons[target]
    return None