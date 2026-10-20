"""Theory book core module.

Loads, indexes, searches, and caches conceptual reference chapters for every
language MentorSmith supports. The chapters themselves are Markdown files under
``mentorsmith/data/theory/<language>/`` - content lives in data, not here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re

THEORY_DIR = Path(__file__).resolve().parent.parent / "data" / "theory"

#: The books the theory chapters are written to accompany.
#:
#: These are the learner's own copies. The app does not ship them, does not
#: copy them, and never quotes them at length: each chapter is an original
#: explanation that follows the book's order, so a learner reading the book
#: and the app side by side sees the same material in the same sequence.
#:
#: The PDF is looked up at runtime rather than stored, because a copy on the
#: learner's disk is what they own, and the app has no business duplicating
#: a copyrighted book into its own data directory.
BOOKS: dict[str, dict[str, str]] = {
    "java": {
        "title": "Programming with Java: A Primer",
        "author": "E. Balagurusamy",
        "edition": "Third Edition",
        "publisher": "Tata McGraw-Hill",
    },
    "cpp": {
        "title": "Object Oriented Programming with C++",
        "author": "Dr. Dhamodharan G, Dr. Balasubramanian, Dr. Priya K",
        "edition": "First Edition",
        "publisher": "Emperor Research Foundation (Mayas Publication)",
    },
    "c": {
        "title": "Programming in ANSI C",
        "author": "Ray Dawson",
        "edition": "Third Edition",
        "publisher": "Group D Publications",
    },
}

#: The book the exam answer key was written against. Recorded because the
#: key is a derived artefact and the learner is entitled to know what it was
#: derived from.
ANSWER_KEY_REFERENCE = {
    "title": "The C Programming Language",
    "author": "Brian Kernighan and Dennis Ritchie",
    "edition": "Second Edition",
}

#: Where a learner's copy of the book might be, in order of preference.
#: ``MENTORSMITH_BOOKS_DIR`` wins, then the checkout's ``theory/`` folder,
#: then the app's own data directory.
BOOK_SEARCH_PATHS = (
    "{home}/books/{language}",
    "{home}/data/mentorsmith/books/{language}",
)


def book_info(language: str) -> dict[str, str]:
    """Details of the book a language's theory follows. Empty if none."""
    return dict(BOOKS.get(language, {}))


def find_book_pdf(language: str) -> Path | None:
    """Locate the learner's copy of the book, if they have one on disk.

    Returns None rather than raising: not having the PDF is the normal case
    for most installs, and the theory chapters are useful without it.
    """
    import os

    candidates: list[Path] = []

    override = os.environ.get("MENTORSMITH_BOOKS_DIR", "").strip()
    if override:
        candidates.append(Path(override).expanduser() / language)

    # A checkout of the project, which is where the books were put. The
    # folder is named "C++" for the C++ book, so match case-insensitively
    # and treat "c++" as another name for "cpp".
    repo_root = Path(__file__).resolve().parent.parent.parent
    theory_root = repo_root / "theory"
    candidates.append(theory_root / language)
    if theory_root.is_dir():
        wanted = {language.lower(), "c++" if language == "cpp" else language}
        for folder in theory_root.iterdir():
            if folder.is_dir() and folder.name.lower() in wanted:
                candidates.append(folder)

    data_home = os.environ.get("XDG_DATA_HOME", "").strip()
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    for template in BOOK_SEARCH_PATHS:
        candidates.append(Path(template.format(home=base, language=language)))

    for folder in candidates:
        if not folder.is_dir():
            continue
        pdfs = sorted(folder.glob("*.pdf"))
        if pdfs:
            return pdfs[0]
    return None

FRONT_MATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class TheoryChapter:
    """A comprehensive reference chapter in the Theory Book."""

    id: str
    title: str
    order: int
    language: str
    summary: str = ""
    content: str = ""
    reading_time_mins: int = 5
    tags: list[str] = field(default_factory=list)
    lesson_id: str | None = None
    #: The book this chapter is written to accompany, if any.
    source_book: str = ""
    source_author: str = ""
    source_chapter: str = ""
    #: Page in the source book where the matching material starts.
    source_page: int | None = None

    @property
    def display_title(self) -> str:
        return f"{self.order}. {self.title}" if self.order else self.title

    @property
    def has_source(self) -> bool:
        return bool(self.source_book or self.source_chapter)

    @property
    def source_line(self) -> str:
        """A one-line note saying which book section this follows.

        Empty when the chapter has no book behind it, rather than a
        placeholder that reads like a missing reference.
        """
        if not self.has_source:
            return ""
        bits = []
        if self.source_book:
            # No markdown asterisks: this line goes into a plain-text label,
            # where they would be shown rather than interpreted.
            bits.append(self.source_book)
            if self.source_author:
                bits.append(f"({self.source_author})")
        if self.source_chapter:
            bits.append(f"ch. {self.source_chapter}")
        if self.source_page:
            bits.append(f"p. {self.source_page}")
        return "Companion reading: " + ", ".join(bits)


