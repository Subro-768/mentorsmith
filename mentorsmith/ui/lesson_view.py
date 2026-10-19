"""The lesson screen: reading material, writing code, compiling, running, tutoring.

This is where the learner spends most of their time, so it shows the evidence
directly — the exact compiler command, its output, the exit code and the
runtime output — rather than summarising any of it.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..compiler.toolchain import CommandResult, Toolchain, ToolMissingError
from ..core import comparisons, theory
from ..core.curriculum import Lesson
from . import theme
from .chat_panel import ChatPanel
from .code_editor import CodeEditor, MarkdownView, markdown_to_html

#: Default source filename. The actual filename now comes from the execution
#: adapter's extension, so Python writes ``main.py`` and JavaScript ``main.mjs``.
SOURCE_FILENAME = "main.cpp"


class CompileWorker(QThread):
    """Runs compile+run off the GUI thread so the window stays responsive."""

    completed = pyqtSignal(object, object)  # CommandResult, CommandResult | None

    def __init__(self, toolchain: Toolchain, source: str, stdin_data: str) -> None:
        super().__init__()
        self.toolchain = toolchain
        self.source = source
        self.stdin_data = stdin_data

    def run(self) -> None:  # noqa: D102 - QThread API
        try:
            compile_result, run_result = self.toolchain.run(
                self.source,
                stdin_data=self.stdin_data,
                filename=self._filename(),
            )
        except ToolMissingError as exc:
            compile_result = CommandResult(ok=False, error=str(exc))
            run_result = None
        except Exception as exc:  # pragma: no cover - defensive
            compile_result = CommandResult(ok=False, error=f"Unexpected failure: {exc}")
            run_result = None
        self.completed.emit(compile_result, run_result)

    def _filename(self) -> str:
        """Source filename using the adapter's extension for this language."""
        extension = getattr(self.toolchain, "extension", ".cpp")
        return f"main{extension}"


