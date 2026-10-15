"""Main window: navigation, persistence wiring and the tutor thread."""

from __future__ import annotations

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
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

from ..config import load_settings
from ..core.curriculum import Lesson, adjacent_lesson, lesson_index, load_lessons
from ..core.db import Database
from ..providers.base import ProviderError
from ..providers.openai_compat import build_provider, network_allowed
from ..services.tutor import TutorContext, TutorReply, TutorService
from . import theme
from .dashboard import DashboardView, ProgressView
from .lesson_view import LessonView
from .settings_dialog import SettingsDialog


class TutorWorker(QThread):
    """Calls the provider off the GUI thread so the window never freezes."""

    replied = pyqtSignal(object)      # TutorReply
    failed = pyqtSignal(str)          # human-readable error
    unavailable = pyqtSignal(str)     # offline / not configured

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
        self.resize(1360, 880)

        self.settings = load_settings()
        self.database = database or Database(_default_db_path())
        self.database.connect()

        self.lessons: list[Lesson] = load_lessons()
        self.current_lesson_id: str | None = None
        self._tutor_worker: TutorWorker | None = None

        # The toolchain must exist before the UI is built, because the lesson
        # view reports the compiler and sandbox status while constructing.
        self._build_toolchain()

        self._build_ui()
        self._wire()
        self.refresh_all()
        self.show_page(0)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self.setStyleSheet(theme.STYLESHEET)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 6, 0, 0)
        layout.setSpacing(0)

        # Navigation bar
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

        self.dashboard_button = QPushButton("Dashboard")
        self.lesson_button = QPushButton("Lessons")
        self.progress_button = QPushButton("Progress")
        nav_layout.addWidget(self.dashboard_button)
        nav_layout.addWidget(self.lesson_button)
        nav_layout.addWidget(self.progress_button)
        nav_layout.addStretch(1)

        self.provider_label = QLabel()
        self.provider_label.setObjectName("muted")
        nav_layout.addWidget(self.provider_label)

        self.settings_button = QPushButton("Settings")
        nav_layout.addWidget(self.settings_button)

        layout.addWidget(nav)

        self.stack = QStackedWidget()
        self.dashboard = DashboardView()
        self.lesson_view = LessonView(toolchain=self.toolchain)
        self.progress_view = ProgressView()
        self.stack.addWidget(self.dashboard)
        self.stack.addWidget(self.lesson_view)
        self.stack.addWidget(self.progress_view)
        layout.addWidget(self.stack, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready")

        # Keyboard shortcuts
        for key, slot in (
            ("Ctrl+R", self.dashboard_button.click),
            ("Ctrl+L", self.lesson_button.click),
            ("Ctrl+P", self.progress_button.click),
            ("Ctrl+Shift+P", self.run_current_lesson),
            ("Ctrl+,", self.open_settings),
        ):
            action = QAction(self)
            action.setShortcut(QKeySequence(key))
            action.triggered.connect(slot)
            self.addAction(action)

    def _build_toolchain(self) -> None:
        """Create the toolchain, honouring the saved sandbox preference."""
        from ..compiler.toolchain import Toolchain

        self.toolchain = Toolchain(sandbox=bool(self.settings.get("sandbox_enabled", False)))

    def _wire(self) -> None:
        self.dashboard_button.clicked.connect(lambda: self.show_page(0))
        self.lesson_button.clicked.connect(lambda: self.show_page(1))
        self.progress_button.clicked.connect(lambda: self.show_page(2))
        self.settings_button.clicked.connect(self.open_settings)

        self.dashboard.lesson_selected.connect(self.open_lesson)
        self.lesson_view.navigate_requested.connect(self._navigate)
        self.lesson_view.attempt_recorded.connect(self._record_attempt)
        self.lesson_view.lesson_completed.connect(self._mark_complete)
        self.lesson_view.tutor_requested.connect(self._ask_tutor)
        self.progress_view.refresh_button.clicked.connect(self.refresh_all)
        self.progress_view.reset_button.clicked.connect(self._reset_progress)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        active = self.stack.widget(index)
        for button, page in (
            (self.dashboard_button, 0),
            (self.lesson_button, 1),
            (self.progress_button, 2),
        ):
            button.setObjectName("primary" if page == index else "")
            button.style().unpolish(button)
            button.style().polish(button)

        if index == 1 and self.current_lesson_id is None:
            first = self.lessons[0]
            self.open_lesson(first.id)

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
        self.show_page(1)
        self.statusBar().showMessage(f"Opened {lesson.display_title}")

    def complete_button_state(self) -> None:
        if not self.current_lesson_id:
            return
        done = self.database.is_lesson_complete(self.current_lesson_id)
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
        self.show_page(1)
        self.lesson_view.on_run_clicked()

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
        )
        self.database.record_activity("exercise_attempt", lesson_id, summary)
        self.refresh_progress_views()

    def _mark_complete(self, lesson_id: str) -> None:
        self.database.mark_lesson_complete(lesson_id)
        self.database.record_activity("lesson_complete", lesson_id, "marked complete")
        self.refresh_progress_views()
        self.complete_button_state()
        self.statusBar().showMessage(f"{lesson_id} marked complete")

    def _reset_progress(self) -> None:
        if not self.progress_view.confirm_reset():
            return
        for lesson in self.lessons:
            self.database.unmark_lesson_complete(lesson.id)
        self.database.clear_activity()
        self.refresh_all()
        self.statusBar().showMessage("All progress cleared")

    def refresh_progress_views(self) -> None:
        completed = set(self.database.completed_lessons())
        stats = self.database.lesson_stats([l.id for l in self.lessons])
        self.dashboard.refresh(completed, stats)
        self.dashboard.set_activity(self.database.recent_activity(12))
        self.progress_view.set_lessons(self.lessons)
        self.progress_view.refresh(self.database, self.database.completed_lessons())

    def refresh_all(self) -> None:
        self.dashboard.set_lessons(self.lessons)
        self.refresh_progress_views()
        self._refresh_provider_status()

    # ------------------------------------------------------------------
    # AI provider
    # ------------------------------------------------------------------
    def _refresh_provider_status(self) -> None:
        self.settings = load_settings()
        self.provider = build_provider(self.settings)
        offline = not network_allowed()

        chat = self.lesson_view.chat()
        if offline:
            chat.set_provider_ready(False)
            chat.add_system_note(
                "AI calls are blocked: MENTORSMITH_OFFLINE is set for this run."
            )
            self.provider_label.setText("AI: offline (blocked)")
            return

        if self.provider.configured:
            chat.set_provider_ready(True)
            chat.set_provider_note(self.provider.describe())
            self.provider_label.setText("AI: configured")
        else:
            chat.set_provider_ready(False)
            self.provider_label.setText("AI: not configured")

    def _ask_tutor(self, message: str, level: str, context: TutorContext) -> None:
        """Dispatch one tutor turn on a worker thread."""
        chat = self.lesson_view.chat()

        if not network_allowed():
            chat.add_tutor_error(
                "AI calls are blocked because MENTORSMITH_OFFLINE is set."
            )
            return

        if not self.provider.configured:
            # EchoProvider, and a partially configured real provider, both
            # raise a detailed message naming exactly what is missing.
            from ..providers.base import CompletionRequest

            try:
                self.provider.complete(CompletionRequest(system="", user=""))
            except ProviderError as exc:
                chat.add_tutor_error(str(exc))
            else:
                chat.add_tutor_error(
                    "The provider is not fully configured. Open Settings to check "
                    "the base URL, model and API key."
                )
            return

        service = TutorService(provider=self.provider, level=level)
        if self._tutor_worker is not None and self._tutor_worker.isRunning():
            chat.add_system_note("Still waiting on the previous reply…")
            return

        chat.set_sending(True)
        context.user_message = message
        self._tutor_worker = TutorWorker(service, context)
        self._tutor_worker.replied.connect(lambda reply: self._on_tutor_reply(reply))
        self._tutor_worker.failed.connect(chat.add_tutor_error)
        self._tutor_worker.unavailable.connect(chat.add_tutor_error)
        self._tutor_worker.finished.connect(lambda: chat.set_sending(False))
        self._tutor_worker.start()

    def _on_tutor_reply(self, reply: TutorReply) -> None:
        chat = self.lesson_view.chat()
        chat.add_tutor_message(reply.as_chat_text())
        if reply.action and reply.action != "none":
            chat.add_system_note(f"Suggested next step: {reply.action.replace('_', ' ')}.")
        if reply.reveals_solution:
            chat.add_system_note(
                "The tutor gave a solution. Read it, then close the editor and "
                "rebuild it yourself before moving on."
            )

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    def open_settings(self) -> None:
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.settings = load_settings()
            # Rebuild the toolchain so the sandbox preference takes effect.
            self._build_toolchain()
            self.lesson_view.refresh_sandbox_status()
            self._refresh_provider_status()
            self.statusBar().showMessage("Settings saved")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        """Stop any running learner program before the window closes."""
        try:
            self.toolchain.stop()
        except Exception:  # pragma: no cover - defensive
            pass
        try:
            self.database.close()
        except Exception:  # pragma: no cover - defensive
            pass
        super().closeEvent(event)


def _default_db_path() -> str:
    from ..config import db_path

    return str(db_path())