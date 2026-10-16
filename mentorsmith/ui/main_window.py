"""Main window: navigation, persistence wiring and the tutor threads."""

from __future__ import annotations

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..config import load_settings, work_dir as default_work_dir
from ..core import curriculum_registry
from ..core.curriculum import Lesson, adjacent_lesson, lesson_index
from ..execution import adapter as execution_adapter
from ..core.db import Database
from ..providers.base import CompletionRequest, ProviderError
from ..providers.openai_compat import build_provider, network_allowed
from ..services.insights import build_report
from ..services.tutor import TutorContext, TutorReply, TutorService
from . import theme
from .dashboard import DashboardView, InsightsPanel, ProgressView
from .developer_view import DeveloperView
from .lesson_view import LessonView
from .practice_view import PracticeView
from .projects_view import ProjectsView
from .settings_dialog import SettingsDialog

#: Page indices, named so navigation code is readable.
PAGE_DASHBOARD = 0
PAGE_PRACTICE = 1
PAGE_LESSON = 2
PAGE_INSIGHTS = 3
PAGE_PROJECTS = 4
PAGE_PROGRESS = 5
PAGE_DEVELOPER = 6


class TutorWorker(QThread):
    """Calls the provider off the GUI thread so the window never freezes."""

    replied = pyqtSignal(object)      # TutorReply
    failed = pyqtSignal(str)

    def __init__(self, service: TutorService, context: TutorContext) -> None:
        super().__init__()
        self.service = service
        self.context = context

    def run(self) -> None:  # noqa: D102 - QThread API
        try:
            self.replied.emit(self.service.ask(self.context))
        except ProviderError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            self.failed.emit(f"Unexpected failure talking to the tutor: {exc}")


