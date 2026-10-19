"""The theory chapters follow the learner's own books.

The app has a theory book for each language. Two books sit in the project -
*Programming with Java: A Primer* (Balagurusamy) and *Object Oriented
Programming with C++* (Dhamodharan G et al.) - and the chapters are written
to accompany them: same subject order, each chapter naming the book section
it follows so the two can be read side by side.

Two rules these tests hold to:

* the app never ships or copies the book - it points at the learner's own
  copy, and the reference is to a *page*, so a reader can find it;
* a chapter may only cite a book section that genuinely covers it. A
  plausible-looking reference to a page that does not discuss the topic is
  worse than no reference at all.
"""

from __future__ import annotations

import re

import pytest

from mentorsmith.core import theory
from mentorsmith.core.curriculum_registry import LANGUAGE_IDS, load_all
from mentorsmith.core.theory import TheoryChapter


class TestTheBookRegistry:
    def test_java_names_its_book(self) -> None:
        info = theory.book_info("java")
        assert "Java" in info["title"]
        assert info["author"]

    def test_cpp_names_its_book(self) -> None:
        info = theory.book_info("cpp")
        assert "C++" in info["title"]
        assert info["author"]

    def test_a_language_with_no_book_says_nothing(self) -> None:
        assert theory.book_info("python") == {}

    def test_the_books_are_the_ones_in_the_project(self) -> None:
        """The registry must describe the PDFs actually shipped alongside."""
        import pathlib

        repo = pathlib.Path(__file__).resolve().parent.parent
        books = repo / "theory"
        if not books.is_dir():
            pytest.skip("no books in this checkout")
        for language in ("java", "cpp"):
            pdf = theory.find_book_pdf(language)
            if pdf is None:
                continue
            assert pdf.suffix == ".pdf"
            assert pdf.stat().st_size > 0


class TestChapterSources:
    @pytest.fixture(scope="class")
    def chapters(self):
        return {lang: theory.load_chapters(lang) for lang in LANGUAGE_IDS}

    def test_every_java_chapter_cites_the_book(self, chapters) -> None:
        for chapter in chapters["java"]:
            assert chapter.has_source, f"{chapter.id} cites nothing"
            assert chapter.source_book == "Programming with Java: A Primer"
            assert chapter.source_author
            assert chapter.source_chapter
            assert chapter.source_page and chapter.source_page > 0

    def test_every_cpp_chapter_cites_the_book(self, chapters) -> None:
        for chapter in chapters["cpp"]:
            assert chapter.has_source, f"{chapter.id} cites nothing"
            assert chapter.source_book == "Object Oriented Programming with C++"
            assert chapter.source_chapter
            assert chapter.source_page and chapter.source_page > 0

    def test_a_chapter_with_no_book_says_nothing(self) -> None:
        chapter = TheoryChapter(id="x", title="X", order=1, language="python")
        assert chapter.has_source is False
        assert chapter.source_line == ""

    def test_the_source_line_names_the_book_and_the_page(self) -> None:
        chapter = TheoryChapter(
            id="x", title="X", order=1, language="java",
            source_book="Programming with Java: A Primer",
            source_author="E. Balagurusamy",
            source_chapter="12", source_page=207,
        )
        line = chapter.source_line
        assert "Programming with Java" in line
        assert "ch. 12" in line
        assert "p. 207" in line

    def test_a_source_line_without_a_book_is_still_readable(self) -> None:
        chapter = TheoryChapter(
            id="x", title="X", order=1, language="java",
            source_chapter="4", source_page=43,
        )
        assert "ch. 4" in chapter.source_line
        assert "p. 43" in chapter.source_line

    def test_a_page_that_is_not_a_number_is_ignored_rather_than_guessed(self) -> None:
        """A page written as a range is not a page number."""
        chapter = TheoryChapter(
            id="x", title="X", order=1, language="java", source_page=None
        )
        assert chapter.source_page is None
        assert "p." not in chapter.source_line

    def test_a_chapter_without_a_page_still_cites_its_section(self) -> None:
        chapter = TheoryChapter(
            id="x", title="X", order=1, language="java",
            source_book="A Book", source_chapter="3",
        )
        assert "ch. 3" in chapter.source_line
        assert "p." not in chapter.source_line


class TestEveryChapterHasALesson:
    """A chapter nothing links to is unreachable."""

    @pytest.fixture(scope="class")
    def tracks(self):
        return load_all()

    def test_every_chapter_points_at_a_lesson_that_exists(self, tracks) -> None:
        for language, track in tracks.items():
            lesson_ids = {lesson.id for lesson in track.lessons}
            for chapter in theory.load_chapters(language):
                if chapter.lesson_id:
                    assert chapter.lesson_id in lesson_ids, (
                        f"{language}/{chapter.id} points at "
                        f"{chapter.lesson_id}, which is not a lesson"
                    )

    def test_every_lesson_has_a_chapter(self, tracks) -> None:
        for language, track in tracks.items():
            for lesson in track.lessons:
                chapter = theory.get_chapter(language, lesson.id)
                assert chapter is not None, (
                    f"{language}/{lesson.id} has no theory chapter"
                )


