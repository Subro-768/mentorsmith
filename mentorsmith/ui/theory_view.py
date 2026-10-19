"""Theory Book view: interactive reference reader with search, TOC, and deep dive formatting."""

from __future__ import annotations

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
        action_bar.addStretch(1)

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
        if self._chapters:
            self.chapter_list.setCurrentRow(0)

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

        html_body = markdown_to_html(ch.content)
        styled_html = (
            f"<div style='font-family:system-ui,-apple-system,\"Segoe UI\",sans-serif;"
            f"font-size:13px;color:{theme.FOREGROUND};line-height:1.65;'>"
            f"{html_body}"
            f"</div>"
        )
        self.reader_view.setHtml(styled_html)

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