class MainWindow(QMainWindow):
    """The application window."""

    def __init__(self, database: Database | None = None) -> None:
        super().__init__()
        self.setWindowTitle("MentorSmith — C++ tutor")
        self.resize(1420, 900)

        self.settings = load_settings()
        self.database = database or Database(_db_path())
        self.database.connect()

        self.lessons: list[Lesson] = []
        self.language = "cpp"

        # Every language that could be loaded. One broken track must not stop
        # the app, so failures are collected rather than raised.
        self.tracks = curriculum_registry.load_all()
        self.track_errors: dict[str, str] = {}

        self.current_lesson_id: str | None = None
        self._tutor_worker: TutorWorker | None = None
        self._pending_rubric_exercise: str | None = None

        self._apply_track("cpp")
        self._build_toolchain()
        self._build_ui()
        self._wire()
        self.refresh_all()
        self.show_page(PAGE_DASHBOARD)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _apply_track(self, language: str) -> None:
        """Point the window at one language's curriculum."""
        track = self.tracks.get(language)
        if track is None:
            reason = self.track_errors.get(language, "not available")
            self.statusBar().showMessage(f"Language '{language}' unavailable: {reason}")
            return
        self.language = language
        self.lessons = track.lessons
        self.lesson_ids = {lesson.id for lesson in track.lessons}
        self.model = track.model
        self.bank = track.bank
        self.current_lesson_id = None

    def switch_language(self, language: str) -> None:
        """Reload everything for a different language track."""
        if language == self.language and self.current_lesson_id is not None:
            return
        track = self.tracks.get(language)
        if track is None:
            reason = self.track_errors.get(language, "its curriculum failed to load")
            QMessageBox.warning(
                self,
                "Language unavailable",
                f"The '{language}' track could not be loaded:\n\n{reason}",
            )
            return

        if self._tutor_worker is not None and self._tutor_worker.isRunning():
            self._tutor_worker.wait(2000)

        self._apply_track(language)
        self._build_toolchain()

        # Rebuild the widgets that hold per-language data.
        self.practice_view.database = self.database
        self.practice_view.bank = self.bank
        self.practice_view.toolchain = self.toolchain
        self.practice_view.session = None
        self.practice_view._current_exercise_id = None
        self.projects_view.database = self.database
        self.projects_view.model = self.model
        self.projects_view.language = language

        self.lesson_view.toolchain = self.toolchain
        self.lesson_view.refresh_sandbox_status()

        self.refresh_all()
        self.show_page(PAGE_DASHBOARD)
        self.statusBar().showMessage(
            f"Switched to {track.label}: {len(track.lessons)} lessons, "
            f"{len(track.concept_ids)} concepts, {len(track.exercise_ids)} exercises"
        )

    def _build_toolchain(self) -> None:
        """Create the execution adapter for the current language."""
        adapter = execution_adapter(
            self.language,
            default_work_dir() / self.language,
            sandbox=bool(self.settings.get("sandbox_enabled", False)),
        )
        adapter.compile_timeout = 30
        adapter.run_timeout = 5
        self.toolchain = adapter

    def _build_ui(self) -> None:
        self.setStyleSheet(theme.STYLESHEET)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(0)

        nav = QWidget()
        nav.setStyleSheet(f"background-color: {theme.SURFACE_ALT};")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(10, 6, 10, 6)
        nav_layout.setSpacing(8)

        brand = QLabel("MentorSmith")
        brand.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {theme.ACCENT};"
        )
        nav_layout.addWidget(brand)

        self.nav_buttons: dict[int, QPushButton] = {}
        for index, label in (
            (PAGE_DASHBOARD, "Dashboard"),
            (PAGE_PRACTICE, "Practice"),
            (PAGE_LESSON, "Lessons"),
            (PAGE_INSIGHTS, "Progress"),
            (PAGE_PROJECTS, "Projects"),
            (PAGE_PROGRESS, "History"),
            (PAGE_DEVELOPER, "Developer"),
        ):
            button = QPushButton(label)
            button.clicked.connect(lambda _=False, i=index: self.show_page(i))
            nav_layout.addWidget(button)
            self.nav_buttons[index] = button
        nav_layout.addStretch(1)

        nav_layout.addWidget(QLabel("Language:"))
        self.language_combo = QComboBox()
        for language in curriculum_registry.LANGUAGE_IDS:
            track = self.tracks.get(language)
            label = curriculum_registry.display_name(language)
            if track is None:
                label += " (unavailable)"
            self.language_combo.addItem(label, language)
        self.language_combo.setToolTip(
            "Switching language reloads the lessons, concepts and exercises. "
            "Progress is tracked separately per language."
        )
        nav_layout.addWidget(self.language_combo)

        self.tool_label = QLabel()
        self.tool_label.setObjectName("muted")
        nav_layout.addWidget(self.tool_label)

        self.provider_label = QLabel()
        self.provider_label.setObjectName("muted")
        nav_layout.addWidget(self.provider_label)

        self.settings_button = QPushButton("Settings")
        nav_layout.addWidget(self.settings_button)
        layout.addWidget(nav)

        self.stack = QStackedWidget()
        self.dashboard = DashboardView()
        self.practice_view = PracticeView(self.database, self.bank, self.toolchain)
        self.lesson_view = LessonView(toolchain=self.toolchain)
        self.insights = InsightsPanel()
        self.projects_view = ProjectsView(self.database, self.model)
        self.progress_view = ProgressView()

        self.stack.addWidget(self.dashboard)              # 0
        self.stack.addWidget(self.practice_view)          # 1
        self.stack.addWidget(self.lesson_view)            # 2
        self.stack.addWidget(self.insights)               # 3
        self.stack.addWidget(self.projects_view)          # 4
        self.stack.addWidget(self.progress_view)          # 5
        self.developer_view = DeveloperView(self.database)  # 6
        self.stack.addWidget(self.developer_view)         # 6
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        for key, slot in (
            ("Ctrl+R", lambda: self.show_page(PAGE_DASHBOARD)),
            ("Ctrl+K", lambda: self.show_page(PAGE_PRACTICE)),
            ("Ctrl+L", lambda: self.show_page(PAGE_LESSON)),
            ("Ctrl+P", lambda: self.show_page(PAGE_INSIGHTS)),
            ("Ctrl+J", lambda: self.show_page(PAGE_PROJECTS)),
            ("Ctrl+Shift+P", self.run_current_lesson),
            ("Ctrl+,", self.open_settings),
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(slot)
            self.addAction(action)

    def _wire(self) -> None:
        self.settings_button.clicked.connect(self.open_settings)
        self.language_combo.currentIndexChanged.connect(self._on_language_changed)
        self.dashboard.lesson_selected.connect(self.open_lesson)
        self.developer_view.status_message.connect(
            lambda text: self.statusBar().showMessage(text, 8000)
        )
        self.lesson_view.navigate_requested.connect(self._navigate)
        self.lesson_view.attempt_recorded.connect(self._record_attempt)
        self.lesson_view.lesson_completed.connect(self._mark_complete)
        self.lesson_view.tutor_requested.connect(self._on_lesson_tutor)
        self.progress_view.refresh_button.clicked.connect(self.refresh_all)
        self.progress_view.reset_button.clicked.connect(self._reset_progress)

        self.practice_view.attempt_recorded.connect(self._on_practice_attempt)
        self.practice_view.tutor_requested.connect(self._on_practice_tutor)
        self.practice_view.data_changed.connect(self.refresh_insights)

        self.insights.activity_requested.connect(self._open_practice_exercise)
        self.insights.practice_requested.connect(lambda: self.show_page(PAGE_PRACTICE))
        self.insights.projects_requested.connect(lambda: self.show_page(PAGE_PROJECTS))
        self.projects_view.data_changed.connect(self.refresh_insights)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_language_changed(self, _index: int) -> None:
        language = self.language_combo.currentData()
        if language and language != self.language:
            self.switch_language(language)

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for page, button in self.nav_buttons.items():
            button.setObjectName("primary" if page == index else "")
            button.style().unpolish(button)
            button.style().polish(button)
        if index == PAGE_LESSON and self.current_lesson_id is None:
            self.open_lesson(self.lessons[0].id)
        if index == PAGE_INSIGHTS:
            self.refresh_insights()

    def open_lesson(self, lesson_id: str) -> None:
        lesson = next((l for l in self.lessons if l.id == lesson_id), None)
        if lesson is None:
            return
        index = lesson_index(self.lessons)
        self.current_lesson_id = lesson_id
        self.lesson_view.set_lesson(
            lesson,
            has_previous=index.get(lesson_id, 0) > 0,
            has_next=index.get(lesson_id, -1) < len(self.lessons) - 1,
        )
        self.complete_button_state()
        self.show_page(PAGE_LESSON)
        self.statusBar().showMessage(f"Opened {lesson.display_title}")

    def complete_button_state(self) -> None:
        if not self.current_lesson_id:
            return
        done = self.database.is_lesson_complete(self.current_lesson_id, self.language)
        self.lesson_view.complete_button.setText(
            "Completed ✓" if done else "Mark complete"
        )

    def _navigate(self, step: int) -> None:
        if not self.current_lesson_id:
            return
        neighbour = adjacent_lesson(self.lessons, self.current_lesson_id, step)
        if neighbour is not None:
            self.open_lesson(neighbour.id)

    def run_current_lesson(self) -> None:
        self.show_page(PAGE_LESSON)
        self.lesson_view.on_run_clicked()

    def _open_practice_exercise(self, exercise_id: str) -> None:
        exercise = self.bank.get(exercise_id)
        if exercise is None:
            return
        self.practice_view.load_exercise(exercise)
        self.show_page(PAGE_PRACTICE)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    def _record_attempt(self, lesson_id: str, compiled: bool, ran: bool, summary: str) -> None:
        self.database.record_exercise_attempt(
            lesson_id,
            lesson_id,
            source=self.lesson_view.editor.code(),
            compiled_ok=compiled,
            ran_ok=ran,
            result=summary,
            language=self.language,
        )
        self.database.record_activity("exercise_attempt", lesson_id, summary, self.language)
        self.refresh_insights()

    def _on_practice_attempt(self, exercise_id: str, concept_id: str, correct: bool) -> None:
        self.database.record_activity(
            "exercise_passed" if correct else "exercise_failed",
            concept_id,
            f"{exercise_id}: {'correct' if correct else 'not correct yet'}",
            self.language,
        )
        self.refresh_insights()

    def _mark_complete(self, lesson_id: str) -> None:
        self.database.mark_lesson_complete(lesson_id, self.language)
        self.database.record_activity("lesson_complete", lesson_id, "marked complete", self.language)
        self.refresh_insights()
        self.complete_button_state()
        self.statusBar().showMessage(f"{lesson_id} marked complete")

    def _reset_progress(self) -> None:
        if not self.progress_view.confirm_reset():
            return
        for lesson in self.lessons:
            self.database.unmark_lesson_complete(lesson.id, self.language)
        self.database.clear_activity(self.language)
        self.refresh_all()
        self.statusBar().showMessage(
            f"Lesson progress cleared for {curriculum_registry.display_name(self.language)}"
        )

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------
    def refresh_progress_views(self) -> None:
        completed = set(self.database.completed_lessons(self.language))
        stats = self.database.lesson_stats([l.id for l in self.lessons])
        self.dashboard.set_lessons(self.lessons)
        self.dashboard.refresh(completed, stats)
        self.dashboard.set_activity(self.database.recent_activity(12, self.language))
        self.progress_view.set_lessons(self.lessons)
        self.progress_view.refresh(self.database, self.database.completed_lessons(self.language))

    def refresh_insights(self) -> None:
        """Rebuild the Phase 2 dashboard from stored evidence for this language."""
        report = build_report(self.database, self.model, self.bank, language=self.language)
        self.insights.set_report(report)
        self.practice_view.set_recommendations(report.recommendations)
        self.projects_view.refresh(report.assessments)

    def _refresh_tool_status(self) -> None:
        """Show what is installed for the current language."""
        try:
            info = self.toolchain.detect()
            if info.available:
                self.tool_label.setText(f"{info.tool_name}")
                self.tool_label.setToolTip(info.version)
            else:
                self.tool_label.setText("tool missing")
                self.tool_label.setToolTip(info.install_hint)
        except Exception:  # pragma: no cover - defensive
            self.tool_label.setText("")

    def refresh_all(self) -> None:
        self.refresh_progress_views()
        self.refresh_insights()
        self._refresh_provider_status()
        self._refresh_tool_status()

    # ------------------------------------------------------------------
    # AI provider
    # ------------------------------------------------------------------
    def _refresh_provider_status(self) -> None:
        self.settings = load_settings()
        self.provider = build_provider(self.settings)

        if not network_allowed():
            for chat in self._all_chat_panels():
                chat.set_provider_ready(False)
            self.provider_label.setText("AI: offline (blocked)")
            return

        if self.provider.configured:
            for chat in self._all_chat_panels():
                chat.set_provider_ready(True)
                chat.set_provider_note(self.provider.describe())
            self.provider_label.setText("AI: configured")
        else:
            for chat in self._all_chat_panels():
                chat.set_provider_ready(False)
            self.provider_label.setText("AI: not configured")

    def _all_chat_panels(self):
        return (self.lesson_view.chat(), self.practice_view.chat())

    def _send_to_tutor(
        self,
        chat,
        context: TutorContext,
        level: str,
        *,
        rubric_exercise: str | None = None,
    ) -> None:
        """Dispatch one tutor turn, or explain why it cannot be sent."""
        if not network_allowed():
            chat.add_tutor_error(
                "AI calls are blocked because MENTORSMITH_OFFLINE is set."
            )
            return

        if not self.provider.configured:
            try:
                self.provider.complete(CompletionRequest(system="", user=""))
            except ProviderError as exc:
                chat.add_tutor_error(str(exc))
            else:
                chat.add_tutor_error(
                    "The provider is not fully configured. Open Settings."
                )
            return

        if self._tutor_worker is not None and self._tutor_worker.isRunning():
            chat.add_system_note("Still waiting on the previous reply…")
            return

        chat.set_sending(True)
        self._pending_rubric_exercise = rubric_exercise
        service = TutorService(provider=self.provider, level=level)
        self._tutor_worker = TutorWorker(service, context)
        self._tutor_worker.replied.connect(
            lambda reply: self._on_tutor_reply(reply, chat, rubric_exercise)
        )
        self._tutor_worker.failed.connect(chat.add_tutor_error)
        self._tutor_worker.finished.connect(lambda: chat.set_sending(False))
        self._tutor_worker.start()

    # ------------------------------------------------------------------
    # Tutor entry points
    # ------------------------------------------------------------------
    def _on_lesson_tutor(self, message: str, level: str, context: TutorContext) -> None:
        self._send_to_tutor(self.lesson_view.chat(), context, level)

    def _on_practice_tutor(self, message: str, level: str, marker: str) -> None:
        """Handle the three kinds of tutor request the practice screen makes."""
        if marker == "__back_to_lesson__":
            self.show_page(PAGE_LESSON)
            return

        chat = self.practice_view.chat()
        session = self.practice_view.session
        if session is None:
            return

        if marker.startswith("__rubric__"):
            exercise_id = marker.split("__rubric__", 1)[1]
            context = TutorContext(
                lesson_title=session.exercise.concept_id,
                section=f"exercise type {session.exercise.type}",
                user_message=message,
            )
            self._send_to_tutor(
                chat, context, "guided", rubric_exercise=exercise_id
            )
            return

        # __practice__ - ordinary help with the learner's code and real output.
        context = TutorContext(
            lesson_title=session.exercise.concept_id,
            section=f"exercise: {session.exercise.title} ({session.exercise.type})",
            code=session.editor_code() if hasattr(session, "editor_code") else "",
            user_message=message,
        )
        view = self.practice_view
        context.code = view.editor.code()
        context.compile_output = view.result_view.toPlainText()[:4000]
        context.attempt_count = session.session.attempts
        context.misconception_shown = session.session.hints_used > 0
        self._send_to_tutor(chat, context, level)

    def _on_tutor_reply(
        self, reply: TutorReply, chat, rubric_exercise: str | None
    ) -> None:
        chat.add_tutor_message(reply.as_chat_text())

        if rubric_exercise:
            self._record_rubric_grade(reply, chat, rubric_exercise)
            return

        if reply.action and reply.action != "none":
            chat.add_system_note(
                f"Suggested next step: {reply.action.replace('_', ' ')}."
            )
        if reply.reveals_solution:
            chat.add_system_note(
                "The tutor gave a solution. Read it, then close the editor and "
                "rebuild it yourself before moving on."
            )

    def _record_rubric_grade(self, reply: TutorReply, chat, exercise_id: str) -> None:
        """Parse a verdict from the tutor and record it as an interpretive grade.

        The reply is untrusted text: :func:`parse_verdict` is the only thing
        that reads it, and it can do nothing except pick a verdict.
        """
        from ..services.practice import parse_verdict

        verdict, reason = parse_verdict(reply.raw)

        session = self.practice_view.session
        exercise = self.bank.get(exercise_id)
        if session is None or exercise is None:
            return
        # Rebuild a session bound to this exercise so the grade lands on it.
        from ..services.practice import PracticeSession

        grading = PracticeSession(
            database=self.database, toolchain=self.toolchain, exercise=exercise
        )
        grading.session.hints_used = session.session.hints_used
        outcome = grading.record_interpretive(
            self.practice_view.answer_edit.toPlainText(),
            verdict=verdict,
            feedback=reason,
            hints_used=session.session.hints_used,
        )
        colour = theme.SUCCESS if outcome.correct else theme.WARNING
        chat.add_system_note(
            f"Recorded as an <b>interpretive</b> grade: {verdict}. "
            "This is the tutor's reading of your explanation, not a proof."
        )
        chat.add_system_note(
            f'<span style="color:{colour}">'
            + ("Correct." if outcome.correct else "Not yet — try explaining again.")
            + "</span>"
        )
        self._on_practice_attempt(exercise_id, exercise.concept_id, outcome.correct)

    # ------------------------------------------------------------------
    # Settings and lifecycle
    # ------------------------------------------------------------------
    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.settings = load_settings()
            self._build_toolchain()
            self.practice_view.toolchain = self.toolchain
            self.lesson_view.toolchain = self.toolchain
            self.lesson_view.refresh_sandbox_status()
            self._refresh_provider_status()
            self.statusBar().showMessage("Settings saved")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        try:
            self.toolchain.stop()
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            self.database.close()
        except Exception:  # pragma: no cover - defensive
            pass
        super().closeEvent(event)


def _db_path() -> str:
    from ..config import db_path

    return str(db_path())