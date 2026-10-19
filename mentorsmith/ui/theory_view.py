"""Theory Book view: interactive reference reader with search, TOC, and deep dive formatting."""

from __future__ import annotations

import html
from pathlib import Path

from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core import curriculum_registry, theory
from . import theme
from .code_editor import markdown_to_html


class TheoryView(QWidget):
    """Dedicated Theory Book view with multi-language selector, chapter search, and rich content."""

    open_lesson_requested = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.load_warning = None
        self.current_language: str = "cpp"
        self._chapters: list[theory.TheoryChapter] = []
        self._current_chapter: theory.TheoryChapter | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(14)

        # ── Header ────────────────────────────────────────────────────────
        header_row = QHBoxLayout()

        heading_col = QVBoxLayout()
        heading_col.setSpacing(2)
        title = QLabel("Theory Reference Book 📚")
        title.setObjectName("title")
        heading_col.addWidget(title)

        subtitle = QLabel(
            "In-depth conceptual guides, architecture breakdowns, memory models, and pitfalls."
        )
        subtitle.setObjectName("subtitle")
        heading_col.addWidget(subtitle)
        header_row.addLayout(heading_col)
        header_row.addStretch(1)

        root.addLayout(header_row)

        # ── Main Splitter: TOC Sidebar | Content Reader ───────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # ── Left: Search + Chapter List ───────────────────────────────────
        toc_panel = QWidget()
        toc_lay = QVBoxLayout(toc_panel)
        toc_lay.setContentsMargins(0, 0, 12, 0)
        toc_lay.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search chapters & topics...")
        self.search_input.setFixedHeight(36)
        self.search_input.textChanged.connect(self._on_search_changed)
        toc_lay.addWidget(self.search_input)

        # Chapter list — plain QListWidgetItem, no custom widget, no rendering fights
        self.chapter_list = QListWidget()
        self.chapter_list.setObjectName("chapter_list")
        self.chapter_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.chapter_list.setUniformItemSizes(False)
        self.chapter_list.setSpacing(1)
        self.chapter_list.setWordWrap(True)
        # Clean inline stylesheet — no conflicting sub-widget backgrounds
        self.chapter_list.setStyleSheet(
            f"""
            QListWidget {{
                background-color: {theme.SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: 10px;
                padding: 4px;
                outline: none;
            }}
            QListWidget::item {{
                background-color: transparent;
                color: {theme.FOREGROUND};
                border-radius: 6px;
                padding: 10px 12px;
                margin: 1px 2px;
            }}
            QListWidget::item:selected {{
                background-color: {theme.NAV_ACTIVE_BG};
                color: {theme.ACCENT_LIGHT};
                border: 1px solid {theme.ACCENT};
            }}
            QListWidget::item:hover:!selected {{
                background-color: {theme.SURFACE_HOV};
                color: {theme.FOREGROUND};
            }}
            """
        )
        self.chapter_list.currentRowChanged.connect(self._on_chapter_selected)
        toc_lay.addWidget(self.chapter_list, 1)

        splitter.addWidget(toc_panel)

        # ── Right: Reader Area ────────────────────────────────────────────
        reader_panel = QWidget()
        reader_lay = QVBoxLayout(reader_panel)
        reader_lay.setContentsMargins(12, 0, 0, 0)
        reader_lay.setSpacing(10)

        # Action bar above reader
        action_bar = QHBoxLayout()
        self.chapter_badge = QLabel("Chapter")
        self.chapter_badge.setObjectName("badge_info")
        action_bar.addWidget(self.chapter_badge)

        self.reading_estimate_badge = QLabel("⏱ 3 min read")
        self.reading_estimate_badge.setObjectName("badge_muted")
        action_bar.addWidget(self.reading_estimate_badge)

        # Which book section this chapter follows. The learner has their own
        # copy of the book; telling them the page means the two can be read
        # side by side instead of one replacing the other.
        self.source_label = QLabel("")
        self.source_label.setObjectName("badge_muted")
        self.source_label.setVisible(False)
        action_bar.addWidget(self.source_label)

        action_bar.addStretch(1)

        # Open the learner's own copy of the book at the matching page.
        self.btn_open_book = QPushButton("📕 Open in book")
        self.btn_open_book.setObjectName("subtle")
        self.btn_open_book.setFixedHeight(34)
        self.btn_open_book.setVisible(False)
        self.btn_open_book.clicked.connect(self._on_open_book_clicked)
        action_bar.addWidget(self.btn_open_book)

        self.btn_open_lesson = QPushButton("📖 Open Interactive Lesson")
        self.btn_open_lesson.setObjectName("primary")
        self.btn_open_lesson.setFixedHeight(34)
        self.btn_open_lesson.clicked.connect(self._on_open_lesson_clicked)
        action_bar.addWidget(self.btn_open_lesson)

        reader_lay.addLayout(action_bar)

        # Rich Markdown Browser
        self.reader_view = QTextBrowser()
        self.reader_view.setOpenExternalLinks(True)
        self.reader_view.setStyleSheet(
            f"""
            QTextBrowser {{
                background-color: {theme.SURFACE};
                border: 1px solid {theme.BORDER};
                border-radius: 12px;
                padding: 20px 24px;
                font-size: 13px;
                color: {theme.FOREGROUND};
            }}
            """
        )
        reader_lay.addWidget(self.reader_view, 1)

        splitter.addWidget(reader_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([300, 820])

        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    def set_language(self, language: str) -> None:
        """Switch language and reload chapters."""
        self.current_language = language
        self.search_input.clear()
        self.refresh()

    def refresh(self) -> None:
        self._chapters = theory.load_chapters(self.current_language)
        self._populate_list(self._chapters)
        self._refresh_load_warning()
        if self._chapters:
            self.chapter_list.setCurrentRow(0)

    def _refresh_load_warning(self) -> None:
        """Say so when a chapter file could not be read.

        A chapter that fails to parse used to disappear behind a ``print`` that
        a GUI application never shows. The chapter was then simply missing, and
        a missing chapter looks exactly like one that was never written - so a
        broken data file read as incomplete content rather than as an error.
        """
        failures = theory.load_failures(self.current_language)
        if not failures:
            if self.load_warning is not None:
                self.load_warning.setVisible(False)
            return

        if self.load_warning is None:
            self.load_warning = QLabel()
            self.load_warning.setWordWrap(True)
            self.load_warning.setStyleSheet(
                f"background-color: {theme.WARNING_BG}; color: {theme.WARNING}; "
                f"border: 1px solid {theme.BORDER}; border-radius: 6px; "
                f"padding: 8px; font-size: 11px;"
            )
            # Above the reader, where it cannot be scrolled past.
            self.layout().insertWidget(1, self.load_warning)

        names = ", ".join(Path(path).name for path, _msg in failures)
        detail = failures[0][1]
        self.load_warning.setText(
            f"⚠ {len(failures)} chapter file(s) could not be read, so they are "
            f"missing from the list: <b>{html.escape(names)}</b><br>"
            f"<span style='opacity:0.8'>{html.escape(detail)}</span>"
        )
        self.load_warning.setVisible(True)

    def _populate_list(self, chapters: list[theory.TheoryChapter]) -> None:
        """Fill the list with plain text items — no custom widgets, no rendering issues."""
        self.chapter_list.clear()
        bold_font = QFont()
        bold_font.setPointSize(10)
        bold_font.setWeight(QFont.Weight.DemiBold)

        for ch in chapters:
            # Build a two-line label: title on line 1, meta on line 2
            tag_str = f"  ·  #{ch.tags[0]}" if ch.tags else ""
            display = f"{ch.display_title}\n⏱ {ch.reading_time_mins} min read{tag_str}"
            item = QListWidgetItem(display)
            item.setFont(bold_font)
            item.setSizeHint(QSize(0, 60))
            item.setData(Qt.ItemDataRole.UserRole, ch.id)
            item.setToolTip(ch.display_title)
            self.chapter_list.addItem(item)

    # ------------------------------------------------------------------
    def _on_search_changed(self, text: str) -> None:
        q = text.strip()
        if not q:
            self._populate_list(self._chapters)
            if self._chapters:
                self.chapter_list.setCurrentRow(0)
            return

        results = theory.search_theory(self.current_language, q)
        filtered_chapters = [r.chapter for r in results]
        self._populate_list(filtered_chapters)
        if filtered_chapters:
            self.chapter_list.setCurrentRow(0)

    def _on_chapter_selected(self, row: int) -> None:
        if row < 0 or row >= self.chapter_list.count():
            return
        item = self.chapter_list.item(row)
        if not item:
            return
        cid = item.data(Qt.ItemDataRole.UserRole)
        ch = theory.get_chapter(self.current_language, cid)
        if not ch:
            return

        self._current_chapter = ch
        lang_name = curriculum_registry.display_name(self.current_language)
        self.chapter_badge.setText(f"Topic {ch.order}: {lang_name}")
        self.reading_estimate_badge.setText(f"⏱ {ch.reading_time_mins} min read")
        self._refresh_source(ch)

        html_body = markdown_to_html(ch.content)
        styled_html = (
            f"<div style='font-family:system-ui,-apple-system,\"Segoe UI\",sans-serif;"
            f"font-size:13px;color:{theme.FOREGROUND};line-height:1.65;'>"
            f"{html_body}"
            f"</div>"
        )
        self.reader_view.setHtml(styled_html)

    def _refresh_source(self, chapter) -> None:
        """Show which book this chapter follows, and offer to open it."""
        line = chapter.source_line
        self.source_label.setText(line)
        self.source_label.setVisible(bool(line))
        self.source_label.setToolTip(line)

        pdf = theory.find_book_pdf(self.current_language)
        self._book_pdf = pdf
        has_page = bool(pdf) and chapter.source_page is not None
        self.btn_open_book.setVisible(has_page)
        if has_page:
            self.btn_open_book.setToolTip(
                f"Open {pdf.name} at page {chapter.source_page} in your PDF reader"
            )
        elif pdf:
            self.btn_open_book.setToolTip(f"Open {pdf.name} in your PDF reader")

    def _on_open_book_clicked(self) -> None:
        """Open the learner's own PDF at the matching page.

        The file is the learner's, on their disk, and is opened with whatever
        reader they use - the app neither copies nor embeds it.
        """
        pdf = getattr(self, "_book_pdf", None)
        if not pdf:
            return
        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        chapter = self._current_chapter
        page = chapter.source_page if chapter else None
        if page:
            # #page= is honoured by the common readers (Evince, Okular,
            # Firefox, Zathura). Where it is not, the file still opens - at
            # the beginning rather than at the page, which is a lesser
            # outcome than not opening it at all.
            target = QUrl.fromLocalFile(str(pdf))
            target.setFragment(f"page={page}")
        else:
            target = QUrl.fromLocalFile(str(pdf))
        QDesktopServices.openUrl(target)

    def select_chapter_by_lesson_id(self, lesson_id: str) -> None:
        """Navigate to the chapter corresponding to a lesson."""
        for row in range(self.chapter_list.count()):
            item = self.chapter_list.item(row)
            cid = item.data(Qt.ItemDataRole.UserRole)
            ch = theory.get_chapter(self.current_language, cid)
            if ch and (ch.lesson_id == lesson_id or ch.id == lesson_id):
                self.chapter_list.setCurrentRow(row)
                break

    def _on_open_lesson_clicked(self) -> None:
        if self._current_chapter and self._current_chapter.lesson_id:
            self.open_lesson_requested.emit(self._current_chapter.lesson_id)
