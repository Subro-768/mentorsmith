"""Theory book loading.

Two things were wrong, both invisible:

* ``load_chapters`` is ``lru_cache``d and returned a **list**. Every caller
  shared the same object, so one ``.sort()`` or ``.append()`` silently rewrote
  the cache for the whole session. Nothing does that today, which is exactly
  why it is worth closing rather than leaving to chance.
* A chapter file that could not be parsed was skipped behind a bare ``print``,
  which a GUI application never shows. The chapter was then simply absent, and
  an absent chapter looks precisely like one that was never written - so a
  corrupted data file read as incomplete content rather than as an error.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mentorsmith.core import theory
from mentorsmith.core.theory import TheoryChapter, load_chapters, load_failures


@pytest.fixture(autouse=True)
def _clean_cache():
    """The module caches for the whole process; do not leak between tests."""
    theory.clear_cache()
    yield
    theory.clear_cache()


@pytest.fixture()
def sandbox_theory_dir(tmp_path, monkeypatch):
    """Point THEORY_DIR at a throwaway tree so real content is never touched."""
    root = tmp_path / "theory"
    (root / "demo").mkdir(parents=True)
    monkeypatch.setattr(theory, "THEORY_DIR", root)
    theory.clear_cache()
    return root


def write(root: Path, language: str, name: str, body: str) -> Path:
    path = root / language / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


# ======================================================================
# The shared-cache hazard
# ======================================================================
class TestCachedResultIsNotMutable:
    def test_it_returns_an_immutable_sequence(self, sandbox_theory_dir) -> None:
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        result = load_chapters("demo")
        assert isinstance(result, tuple), (
            "a cached list is shared between callers and any one of them can "
            "mutate the cache for everyone"
        )

    def test_it_cannot_be_appended_to(self, sandbox_theory_dir) -> None:
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        with pytest.raises(AttributeError):
            load_chapters("demo").append(TheoryChapter(id="x", title="X", order=0, language="demo"))

    def test_it_cannot_be_sorted_in_place(self, sandbox_theory_dir) -> None:
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        with pytest.raises(AttributeError):
            load_chapters("demo").sort()

    def test_repeated_calls_return_equal_content(self, sandbox_theory_dir) -> None:
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        assert load_chapters("demo") == load_chapters("demo")

    def test_it_is_still_cached(self, sandbox_theory_dir) -> None:
        """Caching is the point; only mutability was the problem."""
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        assert load_chapters("demo") is load_chapters("demo")

    def test_iteration_still_works(self, sandbox_theory_dir) -> None:
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        assert [c.id for c in load_chapters("demo")] == ["01-a"]


# ======================================================================
# A chapter that cannot be read
# ======================================================================
class TestUnreadableChaptersAreReported:
    def test_an_undecodable_file_is_reported(self, sandbox_theory_dir) -> None:
        path = write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        path.write_bytes(path.read_bytes() + b"\n\xff\xfe not utf-8\n")
        load_chapters("demo")
        failures = load_failures("demo")
        assert len(failures) == 1
        assert failures[0][0].endswith("01-a.md")
        assert "UnicodeDecodeError" in failures[0][1]

    def test_the_other_chapters_still_load(self, sandbox_theory_dir) -> None:
        """One bad file must not cost the whole book."""
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        write(sandbox_theory_dir, "demo", "02-b.md", "---\ntitle: B\n---\nbody")
        bad = write(sandbox_theory_dir, "demo", "03-c.md", "---\ntitle: C\n---\nbody")
        bad.write_bytes(b"\xff\xfe\x00bad")

        chapters = load_chapters("demo")
        assert len(chapters) == 2
        assert [c.title for c in chapters] == ["A", "B"]
        assert len(load_failures("demo")) == 1

    def test_failures_are_scoped_to_their_language(self, sandbox_theory_dir) -> None:
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        write(sandbox_theory_dir, "other", "01-x.md", "---\ntitle: X\n---\nbody")
        bad = write(sandbox_theory_dir, "demo", "02-b.md", "---\ntitle: B\n---\nbody")
        bad.write_bytes(b"\xffbroken")

        load_chapters("demo")
        load_chapters("other")

        assert len(load_failures("demo")) == 1
        assert load_failures("other") == [], "another language's failures leaked in"
        assert len(load_failures()) == 1

    def test_clear_cache_clears_the_failures(self, sandbox_theory_dir) -> None:
        bad = write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        bad.write_bytes(b"\xffbroken")
        load_chapters("demo")
        assert load_failures("demo")

        theory.clear_cache()
        assert load_failures("demo") == []

    def test_a_healthy_book_reports_nothing(self, sandbox_theory_dir) -> None:
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        load_chapters("demo")
        assert load_failures("demo") == []

    def test_malformed_front_matter_is_not_an_error(self, sandbox_theory_dir) -> None:
        """The parser degrades gracefully on odd metadata, which is the right
        behaviour; only genuinely unreadable bytes are a failure."""
        write(sandbox_theory_dir, "demo", "01-a.md", "---\nid: [unclosed\n---\nstill here")
        chapters = load_chapters("demo")
        assert len(chapters) == 1
        assert load_failures("demo") == []
        assert "still here" in chapters[0].content

    def test_a_missing_language_is_not_a_failure(self, sandbox_theory_dir) -> None:
        assert load_chapters("nonexistent") == ()
        assert load_failures("nonexistent") == []


# ======================================================================
# The warning reaches the screen
# ======================================================================
class TestTheWarningIsShown:
    @pytest.fixture()
    def view(self, sandbox_theory_dir, monkeypatch):
        pytest.importorskip("PyQt6")
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance() or QApplication([])
        from mentorsmith.ui.theory_view import TheoryView

        widget = TheoryView()
        widget.show()
        app.processEvents()
        yield widget, app
        widget.deleteLater()

    @staticmethod
    def _shown(widget) -> bool:
        """Is a warning actually on screen?

        The label is created once and hidden again rather than destroyed and
        rebuilt, so switching languages does not churn the layout. The contract
        that matters is what the user sees, not whether a QLabel exists.
        """
        return widget.load_warning is not None and not widget.load_warning.isHidden()

    def test_no_warning_when_everything_loads(self, view, sandbox_theory_dir) -> None:
        widget, app = view
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        widget.set_language("demo")
        app.processEvents()
        assert not self._shown(widget)

    def test_a_warning_appears_naming_the_file(self, view, sandbox_theory_dir) -> None:
        widget, app = view
        write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        bad = write(sandbox_theory_dir, "demo", "02-b.md", "---\ntitle: B\n---\nbody")
        bad.write_bytes(b"\xffbroken")

        widget.set_language("demo")
        app.processEvents()

        warning = widget.load_warning
        assert warning is not None, "a corrupted chapter vanished silently again"
        assert warning.isVisible()
        assert "02-b.md" in warning.text()

    def test_the_warning_disappears_once_the_file_is_repaired(
        self, view, sandbox_theory_dir
    ) -> None:
        widget, app = view
        path = write(sandbox_theory_dir, "demo", "01-a.md", "---\ntitle: A\n---\nbody")
        path.write_bytes(b"\xffbroken")
        widget.set_language("demo")
        app.processEvents()
        assert widget.load_warning is not None

        path.write_text("---\ntitle: A\n---\nrepaired", encoding="utf-8")
        theory.clear_cache()
        widget.set_language("demo")
        app.processEvents()
        assert not self._shown(widget), "the warning stayed up after the file was fixed"
        assert len(widget._chapters) == 1


# ======================================================================
# The real content still loads
# ======================================================================
class TestRealContent:
    def test_every_language_has_chapters(self) -> None:
        for language in ("cpp", "python", "java", "c", "javascript"):
            assert len(load_chapters(language)) > 0, f"no chapters for {language}"

    def test_the_shipped_content_has_no_failures(self) -> None:
        """A silent parse failure in the shipped data would be invisible."""
        for language in ("cpp", "python", "java", "c", "javascript"):
            load_chapters(language)
        assert load_failures() == [], f"shipped theory data failed to parse: {load_failures()}"

    def test_search_still_works_over_the_real_content(self) -> None:
        assert theory.search_theory("cpp", "pointer")
        assert theory.search_theory("java", "exception")

    def test_an_empty_query_returns_nothing(self) -> None:
        assert theory.search_theory("cpp", "") == []
        assert theory.search_theory("cpp", "   ") == []

    def test_get_chapter_finds_by_id_and_by_lesson_id(self) -> None:
        chapter = theory.get_chapter("cpp", "01-program-structure")
        assert chapter is not None
        assert theory.get_chapter("cpp", chapter.lesson_id) is not None
        assert theory.get_chapter("cpp", "no-such-chapter") is None