@dataclass
class TheorySearchResult:
    """A match from searching through the Theory Book."""

    chapter: TheoryChapter
    snippet: str
    matched_term: str


def _estimate_reading_time(text: str) -> int:
    """Rough reading time based on 200 words per minute."""
    words = len(text.split())
    return max(2, round(words / 200))


def _parse_chapter_file(path: Path, language: str) -> TheoryChapter:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = raw

    match = FRONT_MATTER_RE.match(raw)
    if match:
        body = raw[match.end():]
        for line in match.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()

    stem = path.stem
    cid = meta.get("id", stem)
    title = meta.get("title", stem.replace("-", " ").title())
    try:
        order = int(meta.get("order", "0"))
    except ValueError:
        order = 0

    if not order and stem[:2].isdigit():
        try:
            order = int(stem[:2])
        except ValueError:
            pass

    summary = meta.get("summary", "")
    lesson_id = meta.get("lesson_id", cid)
    tags_raw = meta.get("tags", "")
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    source_page: int | None = None
    page_raw = meta.get("source_page", "").strip()
    if page_raw:
        try:
            source_page = int(page_raw)
        except ValueError:
            # A page written as "207-209" or "p. 207" is still useful, but it
            # is not a number and pretending otherwise would put nonsense in
            # a link. It is kept as text and the numeric field stays empty.
            source_page = None

    reading_time = _estimate_reading_time(body)

    return TheoryChapter(
        id=cid,
        title=title,
        order=order,
        language=language,
        summary=summary,
        content=body,
        reading_time_mins=reading_time,
        tags=tags,
        lesson_id=lesson_id,
        source_book=meta.get("source_book", ""),
        source_author=meta.get("source_author", ""),
        source_chapter=meta.get("source_chapter", ""),
        source_page=source_page,
    )


#: Chapters that failed to parse, as ``(path, message)``.
#:
#: Populated by :func:`load_chapters` and cleared by :func:`clear_cache`. A
#: chapter that cannot be parsed used to be skipped with a bare ``print``,
#: which is invisible in a GUI application: the chapter simply was not there,
#: with nothing on screen or in the logs explaining why. A missing chapter is
#: indistinguishable from one that was never written, so the failure is
#: recorded where the UI can show it.
_LOAD_FAILURES: list[tuple[str, str]] = []


def load_failures(language: str | None = None) -> list[tuple[str, str]]:
    """Chapters that failed to parse.

    Pass a language to see only its failures.
    """
    if language is None:
        return list(_LOAD_FAILURES)
    prefix = str(THEORY_DIR / language) + "/"
    return [(p, m) for p, m in _LOAD_FAILURES if p.startswith(prefix)]


@lru_cache(maxsize=None)
def load_chapters(language: str) -> tuple[TheoryChapter, ...]:
    """Load and cache all chapters for a language in canonical order.

    Returns a **tuple**, not a list. This result is cached and shared by every
    caller, so a list handed out here is a list any caller can mutate: one
    ``.append()`` or ``.sort()`` silently rewrites the cache for the whole
    session. Nothing does that today, which is exactly why it is worth closing
    rather than leaving to chance.
    """
    lang_dir = THEORY_DIR / language
    if not lang_dir.exists():
        return ()

    chapters: list[TheoryChapter] = []
    for path in sorted(lang_dir.glob("*.md")):
        try:
            chapters.append(_parse_chapter_file(path, language))
        except Exception as exc:  # noqa: BLE001 - one bad file must not hide the rest
            message = f"{type(exc).__name__}: {exc}"
            _LOAD_FAILURES.append((str(path), message))
            # Also to stderr, so it is visible when launched from a terminal.
            print(f"Warning: failed to load theory chapter {path}: {message}")

    chapters.sort(key=lambda c: (c.order, c.title))
    return tuple(chapters)


def get_chapter(language: str, chapter_id: str) -> TheoryChapter | None:
    """Get a specific chapter by id."""
    for ch in load_chapters(language):
        if ch.id == chapter_id or ch.lesson_id == chapter_id:
            return ch
    return None


def search_theory(language: str, query: str) -> list[TheorySearchResult]:
    """Search for matching keywords in a language's theory book."""
    q = query.strip().lower()
    if not q:
        return []

    results: list[TheorySearchResult] = []
    for ch in load_chapters(language):
        text_lower = ch.content.lower()
        title_lower = ch.title.lower()
        summary_lower = ch.summary.lower()

        if q in title_lower or q in summary_lower or q in text_lower:
            # Extract snippet
            idx = text_lower.find(q)
            if idx != -1:
                start = max(0, idx - 60)
                end = min(len(ch.content), idx + len(q) + 60)
                snippet = "..." + ch.content[start:end].replace("\n", " ").strip() + "..."
            else:
                snippet = ch.summary or ch.title
            results.append(TheorySearchResult(chapter=ch, snippet=snippet, matched_term=query))

    return results


def clear_cache() -> None:
    """Clear the memory cache and the recorded failures, for a reload."""
    load_chapters.cache_clear()
    _LOAD_FAILURES.clear()
