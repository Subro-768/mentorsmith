"""The Practice screen: adaptive exercises with real deterministic grading.

Left: recommendations, each with the reason it was suggested.
Right: the exercise, an editor (or an answer box for free-form work), a
**Run & check** button, and the grading result.

The screen is explicit about *how* an answer was judged. A deterministic
result says so, because it came from running the code. An interpretive result
is labelled as the tutor's opinion, because it did not.
"""

from __future__ import annotations

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..compiler.toolchain import CommandResult, Toolchain
from ..core.db import Database
from ..core.exercises import Exercise, ExerciseBank
from ..services.practice import PracticeError, PracticeSession
from . import theme
from .chat_panel import ChatPanel
from .code_editor import CodeEditor, MarkdownView


class GradeWorker(QThread):
    """Runs the practice attempt off the GUI thread."""

    graded = pyqtSignal(object)          # PracticeOutcome
    failed = pyqtSignal(str)

    def __init__(self, session: PracticeSession, source: str, stdin: str = "") -> None:
        super().__init__()
        self.session = session
        self.source = source
        self.stdin = stdin

    def run(self) -> None:  # noqa: D102 - QThread API
        try:
            self.graded.emit(self.session.submit(self.source, stdin=self.stdin))
        except PracticeError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(f"Unexpected failure while grading: {exc}")