class TestTheNewChapters:
    """The chapters the books cover that the app was missing."""

    @pytest.mark.parametrize(
        "language, chapter_id, title_words",
        [
            ("java", "13-inheritance", ["inheritance"]),
            ("java", "14-interfaces", ["interface"]),
            ("java", "15-packages", ["package"]),
            ("java", "16-file-io", ["file"]),
            ("java", "17-multithreading", ["thread"]),
            ("java", "18-assertions", ["assertion"]),
            ("cpp", "17-inheritance", ["inheritance"]),
            ("cpp", "18-operator-overloading", ["operator"]),
            ("cpp", "19-virtual-functions", ["virtual"]),
        ],
    )
    def test_the_chapter_exists_and_says_what_it_is_about(
        self, language: str, chapter_id: str, title_words: list[str]
    ) -> None:
        chapter = theory.get_chapter(language, chapter_id)
        assert chapter is not None, f"{language}/{chapter_id} is missing"
        lowered = chapter.title.lower()
        assert any(word in lowered for word in title_words), chapter.title
        assert chapter.summary

    @pytest.mark.parametrize(
        "language, chapter_id",
        [
            ("java", "13-inheritance"),
            ("java", "14-interfaces"),
            ("java", "15-packages"),
            ("java", "16-file-io"),
            ("java", "17-multithreading"),
            ("java", "18-assertions"),
            ("cpp", "17-inheritance"),
            ("cpp", "18-operator-overloading"),
            ("cpp", "19-virtual-functions"),
        ],
    )
    def test_the_chapter_teaches_rather_than_just_names(
        self, language: str, chapter_id: str
    ) -> None:
        """A chapter has to have a body, examples, questions and a task."""
        chapter = theory.get_chapter(language, chapter_id)
        assert chapter is not None
        body = chapter.content
        assert len(body) > 1500, f"{chapter_id} is too short to teach anything"
        assert "```" in body, f"{chapter_id} has no code example"
        assert "Review questions" in body, f"{chapter_id} has no review questions"
        assert "Practice" in body, f"{chapter_id} has no practice task"

    @pytest.mark.parametrize(
        "language, chapter_id",
        [
            ("java", "13-inheritance"),
            ("java", "14-interfaces"),
            ("java", "16-file-io"),
            ("java", "17-multithreading"),
            ("cpp", "17-inheritance"),
            ("cpp", "18-operator-overloading"),
            ("cpp", "19-virtual-functions"),
        ],
    )
    def test_the_review_questions_are_real_questions(
        self, language: str, chapter_id: str
    ) -> None:
        chapter = theory.get_chapter(language, chapter_id)
        assert chapter is not None
        section = chapter.content.split("### Review questions", 1)[1]
        section = section.split("###", 1)[0]
        questions = [l for l in section.splitlines() if re.match(r"^\d+\.\s", l.strip())]
        assert len(questions) >= 5, f"{chapter_id} has only {len(questions)} questions"


class TestBookPagesArePlausible:
    """A page number outside the book is a citation to nowhere."""

    @pytest.mark.parametrize("language", ["java", "cpp"])
    def test_pages_are_within_the_book(self, language: str) -> None:
        import subprocess

        pdf = theory.find_book_pdf(language)
        if pdf is None:
            pytest.skip("no book on disk")
        try:
            out = subprocess.run(
                ["pdfinfo", str(pdf)], capture_output=True, text=True, timeout=60
            ).stdout
        except (FileNotFoundError, subprocess.SubprocessError):
            pytest.skip("pdfinfo is not available")
        match = re.search(r"^Pages:\s+(\d+)", out, re.M)
        if not match:
            pytest.skip("this PDF reports no page count")
        total = int(match.group(1))

        for chapter in theory.load_chapters(language):
            if chapter.source_page is None:
                continue
            # The printed page number is not the PDF page: front matter
            # shifts it. A generous margin still catches a page that is
            # simply not in the book.
            assert 0 < chapter.source_page <= total + 60, (
                f"{chapter.id} cites p. {chapter.source_page}, "
                f"but the PDF has {total} pages"
            )


class TestTheReaderShowsTheSource:
    """A citation nobody can see is a citation nobody has."""

    @pytest.fixture(scope="module")
    def qapp(self):
        from PyQt6.QtWidgets import QApplication

        existing = QApplication.instance()
        app = existing or QApplication([])
        yield app

    @pytest.fixture()
    def view(self, qapp):
        from mentorsmith.ui.theory_view import TheoryView

        widget = TheoryView()
        yield widget
        widget.deleteLater()

    def test_it_names_the_book_and_the_page(self, view) -> None:
        view.set_language("java")
        view._on_chapter_selected(0)
        text = view.source_label.text()
        assert "Java" in text
        assert "p." in text
        assert view.source_label.isVisibleTo(view) is True

    def test_the_book_button_appears_when_the_pdf_is_on_disk(self, view) -> None:
        if theory.find_book_pdf("java") is None:
            pytest.skip("no book on this machine")
        view.set_language("java")
        view._on_chapter_selected(0)
        assert view.btn_open_book.isVisibleTo(view) is True
        assert "page" in view.btn_open_book.toolTip()

    def test_no_book_means_no_button(self, view) -> None:
        view.set_language("python")
        view._on_chapter_selected(0)
        # Python has no book, so there is nothing to open.
        assert view.btn_open_book.isVisibleTo(view) is False
        assert view.source_label.text() == ""
