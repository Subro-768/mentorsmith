"""Tests for theory book core and UI view."""

from __future__ import annotations

import pytest
from PyQt6.QtWidgets import QApplication

from mentorsmith.core.theory import (
    TheoryChapter,
    get_chapter,
    load_chapters,
    search_theory,
)
from mentorsmith.ui.theory_view import TheoryView


@pytest.fixture(scope="session")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_theory_chapters_load_all_languages() -> None:
    languages = ["cpp", "python", "java", "c", "javascript"]
    for lang in languages:
        chapters = load_chapters(lang)
        assert len(chapters) > 0, f"Expected chapters for {lang}"
        for ch in chapters:
            assert isinstance(ch, TheoryChapter)
            assert ch.id
            assert ch.title
            assert ch.language == lang
            assert len(ch.content) > 100
            assert ch.reading_time_mins >= 1


def test_theory_get_chapter() -> None:
    ch = get_chapter("cpp", "01-program-structure")
    assert ch is not None
    assert ch.id == "01-program-structure"
    assert "Program Structure" in ch.title

    missing = get_chapter("cpp", "non_existent_topic")
    assert missing is None


def test_theory_search() -> None:
    results = search_theory("cpp", "pointer")
    assert len(results) > 0
    assert any(r.chapter.id == "09-pointers" for r in results)

    results_java = search_theory("java", "exception")
    assert len(results_java) > 0
    assert any("exception" in r.chapter.id for r in results_java)


def test_theory_view_widget(qapp: QApplication) -> None:
    view = TheoryView()
    view.set_language("java")
    # Derived from the files rather than written down: the Java theory book
    # gained six chapters alongside the lessons the Balagurusamy primer
    # covers.
    from mentorsmith.core.theory import load_chapters

    expected = len(load_chapters("java"))
    assert len(view._chapters) == expected
    assert expected >= 12, "the Java theory book has shrunk"

    # Test search filter
    view.search_input.setText("exception")
    visible_count = sum(1 for i in range(view.chapter_list.count()) if not view.chapter_list.item(i).isHidden())
    assert visible_count >= 1

    # Clear search
    view.search_input.setText("")

    # Select chapter
    view.chapter_list.setCurrentRow(0)
    assert view.btn_open_lesson.isEnabled()
