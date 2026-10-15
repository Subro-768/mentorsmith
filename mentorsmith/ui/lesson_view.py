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

from ..compiler.toolchain import CompilerNotFoundError, CommandResult, Toolchain
from ..core.curriculum import Lesson
from . import theme
from .chat_panel import ChatPanel
from .code_editor import CodeEditor, MarkdownView, markdown_to_html

#: Filename written into the work directory; one at a time keeps it obvious
#: which file is being compiled.
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
                filename=SOURCE_FILENAME,
            )
        except CompilerNotFoundError as exc:
            compile_result = CommandResult(ok=False, error=str(exc))
            run_result = None
        except Exception as exc:  # pragma: no cover - defensive
            compile_result = CommandResult(ok=False, error=f"Unexpected failure: {exc}")
            run_result = None
        self.completed.emit(compile_result, run_result)


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
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ---- header ----
        header = QHBoxLayout()
        self.title_label = QLabel("No lesson selected")
        self.title_label.setObjectName("title")
        header.addWidget(self.title_label)
        header.addStretch(1)

        self.prev_button = QPushButton("← Previous")
        self.next_button = QPushButton("Next →")
        self.complete_button = QPushButton("Mark complete")
        self.complete_button.setObjectName("primary")
        header.addWidget(self.prev_button)
        header.addWidget(self.next_button)
        header.addWidget(self.complete_button)
        root.addLayout(header)

        # ---- main splitter ----
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: the reading material.
        self.material_tabs = QTabWidget()
        self.lesson_view = MarkdownView()
        self.objectives_view = MarkdownView()
        self.exercise_view = MarkdownView()
        self.mistakes_view = MarkdownView()
        self.recap_view = MarkdownView()

        self.material_tabs.addTab(self.lesson_view, "Explanation")
        self.material_tabs.addTab(self.objectives_view, "Objectives")
        self.material_tabs.addTab(self.exercise_view, "Exercise")
        self.material_tabs.addTab(self.mistakes_view, "Common mistakes")
        self.material_tabs.addTab(self.recap_view, "Recap")

        checks_page = QWidget()
        checks_layout = QVBoxLayout(checks_page)
        checks_layout.setContentsMargins(8, 8, 8, 8)
        checks_intro = QLabel(
            "Answer each question out loud or in your own words, then reveal "
            "the answer. Being wrong here is useful — it tells you what to "
            "ask the tutor about."
        )
        checks_intro.setObjectName("muted")
        checks_intro.setWordWrap(True)
        checks_layout.addWidget(checks_intro)

        checks_layout_buttons = QHBoxLayout()
        self.next_check_button = QPushButton("Reveal answer")
        checks_layout_buttons.addWidget(self.next_check_button)
        checks_layout.addLayout(checks_layout_buttons)
        checks_layout.addStretch(1)
        self.material_tabs.addTab(checks_page, "Knowledge checks")
        self._build_checks_content(checks_page)

        self.splitter.addWidget(self.material_tabs)

        # Right: code, and below it the evidence plus the tutor.
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        editor_box = QWidget()
        editor_layout = QVBoxLayout(editor_box)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(6)

        controls = QHBoxLayout()
        self.run_button = QPushButton("Compile & Run")
        self.run_button.setObjectName("primary")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        self.reset_button = QPushButton("Reset code")
        self.ask_tutor_button = QPushButton("Ask the tutor")
        controls.addWidget(self.run_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.reset_button)
        controls.addStretch(1)
        controls.addWidget(QLabel("stdin:"))
        self.stdin_edit = QLineEdit()
        self.stdin_edit.setPlaceholderText("optional text your program reads")
        self.stdin_edit.setMaximumWidth(260)
        controls.addWidget(self.stdin_edit)
        controls.addWidget(self.ask_tutor_button)
        editor_layout.addLayout(controls)

        self.editor = CodeEditor()
        editor_layout.addWidget(self.editor, 1)
        right_layout.addWidget(editor_box, 3)

        # Evidence + tutor tabs.
        self.output_tabs = QTabWidget()

        self.output_view = QTextBrowser()
        self.output_view.setPlaceholderText("Compiler and runtime output appear here.")
        self.output_tabs.addTab(self.output_view, "Output")

        self.chat_panel = ChatPanel()
        self.output_tabs.addTab(self.chat_panel, "AI tutor")
        right_layout.addWidget(self.output_tabs, 2)

        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(0, 3)
        self.splitter.setStretchFactor(1, 4)
        # Give the reading pane enough room for prose to wrap without a
        # horizontal scrollbar; the code pane takes the remainder.
        self.splitter.setSizes([560, 800])
        root.addWidget(self.splitter, 1)

        # ---- status line ----
        self.status_label = QLabel()
        self.status_label.setObjectName("muted")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)
        self.refresh_sandbox_status()

        # ---- wiring ----
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
    def set_lesson(self, lesson: Lesson, *, has_previous: bool, has_next: bool) -> None:
        """Display ``lesson`` and reset the working area."""
        self.lesson = lesson
        self.title_label.setText(lesson.display_title)
        self.prev_button.setEnabled(has_previous)
        self.next_button.setEnabled(has_next)

        self.lesson_view.setHtml(
            f"<h2>{lesson.title}</h2>" + markdown_to_html(lesson.section("explanation"))
        )
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
        active, text = self.toolchain.sandbox_status()
        info = self.toolchain.detect()
        compiler = info.name or "none found"
        self.status_label.setObjectName("success" if active else "warning")
        self.status_label.setText(f"Compiler: {compiler} ({info.version or 'version unknown'})"
                                  f"  •  {text}")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)

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
    "SOURCE_FILENAME",
]