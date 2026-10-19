"""Theory book core module.

Loads, indexes, searches, and caches comprehensive conceptual reference
chapters for all programming languages supported in MentorSmith.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
import re

THEORY_DIR = Path(__file__).resolve().parent.parent / "data" / "theory"

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

    @property
    def display_title(self) -> str:
        return f"{self.order}. {self.title}" if self.order else self.title


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
    )


@lru_cache(maxsize=None)
def load_chapters(language: str) -> list[TheoryChapter]:
    """Load and cache all chapters for a language in canonical order."""
    lang_dir = THEORY_DIR / language
    if not lang_dir.exists():
        return []

    chapters: list[TheoryChapter] = []
    for path in sorted(lang_dir.glob("*.md")):
        try:
            ch = _parse_chapter_file(path, language)
            chapters.append(ch)
        except Exception as exc:
            print(f"Warning: failed to load theory chapter {path}: {exc}")

    chapters.sort(key=lambda c: (c.order, c.title))
    return chapters


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
    """Clear memory cache for reload."""
    load_chapters.cache_clear()