class PracticeView(QWidget):
    """Adaptive exercise runner."""

    #: (exercise_id, concept_id, correct)
    attempt_recorded = pyqtSignal(str, str, bool)
    #: (exercise_id, level, question) — for the tutor panel
    tutor_requested = pyqtSignal(str, str, str)
    data_changed = pyqtSignal()

    def __init__(
        self,
        database: Database,
        bank: ExerciseBank,
        toolchain: Toolchain,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.bank = bank
        self.toolchain = toolchain
        self.session: PracticeSession | None = None
        self._current_exercise_id: str | None = None
        self._worker: GradeWorker | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        header = QHBoxLayout()
        title = QLabel("Practice")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch(1)
        self.hint_usage = QLabel()
        self.hint_usage.setObjectName("muted")
        header.addWidget(self.hint_usage)
        root.addLayout(header)

        self.intro = QLabel(
            "Work suggested from your recorded attempts. Every suggestion says "
            "why it was chosen. Chat messages and time spent here are not "
            "counted as evidence — only graded attempts are."
        )
        self.intro.setObjectName("subtitle")
        self.intro.setWordWrap(True)
        root.addWidget(self.intro)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: recommendations with reasons.
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Suggested next"))
        self.recommendation_list = QListWidget()
        self.recommendation_list.setWordWrap(True)
        self.recommendation_list.itemClicked.connect(self._on_recommendation_clicked)
        left_layout.addWidget(self.recommendation_list, 1)

        self.reason_view = QTextBrowser()
        self.reason_view.setMaximumHeight(150)
        self.reason_view.setPlaceholderText("Why this was suggested appears here.")
        left_layout.addWidget(self.reason_view)
        splitter.addWidget(left)

        # Right: the exercise.
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        meta = QHBoxLayout()
        self.title_label = QLabel("No exercise selected")
        self.title_label.setObjectName("title")
        meta.addWidget(self.title_label)
        meta.addStretch(1)
        self.grade_label = QLabel()
        self.grade_label.setObjectName("muted")
        meta.addWidget(self.grade_label)
        right_layout.addLayout(meta)

        self.prompt_view = MarkdownView()
        self.prompt_view.setMaximumHeight(160)
        right_layout.addWidget(self.prompt_view)

        self.tabs = QTabWidget()

        self.editor = CodeEditor()
        self.editor.setMinimumHeight(220)
        self.tabs.addTab(self.editor, "Your code")

        self.answer_edit = QPlainTextEdit()
        self.answer_edit.setPlaceholderText(
            "Explain in your own words. Say what you think is happening and "
            "why — not what the code looks like."
        )
        self.tabs.addTab(self.answer_edit, "Your explanation")
        right_layout.addWidget(self.tabs, 1)

        buttons = QHBoxLayout()
        self.run_button = QPushButton("Run & check")
        self.run_button.setObjectName("primary")
        self.hint_button = QPushButton("Give me a hint")
        self.ask_button = QPushButton("Ask the tutor")
        self.abandon_button = QPushButton("Back to lesson")
        buttons.addWidget(self.run_button)
        buttons.addWidget(self.hint_button)
        buttons.addWidget(self.ask_button)
        buttons.addStretch(1)
        buttons.addWidget(self.abandon_button)
        right_layout.addLayout(buttons)

        self.result_tabs = QTabWidget()
        self.result_view = QTextBrowser()
        self.result_view.setPlaceholderText(
            "Grading results, diffs and the debugging coach appear here."
        )
        self.result_tabs.addTab(self.result_view, "Result")

        self.chat_panel = ChatPanel()
        self.result_tabs.addTab(self.chat_panel, "AI tutor")
        right_layout.addWidget(self.result_tabs, 1)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        self.run_button.clicked.connect(self._on_run)
        self.hint_button.clicked.connect(self._on_hint)
        self.ask_button.clicked.connect(self._on_ask)
        self.abandon_button.clicked.connect(
            lambda: self.tutor_requested.emit("", "", "__back_to_lesson__")
        )

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------
    def set_recommendations(self, recommendations) -> None:
        """Show the ranked recommendations with their reasons.

        The currently loaded exercise is preserved. Without this, submitting an
        attempt would trigger a refresh which re-selected the first row, and
        ``load_exercise`` would clear the grading result the learner is
        reading.
        """
        self.recommendation_list.blockSignals(True)
        self.recommendation_list.clear()
        for rec in recommendations:
            exercise = self.bank.get(rec.exercise_id)
            if exercise is None:
                continue
            label = f"[{rec.category}] {exercise.title}\n{rec.concept_id} · {rec.exercise_type}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, rec.exercise_id)
            item.setToolTip(rec.reason)
            self.recommendation_list.addItem(item)

        if not self.recommendation_list.count():
            self.recommendation_list.blockSignals(False)
            return

        # Never discard an exercise that is already loaded. Reloading would
        # clear the grading result the learner is reading, which happens every
        # time a submit triggers a dashboard refresh.
        if self.session is not None and self._current_exercise_id:
            row = self._row_for(self._current_exercise_id)
            if row >= 0:
                self.recommendation_list.setCurrentRow(row)
                self.reason_view.setPlainText(
                    self.recommendation_list.item(row).toolTip()
                    or "No reason recorded for this suggestion."
                )
            self.recommendation_list.blockSignals(False)
            return

        self.recommendation_list.setCurrentRow(0)
        self.recommendation_list.blockSignals(False)
        self._select(self.recommendation_list.item(0))

    def _row_for(self, exercise_id):
        """Index of the row holding ``exercise_id``, or -1 if absent."""
        if not exercise_id:
            return -1
        for index in range(self.recommendation_list.count()):
            item = self.recommendation_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == exercise_id:
                return index
        return -1

    def _on_recommendation_clicked(self, item: QListWidgetItem) -> None:
        self._select(item)

    def _select(self, item: QListWidgetItem) -> None:
        exercise_id = str(item.data(Qt.ItemDataRole.UserRole))
        exercise = self.bank.get(exercise_id)
        if exercise is None:
            return
        self.load_exercise(exercise, is_review=item.text().startswith("[review]"))
        self.reason_view.setPlainText(
            item.toolTip() or "No reason recorded for this suggestion."
        )

    # ------------------------------------------------------------------
    # Exercise loading
    # ------------------------------------------------------------------
    def load_exercise(self, exercise: Exercise, *, is_review: bool = False) -> None:
        """Set up the editor or answer box for an exercise."""
        self.session = PracticeSession(
            database=self.database,
            toolchain=self.toolchain,
            exercise=exercise,
            is_review=is_review,
            language=getattr(self.toolchain, "language_id", "cpp"),
        )
        self._current_exercise_id = exercise.id
        self.title_label.setText(exercise.title)
        self.prompt_view.setHtml(
            f"<h3>{exercise.title}</h3><p>{exercise.prompt}</p>"
            + (
                f"<p style='color:{theme.WARNING}'><b>{exercise.type}</b>"
                f"{' — unfamiliar variation' if exercise.novel else ''}</p>"
            )
        )

        if exercise.is_interpretive:
            self.tabs.setCurrentWidget(self.answer_edit)
            self.grade_label.setText(
                "Judged by the tutor against a rubric — this is an opinion, "
                "not a proof."
            )
            self.grade_label.setStyleSheet(f"color: {theme.WARNING};")
            self.run_button.setText("Submit explanation")
            self.editor.set_code("")
        else:
            self.tabs.setCurrentWidget(self.editor)
            self.grade_label.setText("Judged by compiling and running your code.")
            self.grade_label.setStyleSheet(f"color: {theme.SUCCESS};")
            self.run_button.setText("Run & check")
            self.editor.set_code(exercise.initial_code)

        self.hint_button.setEnabled(exercise.is_interpretive or not exercise.forbids_hints)
        if exercise.forbids_hints:
            self.hint_button.setToolTip(
                "This exercise must be attempted without hints — that is what "
                "makes it evidence of independent work."
            )
            self.hint_button.setText("Hints disabled")
        else:
            self.hint_button.setToolTip(
                "Each hint is recorded and reduces how independent this attempt "
                "counts as."
            )
            self.hint_button.setText("Give me a hint")

        self.result_view.clear()
        self.result_tabs.setCurrentWidget(self.result_view)
        self.chat_panel.clear_transcript()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _on_run(self) -> None:
        if self.session is None:
            return
        exercise = self.session.exercise

        if exercise.is_interpretive:
            answer = self.answer_edit.toPlainText().strip()
            if not answer:
                QMessageBox.information(
                    self,
                    "No explanation yet",
                    "Write your explanation first. The tutor grades what you "
                    "write, so there is nothing to judge yet.",
                )
                return
            self._render_interpretive_prompt(answer)
            return

        if self._worker is not None and self._worker.isRunning():
            return
        self.run_button.setEnabled(False)
        source = self.editor.code()
        self._worker = GradeWorker(self.session, source)
        self._worker.graded.connect(self._render_outcome)
        self._worker.failed.connect(self._render_error)
        self._worker.finished.connect(lambda: self.run_button.setEnabled(True))
        self._worker.start()

    def _on_hint(self) -> None:
        if self.session is None:
            return
        hint = self.session.hint()
        self.chat_panel.add_system_note(f"Hint {self.session.session.hints_used}")
        self.chat_panel.add_tutor_message(hint)
        self.chat_panel.add_system_note(
            f"Hints used so far: {self.session.session.hints_used}. This "
            "attempt will not count as independent work."
        )
        self.hint_usage.setText(f"Hints used: {self.session.session.hints_used}")

    def _on_ask(self) -> None:
        if self.session is None:
            return
        self.result_tabs.setCurrentWidget(self.chat_panel)
        question = self._debug_question()
        self.chat_panel.add_system_note(question)
        self.tutor_requested.emit(question, self.chat_panel.current_level(), "__practice__")

    def _debug_question(self) -> str:
        """The next question the debugging coach wants answered."""
        if self.session is None:
            return ""
        diagnosis = self.session.session.last_diagnosis
        if diagnosis is None:
            return (
                "I am stuck on this exercise. Here is the code and what it "
                "actually does when I run it."
            )
        return (
            f"Still stuck on this exercise. My current diagnosis: "
            f"{diagnosis.summary} My code and its real output are on screen."
        )

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _render_error(self, message: str) -> None:
        self.result_view.setHtml(
            f"<p style='color:{theme.ERROR}'>{message}</p>"
        )
        self.result_tabs.setCurrentWidget(self.result_view)

    def _render_outcome(self, outcome) -> None:
        grade = outcome.grade
        parts: list[str] = []

        if grade.correct:
            parts.append(
                f"<p style='color:{theme.SUCCESS}'><b>Correct.</b> "
                f"{grade.detail}</p>"
            )
            parts.append(
                f"<p style='color:{theme.MUTED}'>Judged by "
                f"<b>{grade.graded_by}</b> grading — "
                + (
                    "the program was compiled and its real output compared with "
                    "the expected output."
                    if grade.graded_by == "deterministic"
                    else "the tutor's opinion. Treat it as a second reading, "
                         "not a verdict."
                )
                + "</p>"
            )
        else:
            parts.append(
                f"<p style='color:{theme.ERROR}'><b>Not correct yet.</b> "
                f"{grade.detail}</p>"
            )
            if grade.error_category:
                parts.append(
                    f"<p style='color:{theme.WARNING}'>Category: "
                    f"<b>{grade.error_category}</b>"
                    + (
                        f" — {grade.error_category_explanation}"
                        if grade.error_category_explanation
                        else ""
                    )
                    + "</p>"
                )
            if grade.diff:
                parts.append(
                    "<h4>Expected vs actual</h4><pre>"
                    + _escape(grade.diff)
                    + "</pre>"
                )

        if outcome.compile_result is not None and not outcome.compile_result.ok:
            parts.append("<h4>Compiler said</h4><pre>"
                         + _escape(outcome.compile_result.stderr) + "</pre>")
        if outcome.run_result is not None and outcome.run_result.stdout:
            parts.append("<h4>Your program's actual output</h4><pre>"
                         + _escape(outcome.run_result.stdout) + "</pre>")

        if outcome.diagnosis is not None:
            diagnosis = outcome.diagnosis
            parts.append(
                f"<h4>Debugging coach</h4>"
                f"<p><b>{_escape(diagnosis.summary)}</b> "
                f"(confidence: {diagnosis.confidence})</p>"
                + (f"<p style='color:{theme.MUTED}'>{_escape(diagnosis.evidence)}</p>"
                   if diagnosis.evidence else "")
                + f"<p><b>Try this first:</b> {_escape(diagnosis.hint)}</p>"
            )
            if outcome.session is not None and outcome.session.stage == "escalate":
                parts.append(
                    "<p style='color:{theme.WARNING}'>Several attempts have "
                    "failed. Before another hint: say in one sentence what you "
                    "think is wrong and what evidence supports it. The coach "
                    "will not hand you the answer.</p>"
                )
            parts.append(
                "<p style='color:{theme.ACCENT}'>Press <b>Give me a hint</b> "
                "for one small step, or fix it and check again.</p>"
            )

        if outcome.follow_up:
            parts.append(
                f"<h4>Before you move on</h4><p>{_escape(outcome.follow_up)}</p>"
            )

        if self.session is not None:
            parts.append(
                f"<p style='color:{theme.MUTED}'>Attempts: "
                f"{self.session.session.attempts} · hints used: "
                f"{self.session.session.hints_used} · recorded as "
                f"{'independent' if self._independent(outcome) else 'assisted'} work."
                "</p>"
            )

        self.result_view.setHtml("".join(parts))
        self.result_tabs.setCurrentWidget(self.result_view)

        if self.session is not None:
            self.attempt_recorded.emit(
                self.session.exercise.id,
                self.session.exercise.concept_id,
                outcome.correct,
            )
        self.data_changed.emit()

    @staticmethod
    def _independent(outcome) -> bool:
        session = outcome.session
        return bool(outcome.correct and session and session.hints_used == 0
                    and session.escalations == 0)

    def _render_interpretive_prompt(self, answer: str) -> None:
        """Free-form answers are graded by the tutor, so ask the tutor."""
        assert self.session is not None
        prompt = self.session.rubric_prompt(answer)
        self.answer_edit.setPlainText("")
        self.chat_panel.clear_transcript()
        self.chat_panel.add_learner_message(answer)
        self.result_tabs.setCurrentWidget(self.chat_panel)
        self.result_view.setHtml(
            "<p>Your explanation has been sent to the tutor for grading "
            f"against the rubric.</p><pre>{_escape(prompt)}</pre>"
        )
        self.tutor_requested.emit(prompt, "guided", f"__rubric__{self.session.exercise.id}")
        self.tutor_requested.emit(
            "When you reply, judge my explanation against the rubric and end "
            "with a line 'VERDICT: correct' or 'VERDICT: partial' or "
            "'VERDICT: incorrect', then 'REASON: one sentence'.",
            "guided",
            f"__rubric__{self.session.exercise.id}",
        )

    def chat(self) -> ChatPanel:
        return self.chat_panel


def _escape(text: str) -> str:
    import html as html_module

    return html_module.escape(text or "")