class LessonView(QWidget):
    """Everything for one lesson."""

    #: (lesson_id, compiled_ok, ran_ok, result_summary)
    attempt_recorded = pyqtSignal(str, bool, bool, str)
    lesson_completed = pyqtSignal(str)
    tutor_requested = pyqtSignal(str, str, object)  # message, level, context
    request_hint = pyqtSignal(str)
    navigate_requested = pyqtSignal(int)  # -1 previous, +1 next

    def __init__(self, toolchain: Toolchain, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.toolchain = toolchain
        self.lesson: Lesson | None = None
        self._worker: CompileWorker | None = None
        #: The unmet-prerequisite banner, created the first time it is needed.
        self.prereq_banner: QLabel | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header bar ───────────────────────────────────────────────────
        header_bar = QWidget()
        header_bar.setFixedHeight(52)
        header_bar.setStyleSheet(
            f"background-color: {theme.SURFACE}; "
            f"border-bottom: 1px solid {theme.BORDER};"
        )
        header = QHBoxLayout(header_bar)
        header.setContentsMargins(16, 0, 16, 0)
        header.setSpacing(10)

        self.prev_button = QPushButton("← Prev")
        self.prev_button.setObjectName("subtle")
        self.prev_button.setFixedHeight(34)
        self.prev_button.setFixedWidth(76)

        self.title_label = QLabel("No lesson selected")
        self.title_label.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {theme.FOREGROUND};"
        )
        self.title_label.setObjectName("title")

        # Tier badge. A learner working through a track has no other way of
        # telling whether the next topic is more or less demanding than the
        # last one, and "am I still on the beginner part?" is the question a
        # progression is supposed to answer.
        self.tier_badge = QLabel("")
        self.tier_badge.setFixedHeight(22)
        self.tier_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.tier_badge.setContentsMargins(9, 0, 9, 0)
        header.addWidget(self.tier_badge)

        self.next_button = QPushButton("Next →")
        self.next_button.setObjectName("subtle")
        self.next_button.setFixedHeight(34)
        self.next_button.setFixedWidth(76)

        self.complete_button = QPushButton("Mark complete")
        self.complete_button.setObjectName("primary")
        self.complete_button.setFixedHeight(34)

        header.addWidget(self.prev_button)
        header.addWidget(self.title_label)
        header.addStretch(1)
        header.addWidget(self.next_button)
        header.addWidget(self.complete_button)
        root.addWidget(header_bar)

        # ── Main splitter ─────────────────────────────────────────────────
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet(f"background: {theme.BASE};")

        # Left: reading material tabs
        self.material_tabs = QTabWidget()
        self.material_tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: none; background: {theme.BASE}; }}"
            f"QTabBar {{ background: {theme.SURFACE}; }}"
            f"QTabBar::tab {{ padding: 9px 16px; font-size: 12px; }}"
        )
        self.lesson_view       = MarkdownView()
        self.theory_view       = MarkdownView()
        self.objectives_view   = MarkdownView()
        self.exercise_view     = MarkdownView()
        self.mistakes_view     = MarkdownView()
        self.recap_view        = MarkdownView()

        self.material_tabs.addTab(self.lesson_view,     "📝 Explanation")
        self.material_tabs.addTab(self.theory_view,     "📚 Theory Book")
        self.material_tabs.addTab(self.objectives_view, "🎯 Objectives")
        self.material_tabs.addTab(self.exercise_view,   "✏  Exercise")
        self.material_tabs.addTab(self.mistakes_view,   "⚠  Mistakes")
        self.material_tabs.addTab(self.recap_view,      "🔁 Recap")

        checks_page = QWidget()
        checks_page.setStyleSheet(f"background: {theme.BASE};")
        checks_layout = QVBoxLayout(checks_page)
        checks_layout.setContentsMargins(16, 12, 16, 12)
        checks_intro = QLabel(
            "Answer each question out loud or in your own words, then reveal "
            "the answer. Being wrong here is useful — it tells you what to "
            "ask the tutor about."
        )
        checks_intro.setObjectName("muted")
        checks_intro.setWordWrap(True)
        checks_layout.addWidget(checks_intro)

        checks_layout_buttons = QHBoxLayout()
        self.next_check_button = QPushButton("Reveal next answer")
        self.next_check_button.setObjectName("subtle")
        self.next_check_button.setFixedHeight(32)
        checks_layout_buttons.addWidget(self.next_check_button)
        checks_layout_buttons.addStretch(1)
        checks_layout.addLayout(checks_layout_buttons)
        checks_layout.addStretch(1)
        self.material_tabs.addTab(checks_page, "🧠 Checks")
        self._build_checks_content(checks_page)

        self.comparisons_view = MarkdownView()
        self.comparisons_view.setPlaceholderText(
            "Cross-language comparisons appear here once another language is added."
        )
        self.material_tabs.addTab(self.comparisons_view, "⟷ Compare")

        self.splitter.addWidget(self.material_tabs)

        # Right: code editor + output
        right = QWidget()
        right.setStyleSheet(f"background: {theme.BASE};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Editor toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(46)
        toolbar.setStyleSheet(
            f"background-color: {theme.SURFACE_ALT}; "
            f"border-bottom: 1px solid {theme.BORDER};"
        )
        controls = QHBoxLayout(toolbar)
        controls.setContentsMargins(12, 0, 12, 0)
        controls.setSpacing(8)

        self.run_button = QPushButton("▶  Compile & Run")
        self.run_button.setObjectName("primary")
        self.run_button.setFixedHeight(34)

        self.stop_button = QPushButton("⏹ Stop")
        self.stop_button.setFixedHeight(34)
        self.stop_button.setEnabled(False)

        self.reset_button = QPushButton("↺ Reset")
        self.reset_button.setObjectName("subtle")
        self.reset_button.setFixedHeight(34)

        self.ask_tutor_button = QPushButton("🤖 Ask Tutor")
        self.ask_tutor_button.setFixedHeight(34)

        controls.addWidget(self.run_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.reset_button)
        controls.addStretch(1)

        stdin_lbl = QLabel("stdin:")
        stdin_lbl.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        controls.addWidget(stdin_lbl)

        self.stdin_edit = QLineEdit()
        self.stdin_edit.setPlaceholderText("optional stdin")
        self.stdin_edit.setMaximumWidth(200)
        self.stdin_edit.setFixedHeight(30)
        controls.addWidget(self.stdin_edit)

        controls.addWidget(self.ask_tutor_button)
        right_layout.addWidget(toolbar)

        self.editor = CodeEditor()
        right_layout.addWidget(self.editor, 3)

        # Output + chat tabs
        self.output_tabs = QTabWidget()
        self.output_tabs.setStyleSheet(
            f"QTabWidget::pane {{ border-top: 1px solid {theme.BORDER}; "
            f"background: {theme.BASE}; border-radius: 0; }}"
            f"QTabBar {{ background: {theme.SURFACE_ALT}; }}"
            f"QTabBar::tab {{ padding: 8px 16px; font-size: 12px; }}"
        )

        self.output_view = QTextBrowser()
        self.output_view.setPlaceholderText("Compiler and runtime output appear here.")
        self.output_view.setStyleSheet(
            f"QTextBrowser {{ background: {theme.BASE}; border: none; padding: 12px; }}"
        )
        self.output_tabs.addTab(self.output_view, "📟 Output")

        self.chat_panel = ChatPanel()
        self.output_tabs.addTab(self.chat_panel, "🤖 AI Tutor")
        right_layout.addWidget(self.output_tabs, 2)

        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 4)
        self.splitter.setSizes([560, 800])
        root.addWidget(self.splitter, 1)

        # ── Status bar ────────────────────────────────────────────────────
        status_bar = QWidget()
        status_bar.setFixedHeight(28)
        status_bar.setStyleSheet(
            f"background-color: {theme.SURFACE_ALT}; "
            f"border-top: 1px solid {theme.BORDER};"
        )
        status_lay = QHBoxLayout(status_bar)
        status_lay.setContentsMargins(14, 0, 14, 0)
        self.status_label = QLabel()
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(False)
        self.status_label.setStyleSheet("font-size: 11px;")
        status_lay.addWidget(self.status_label)
        status_lay.addStretch(1)
        root.addWidget(status_bar)

        self.refresh_sandbox_status()

        # ── Wiring ────────────────────────────────────────────────────────
        self.run_button.clicked.connect(self.on_run_clicked)
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.reset_button.clicked.connect(self.on_reset_clicked)
        self.complete_button.clicked.connect(self.on_complete_clicked)
        self.prev_button.clicked.connect(lambda: self.navigate_requested.emit(-1))
        self.next_button.clicked.connect(lambda: self.navigate_requested.emit(1))
        self.next_check_button.clicked.connect(self._reveal_next_check)
        self.ask_tutor_button.clicked.connect(self._on_ask_tutor)
        self.chat_panel.message_requested.connect(self._on_tutor_message)
        self.chat_panel.hint_requested.connect(self._on_tutor_message)

    def _build_checks_content(self, page: QWidget) -> None:
        """Insert the container that knowledge-check widgets get added to.

        Placed after the intro label and buttons but before the trailing
        stretch, so added checks grow downwards.
        """
        layout = page.layout()
        self.checks_layout = QVBoxLayout()
        self.checks_layout.setContentsMargins(0, 6, 0, 0)
        self.check_widgets: list[tuple[QLabel, QPushButton, QTextBrowser]] = []
        layout.insertLayout(layout.count() - 1, self.checks_layout)

    # ------------------------------------------------------------------
    # Loading a lesson
    # ------------------------------------------------------------------
    def _populate_comparisons(self) -> None:
        """Show comparisons between this language and the others.

        A comparison is only useful next to the lesson it relates to, and it is
        deliberately about *differences*: the point is to stop a learner
        carrying one language's semantics into another.
        """
        language = getattr(self.toolchain, "language_id", "cpp")
        items = comparisons.for_language(language)
        if not items:
            self.comparisons_view.setHtml(
                "<p>No comparisons involving this language yet.</p>"
            )
            return

        blocks = [
            "<h2>Same idea, different language</h2>",
            "<p>These pairs look equivalent and are not. Read the differences "
            "before moving between tracks.</p>",
        ]
        for item in items:
            other = item.languages[1] if item.languages[0] == language else item.languages[0]
            other_label = {
                "cpp": "C++", "c": "C", "python": "Python", "javascript": "JavaScript",
            }.get(other, other)
            first_snippet, second_snippet = (
                item.snippets if item.languages[0] == language else item.snippets[::-1]
            )
            mine, theirs = (
                (first_snippet, second_snippet)
                if item.languages[0] == language
                else (second_snippet, first_snippet)
            )
            mine_label = {
                "cpp": "C++", "c": "C", "python": "Python", "javascript": "JavaScript",
            }.get(language, language)

            blocks.append(f"<h3>{_escape(item.concept)} — {_escape(mine_label)} vs {_escape(other_label)}</h3>")
            blocks.append(f"<p><b>Shared:</b> {_escape(item.same)}</p>")
            blocks.append("<p><b>Where they differ:</b></p><ul>")
            for difference in item.different:
                blocks.append(f"<li>{_escape(difference)}</li>")
            blocks.append("</ul>")
            blocks.append(
                f"<h4>{_escape(mine_label)}</h4><pre>{_escape(mine)}</pre>"
            )
            blocks.append(
                f"<h4>{_escape(other_label)}</h4><pre>{_escape(theirs)}</pre>"
            )
            blocks.append(
                f"<p><b>Think about it:</b> {_escape(item.question)}</p>"
            )
        self.comparisons_view.setHtml("".join(blocks))

    #: Colour per tier. Deliberately the accent for Advanced so the badge
    #: itself becomes a signal as the work gets harder.
    _TIER_COLOURS = {
        "foundation": "INFO",
        "core": "CYAN",
        "advanced": "ACCENT",
    }

    def _set_tier_badge(self, lesson: Lesson) -> None:
        token = self._TIER_COLOURS.get(lesson.tier, "MUTED")
        colour = getattr(theme, token, theme.MUTED)
        self.tier_badge.setText(lesson.tier_label)
        self.tier_badge.setStyleSheet(
            f"background-color: {theme.SURFACE_HOV}; color: {colour}; "
            f"border: 1px solid {colour}; border-radius: 11px; "
            f"font-size: 11px; font-weight: 700;"
        )
        self.tier_badge.setToolTip(
            f"{lesson.tier_label}: {lesson.tier_blurb}"
            if lesson.tier_blurb
            else lesson.tier_label
        )

    def _set_prerequisite_banner(self, gaps: list) -> None:
        """Say which assumed concepts have not been started."""
        if not gaps:
            if self.prereq_banner is not None:
                self.prereq_banner.setVisible(False)
            return

        # A plain string is a title; an object carries one in .title. Using
        # getattr alone would find str.title - the method - and print it.
        titles = ", ".join(
            g if isinstance(g, str) else str(getattr(g, "title", g))
            for g in gaps
        )
        plural = "s" if len(gaps) != 1 else ""
        if self.prereq_banner is None:
            self.prereq_banner = QLabel()
            self.prereq_banner.setWordWrap(True)
            self.prereq_banner.setStyleSheet(
                f"background-color: {theme.WARNING_BG}; color: {theme.WARNING}; "
                f"border: 1px solid {theme.BORDER}; border-radius: 6px; "
                f"font-size: 11px; padding: 7px 10px;"
            )
            # Above the lesson body, where it cannot be scrolled past.
            self.layout().insertWidget(1, self.prereq_banner)
        self.prereq_banner.setText(
            f"⚠  This lesson assumes {titles}, which you have not started yet. "
            f"Going ahead is fine — but if something here does not make sense, "
            f"that is probably why."
        )
        self.prereq_banner.setVisible(True)

    def set_lesson(
        self,
        lesson: Lesson,
        *,
        has_previous: bool,
        has_next: bool,
        prerequisites: list | None = None,
    ) -> None:
        """Display ``lesson`` and reset the working area.

        ``prerequisites`` lists the concepts this lesson assumes and that
        the learner has not started. They are shown as a heads-up, not a
        gate: the lesson is still open, because sometimes the fastest way
        to learn the prerequisite is to meet it here.
        """
        self.lesson = lesson
        self.title_label.setText(lesson.display_title)
        self._set_tier_badge(lesson)
        self._set_prerequisite_banner(prerequisites or [])
        self.prev_button.setEnabled(has_previous)
        self.next_button.setEnabled(has_next)

        self.lesson_view.setHtml(
            f"<h2>{lesson.title}</h2>" + markdown_to_html(lesson.section("explanation"))
        )
        th_ch = theory.get_chapter(lesson.language, lesson.id)
        if th_ch:
            self.theory_view.setHtml(markdown_to_html(th_ch.content))
        else:
            self.theory_view.setHtml(f"<p style='color:{theme.MUTED}'>No extended theory chapter for this lesson.</p>")
        self.objectives_view.setHtml(
            "<h2>Objectives</h2>" + markdown_to_html(lesson.section("objectives"))
        )
        self.exercise_view.setHtml(
            "<h2>Exercise</h2>"
            + markdown_to_html(lesson.section("exercise"))
            + (
                f"<hr><p style='color:{theme.MUTED}'>Starter code has been "
                "loaded into the editor. Write your answer there and press "
                "<b>Compile &amp; Run</b>.</p>"
                if lesson.starter_code
                else ""
            )
        )
        self.mistakes_view.setHtml(
            "<h2>Common mistakes</h2>" + markdown_to_html(lesson.section("common_mistakes"))
        )
        self.recap_view.setHtml(
            "<h2>Recap</h2>" + markdown_to_html(lesson.section("recap"))
        )

        self.editor.set_code(lesson.starter_code or lesson.example_code)
        self.output_view.clear()
        self.chat_panel.clear_transcript()
        self.chat_panel.set_level("guided")
        self._populate_checks(lesson)
        self._populate_comparisons()

    def _populate_checks(self, lesson: Lesson) -> None:
        """Rebuild the knowledge-check widgets for a lesson."""
        while self.checks_layout.count():
            item = self.checks_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.check_widgets.clear()

        if not lesson.checks:
            label = QLabel("This lesson has no knowledge checks.")
            label.setObjectName("muted")
            self.checks_layout.addWidget(label)
            self.next_check_button.setEnabled(False)
            return

        for number, (question, answer) in enumerate(lesson.checks, start=1):
            heading = QLabel(f"<b>{number}.</b> {question}")
            heading.setWordWrap(True)
            reveal = QPushButton("Reveal")
            answer_box = QTextBrowser()
            answer_box.setHtml(f"<b>Answer.</b> {answer}")
            answer_box.setVisible(False)

            button_row = QHBoxLayout()
            button_row.addWidget(reveal)
            button_row.addStretch(1)

            reveal.clicked.connect(
                lambda _=False, r=reveal, a=answer_box: (a.setVisible(not a.isVisible()),
                                                         r.setText(
                                                             "Hide" if a.isVisible() else "Reveal"))
            )
            self.checks_layout.addWidget(heading)
            self.checks_layout.addLayout(button_row)
            self.checks_layout.addWidget(answer_box)
            self.check_widgets.append((heading, reveal, answer_box))

        self.next_check_button.setEnabled(True)

    def _reveal_next_check(self) -> None:
        """Reveal the first still-hidden answer, for keyboard-free review."""
        for _heading, _reveal, answer_box in self.check_widgets:
            if not answer_box.isVisible():
                answer_box.setVisible(True)
                return
        self.next_check_button.setEnabled(False)

    # ------------------------------------------------------------------
    # Compiling and running
    # ------------------------------------------------------------------
    def refresh_sandbox_status(self) -> None:
        """Describe the tool and containment actually in force.

        Works for every language adapter, not just C++. Interpreted languages
        have no compiler and no binary to sandbox, and the wording must say so
        rather than implying a sandbox that does not exist.
        """
        try:
            info = self.toolchain.detect()
            tool_name = getattr(info, "tool_name", None) or getattr(info, "name", None)
            version = info.version or "version unknown"
            available = info.available
            install = getattr(info, "install_hint", "")
        except Exception:  # pragma: no cover - defensive
            tool_name, version, available, install = None, "", False, ""

        if not available:
            self.status_label.setObjectName("error")
            self.status_label.setText(
                f"{self._language_name()} tool NOT FOUND."
                + (f" Install it with: {install}" if install else "")
                + " Lessons still work; only Compile & Run is unavailable."
            )
        elif getattr(self.toolchain, "kind", "") == "interpreted":
            self.status_label.setObjectName("warning")
            self.status_label.setText(
                f"{self._language_name()}: {tool_name} ({version}). "
                "No compilation step. Resource limits apply (CPU, memory, "
                "file size) and the program is stopped on timeout, but there "
                "is no binary to sandbox and no filesystem isolation."
            )
        else:
            active, text = self.toolchain.sandbox_status()
            self.status_label.setObjectName("success" if active else "warning")
            self.status_label.setText(
                f"Compiler: {tool_name} ({version})  •  {text}"
            )
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

    def _language_name(self) -> str:
        return getattr(self.toolchain, "display_name", None) or "Language"

    def on_run_clicked(self) -> None:
        """Compile and run the current editor contents."""
        if self._worker is not None and self._worker.isRunning():
            return
        source = self.editor.code()
        if not source.strip():
            self.output_view.setHtml(
                f"<span style='color:{theme.ERROR}'>There is nothing to compile — "
                "the editor is empty.</span>"
            )
            return

        self.run_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setObjectName("muted")
        self.status_label.setText("Compiling…")

        self._worker = CompileWorker(self.toolchain, source, self.stdin_edit.text())
        self._worker.completed.connect(self._on_compile_finished)
        self._worker.finished.connect(self._on_worker_done)
        self._worker.start()

    def on_stop_clicked(self) -> None:
        """Terminate a running program."""
        self.toolchain.stop()
        self.status_label.setObjectName("muted")
        self.status_label.setText("Stop requested…")

    def on_complete_clicked(self) -> None:
        """Tell the window to record this lesson as complete."""
        if self.lesson is not None:
            self.lesson_completed.emit(self.lesson.id)
            self.complete_button.setText("Completed ✓")

    def on_reset_clicked(self) -> None:
        """Restore the starter code, after confirming."""
        if not self.lesson:
            return
        answer = QMessageBox.question(
            self,
            "Reset code",
            "Replace what you have written with the starter code?\n\nYour current "
            "code in the editor will be lost.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.editor.set_code(self.lesson.starter_code or self.lesson.example_code)
            self.output_view.clear()

    def _on_worker_done(self) -> None:
        self.run_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.toolchain.forget_run_sessions()

    def _on_compile_finished(self, compile_result, run_result) -> None:
        """Render honest evidence for what actually happened."""
        if compile_result is None:
            self.status_label.setText("No result was produced.")
            return

        blocks: list[str] = []
        if not compile_result.error and compile_result.command:
            blocks.append(
                f"<p style='color:{theme.MUTED}'>Command: "
                f"<code>{' '.join(compile_result.command)}</code></p>"
            )

        if compile_result.ok:
            blocks.append(
                f"<p style='color:{theme.SUCCESS}'><b>Compiled successfully</b> "
                f"in {compile_result.duration_s:.2f}s.</p>"
            )
            if compile_result.stderr.strip():
                blocks.append(
                    "<p style='color:' + '" + theme.WARNING + "' + '>The compiler "
                    "emitted warnings:</p><pre>"
                    + _escape(compile_result.stderr)
                    + "</pre>"
                )
        else:
            reason = compile_result.error or f"exit code {compile_result.exit_code}"
            blocks.append(
                f"<p style='color:{theme.ERROR}'><b>Compilation failed.</b> "
                f"{_escape(reason)}</p>"
            )

        if compile_result.stderr.strip() and not compile_result.ok:
            blocks.append("<pre>" + _escape(compile_result.stderr) + "</pre>")

        if run_result is not None:
            header = (
                f"<p style='color:{theme.SUCCESS}'><b>Program finished</b> "
                f"(exit code {run_result.exit_code}) in {run_result.duration_s:.2f}s.</p>"
                if run_result.ok
                else (
                    f"<p style='color:{theme.ERROR}'><b>Program did not finish "
                    f"cleanly.</b> exit code {run_result.exit_code}</p>"
                )
            )
            if run_result.timed_out:
                header = (
                    f"<p style='color:{theme.WARNING}'><b>Timed out.</b> "
                    f"Stopped after the runtime limit of {self.toolchain.run_timeout}s.</p>"
                )
            blocks.append(header)
            blocks.append("<h4>stdout</h4><pre>" + _escape(run_result.stdout) + "</pre>")
            if run_result.stderr.strip():
                blocks.append("<h4>stderr</h4><pre>" + _escape(run_result.stderr) + "</pre>")
            if run_result.error:
                blocks.append(
                    f"<p style='color:{theme.MUTED}'>{_escape(run_result.error)}</p>"
                )
        elif compile_result.ok:
            blocks.append(
                f"<p style='color:{theme.MUTED}'>The program was compiled but "
                "not run.</p>"
            )

        self.output_view.setHtml("".join(blocks))

        if compile_result.ok:
            self.status_label.setObjectName("success")
            status = "Compiled successfully."
            if run_result is not None:
                status = (
                    "Ran successfully (exit code 0)."
                    if run_result.ok
                    else f"Program exited with code {run_result.exit_code}."
                )
                if run_result.timed_out:
                    status = "Program was stopped for exceeding the runtime limit."
        else:
            self.status_label.setObjectName("error")
            status = "Compilation failed. See the Output tab for the compiler's own words."
        self.status_label.setText(status)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

        if self.lesson is not None:
            summary = self._summarise(compile_result, run_result)
            self.attempt_recorded.emit(
                self.lesson.id,
                compile_result.ok,
                bool(run_result.ok) if run_result is not None else False,
                summary,
            )

    @staticmethod
    def _summarise(compile_result, run_result) -> str:
        if not compile_result.ok:
            return "compile failed"
        if run_result is None:
            return "compiled"
        if run_result.timed_out:
            return "timed out"
        return "ran, exit 0" if run_result.ok else f"exit {run_result.exit_code}"

    # ------------------------------------------------------------------
    # Tutor bridge
    # ------------------------------------------------------------------
    def tutor_context(self):
        """Snapshot what the learner currently has, for the tutor."""
        from ..services.tutor import TutorContext

        lesson = self.lesson
        compile_text = self.output_view.toPlainText() if self.output_view else ""
        return TutorContext(
            lesson_title=lesson.display_title if lesson else "",
            lesson_objectives=lesson.section("objectives") if lesson else "",
            section=self.material_tabs.tabText(self.material_tabs.currentIndex()),
            code=self.editor.code(),
            compile_output=compile_text[:4000],
            user_message="",
            attempt_count=1,
        )

    def _on_ask_tutor(self) -> None:
        """Send whatever the learner has without typing a question."""
        self.output_tabs.setCurrentWidget(self.chat_panel)
        self.chat_panel.add_system_note(
            "Tutor shown your current code and output."
        )
        self.tutor_requested.emit("", self.chat_panel.current_level(), self.tutor_context())

    def _on_tutor_message(self, message: str, level: str | None = None) -> None:
        context = self.tutor_context()
        context.user_message = message
        self.tutor_requested.emit(message, level or self.chat_panel.current_level(), context)

    def chat(self) -> ChatPanel:
        return self.chat_panel


def _escape(text: str) -> str:
    """HTML-escape program output for display."""
    import html as html_module

    return html_module.escape(text or "")


__all__ = [
    "LessonView",
    "CompileWorker",
]