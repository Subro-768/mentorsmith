"""Main window: vertical sidebar navigation, persistence wiring and tutor threads."""

from __future__ import annotations

import threading

from PyQt6.QtCore import QThread, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QFont, QKeySequence
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
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
from .analytics_view import AnalyticsView
from .dashboard import DashboardView, InsightsPanel, ProgressView
from .developer_view import DeveloperView
from .lesson_view import LessonView
from .practice_view import PracticeView
from .playground_view import PlaygroundView
from .projects_view import ProjectsView
from .settings_dialog import SettingsDialog
from .theory_view import TheoryView

#: Page indices
PAGE_DASHBOARD  = 0
PAGE_PRACTICE   = 1
PAGE_LESSON     = 2
PAGE_INSIGHTS   = 3
PAGE_PROJECTS   = 4
PAGE_PROGRESS   = 5
PAGE_DEVELOPER  = 6
PAGE_ANALYTICS  = 7
PAGE_THEORY     = 8
PAGE_PLAYGROUND = 9

_NAV_ITEMS = [
    (PAGE_ANALYTICS,  "📊", "Analytics"),
    (PAGE_DASHBOARD,  "🏠", "Dashboard"),
    (PAGE_PLAYGROUND, "💻", "Playground"),
    (PAGE_THEORY,     "📚", "Theory Book"),
    (PAGE_PRACTICE,   "⚡", "Practice"),
    (PAGE_LESSON,     "📖", "Lessons"),
    (PAGE_INSIGHTS,   "🎯", "Mastery"),
    (PAGE_PROJECTS,   "🏗", "Projects"),
    (PAGE_PROGRESS,   "📋", "History"),
    (PAGE_DEVELOPER,  "🛠", "Developer"),
]


class TutorWorker(QThread):
    """Calls the provider off the GUI thread so the window never freezes."""

    replied   = pyqtSignal(object)   # TutorReply
    failed    = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, service: TutorService, context: TutorContext) -> None:
        super().__init__()
        self.service  = service
        self.context  = context
        #: Set by :meth:`cancel`. Checked before the reply is shown, so a
        #: reply that arrives after the learner gave up is discarded rather
        #: than appearing in the transcript as if it had been wanted.
        self._cancel = threading.Event()

    @property
    def cancelled_requested(self) -> bool:
        return self._cancel.is_set()

    def cancel(self) -> bool:
        """Ask for the request to stop. Returns True if there was one to stop.

        Two layers, because one is not enough:

        * The provider's connection is closed, which unblocks a read that is
          already in progress.
        * The flag is set, so a reply that still arrives is thrown away and
          the tutor reports a cancellation rather than a failure.

        A request that has not been sent yet is simply never sent.
        """
        if self._cancel.is_set():
            return False
        self._cancel.set()
        provider = getattr(self.service, "provider", None)
        closer = getattr(provider, "close_active", None)
        if callable(closer):
            try:
                closer()
            except Exception:  # pragma: no cover - defensive
                pass
        return True

    def run(self) -> None:  # noqa: D102 - QThread API
        if self._cancel.is_set():
            self.cancelled.emit()
            return
        try:
            reply = self.service.ask(self.context)
        except ProviderError as exc:
            if self._cancel.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(str(exc))
        except Exception as exc:  # pragma: no cover - defensive
            if self._cancel.is_set():
                self.cancelled.emit()
            else:
                self.failed.emit(f"Unexpected failure talking to the tutor: {exc}")
        else:
            if self._cancel.is_set():
                self.cancelled.emit()
            else:
                self.replied.emit(reply)


# ---------------------------------------------------------------------------
# Sidebar nav button
# ---------------------------------------------------------------------------

class SidebarButton(QPushButton):
    """Icon + label nav button with active / inactive visual states."""

    def __init__(self, icon: str, label: str, parent: QWidget | None = None) -> None:
        super().__init__(f"  {icon}  {label}", parent)
        self._active = False
        self._set_style()

    def set_active(self, active: bool) -> None:
        self._active = active
        self._set_style()

    def _set_style(self) -> None:
        name = "nav_item_active" if self._active else "nav_item"
        self.setObjectName(name)
        self.style().unpolish(self)
        self.style().polish(self)


# ---------------------------------------------------------------------------
# Status chip widget
# ---------------------------------------------------------------------------

class StatusChip(QLabel):
    """Compact rounded badge showing a brief status string."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state("muted", "—")

    def set_state(self, kind: str, text: str) -> None:
        """kind: 'success' | 'error' | 'warning' | 'muted'"""
        self.setText(text)
        self.setObjectName(f"badge_{kind}")
        self.style().unpolish(self)
        self.style().polish(self)
        self.setToolTip(text)


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """The application window with a vertical sidebar."""

    def __init__(self, database: Database | None = None) -> None:
        super().__init__()
        self.setWindowTitle("MentorSmith")
        self.resize(1440, 900)

        self.settings = load_settings()
        self.database = database or Database(_db_path())
        self.database.connect()

        self.lessons:           list[Lesson] = []
        self.language:          str          = "cpp"
        self.tracks                          = curriculum_registry.load_all()
        self.track_errors:      dict[str, str] = {}
        self.current_lesson_id: str | None   = None
        self._tutor_worker:     TutorWorker | None = None
        #: Kept so the reply handler can read the token accounting the
        #: service recorded for the call that produced it.
        self._tutor_service:    TutorService | None = None
        self._pending_rubric_exercise: str | None  = None

        self._apply_track("cpp")
        self._build_toolchain()
        self._build_ui()
        # Apply saved theme (default: dark_orange)
        saved_theme = self.settings.get("theme", "dark_orange")
        theme.apply_theme(self, saved_theme)
        self._wire()
        self.refresh_all()
        self.show_page(PAGE_DASHBOARD)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _apply_track(self, language: str) -> None:
        track = self.tracks.get(language)
        if track is None:
            reason = self.track_errors.get(language, "not available")
            self.statusBar().showMessage(f"Language '{language}' unavailable: {reason}")
            return
        self.language          = language
        self.lessons           = track.lessons
        self.lesson_ids        = {lesson.id for lesson in track.lessons}
        self.model             = track.model
        self.bank              = track.bank
        self.current_lesson_id = None

    def switch_language(self, language: str) -> None:
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

        self.practice_view.database  = self.database
        self.practice_view.bank      = self.bank
        self.practice_view.toolchain = self.toolchain
        self.practice_view.session   = None
        self.practice_view._current_exercise_id = None
        self.projects_view.database  = self.database
        self.projects_view.model     = self.model
        self.projects_view.language  = language

        self.lesson_view.toolchain = self.toolchain
        self.lesson_view.refresh_sandbox_status()
        self.theory_view.set_language(language)
        self.playground_view.set_language(language)

        self.refresh_all()
        self.show_page(PAGE_DASHBOARD)
        self.statusBar().showMessage(
            f"Switched to {track.label}: {len(track.lessons)} lessons, "
            f"{len(track.concept_ids)} concepts, {len(track.exercise_ids)} exercises"
        )

    def _build_toolchain(self) -> None:
        adapter = execution_adapter(
            self.language,
            default_work_dir() / self.language,
            sandbox=bool(self.settings.get("sandbox_enabled", False)),
        )
        adapter.compile_timeout = 30
        adapter.run_timeout     = 5
        self.toolchain          = adapter

    def _build_ui(self) -> None:
        self.setStyleSheet(theme.STYLESHEET)

        # Root layout: sidebar | content
        root_widget = QWidget()
        root_layout = QHBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(4)

        # Brand
        brand = QLabel("MentorSmith")
        brand.setObjectName("brand")
        sidebar_layout.addWidget(brand)

        tagline = QLabel("C++ Learning Studio")
        tagline.setObjectName("muted")
        tagline.setStyleSheet(f"font-size: 11px; color: {theme.PLACEHOLDER}; margin-bottom: 12px;")
        sidebar_layout.addWidget(tagline)

        # Divider
        div1 = QFrame()
        div1.setFrameShape(QFrame.Shape.HLine)
        div1.setStyleSheet(f"background-color: {theme.BORDER}; max-height: 1px; margin: 4px 0;")
        sidebar_layout.addWidget(div1)

        # Nav section label
        nav_label = QLabel("NAVIGATION")
        nav_label.setObjectName("section_header")
        nav_label.setStyleSheet(f"font-size: 10px; color: {theme.PLACEHOLDER}; margin: 8px 4px 4px 4px;")
        sidebar_layout.addWidget(nav_label)

        # Nav buttons
        self.nav_buttons: dict[int, SidebarButton] = {}
        for index, icon, label in _NAV_ITEMS:
            btn = SidebarButton(icon, label)
            btn.setFixedHeight(42)
            btn.clicked.connect(lambda _=False, i=index: self.show_page(i))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[index] = btn

        sidebar_layout.addStretch(1)

        # Bottom section — language + status
        div2 = QFrame()
        div2.setFrameShape(QFrame.Shape.HLine)
        div2.setStyleSheet(f"background-color: {theme.BORDER}; max-height: 1px; margin: 4px 0;")
        sidebar_layout.addWidget(div2)

        lang_label = QLabel("LANGUAGE")
        lang_label.setObjectName("section_header")
        lang_label.setStyleSheet(f"font-size: 10px; color: {theme.PLACEHOLDER}; margin: 8px 4px 2px 4px;")
        sidebar_layout.addWidget(lang_label)

        self.language_combo = QComboBox()
        self.language_combo.setFixedHeight(34)
        for language in curriculum_registry.LANGUAGE_IDS:
            track = self.tracks.get(language)
            label = curriculum_registry.display_name(language)
            if track is None:
                label += " (unavailable)"
            self.language_combo.addItem(label, language)
        self.language_combo.setToolTip(
            "Switching language reloads the lessons, concepts and exercises.\n"
            "Progress is tracked separately per language."
        )
        sidebar_layout.addWidget(self.language_combo)

        # Tool chip
        self.tool_chip = StatusChip()
        self.tool_chip.setFixedHeight(24)
        sidebar_layout.addWidget(self.tool_chip)

        # Provider chip
        self.provider_chip = StatusChip()
        self.provider_chip.setFixedHeight(24)
        sidebar_layout.addWidget(self.provider_chip)

        # Settings button
        self.settings_button = QPushButton("⚙  Settings")
        self.settings_button.setObjectName("subtle")
        self.settings_button.setFixedHeight(36)
        self.settings_button.setStyleSheet("text-align: left; padding-left: 10px;")
        sidebar_layout.addWidget(self.settings_button)

        root_layout.addWidget(sidebar)

        # ── Content stack ─────────────────────────────────────────────────
        content_area = QWidget()
        content_area.setObjectName("content_area")
        content_layout = QVBoxLayout(content_area)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.stack = QStackedWidget()
        self.dashboard      = DashboardView()
        self.practice_view  = PracticeView(self.database, self.bank, self.toolchain)
        self.lesson_view    = LessonView(toolchain=self.toolchain)
        self.insights       = InsightsPanel()
        self.projects_view  = ProjectsView(self.database, self.model)
        self.progress_view  = ProgressView()
        self.developer_view = DeveloperView(self.database)
        self.analytics_view = AnalyticsView(self.database)
        self.theory_view    = TheoryView()
        self.playground_view = PlaygroundView()

        self.stack.addWidget(self.dashboard)       # 0
        self.stack.addWidget(self.practice_view)   # 1
        self.stack.addWidget(self.lesson_view)     # 2
        self.stack.addWidget(self.insights)        # 3
        self.stack.addWidget(self.projects_view)   # 4
        self.stack.addWidget(self.progress_view)   # 5
        self.stack.addWidget(self.developer_view)  # 6
        self.stack.addWidget(self.analytics_view)  # 7
        self.stack.addWidget(self.theory_view)     # 8
        self.stack.addWidget(self.playground_view) # 9

        content_layout.addWidget(self.stack, 1)
        root_layout.addWidget(content_area, 1)

        self.setCentralWidget(root_widget)

        status_bar = QStatusBar()
        status_bar.setFixedHeight(26)
        self.setStatusBar(status_bar)
        self.statusBar().showMessage("Ready")

        # Keyboard shortcuts
        for key, slot in (
            ("Ctrl+R", lambda: self.show_page(PAGE_DASHBOARD)),
            ("Ctrl+T", lambda: self.show_page(PAGE_PLAYGROUND)),
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

        # Stop is connected once, here, rather than on every send - a
        # connection made per request would stack up and fire the handler
        # several times for one click.
        for chat in self._all_chat_panels():
            chat.cancel_requested.connect(self._cancel_tutor_request)
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

        self.analytics_view.language_switch_requested.connect(self._on_analytics_language_switch)
        self.theory_view.open_lesson_requested.connect(self.open_lesson)

    def _on_analytics_language_switch(self, language: str) -> None:
        idx = self.language_combo.findData(language)
        if idx >= 0:
            self.language_combo.setCurrentIndex(idx)
        else:
            self.switch_language(language)
        self.show_page(PAGE_DASHBOARD)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def _on_language_changed(self, _index: int) -> None:
        language = self.language_combo.currentData()
        if language and language != self.language:
            self.switch_language(language)

    def show_page(self, index: int) -> None:
        self.stack.setCurrentIndex(index)
        for page, btn in self.nav_buttons.items():
            btn.set_active(page == index)
        if index == PAGE_LESSON and self.current_lesson_id is None:
            self.open_lesson(self.lessons[0].id)
        if index == PAGE_INSIGHTS:
            self.refresh_insights()
        if index == PAGE_ANALYTICS:
            self.analytics_view.refresh()
        if index == PAGE_THEORY:
            self.theory_view.set_language(self.language)
        if index == PAGE_PLAYGROUND:
            self.playground_view.set_language(self.language)

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
            "✓ Completed" if done else "Mark complete"
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
        report = build_report(self.database, self.model, self.bank, language=self.language)
        self.insights.set_report(report)
        self.practice_view.set_recommendations(report.recommendations)
        self.projects_view.refresh(report.assessments)

    def _refresh_tool_status(self) -> None:
        try:
            info = self.toolchain.detect()
            if info.available:
                self.tool_chip.set_state("success", f"⚙ {info.tool_name}")
                self.tool_chip.setToolTip(info.version)
            else:
                self.tool_chip.set_state("error", "⚙ tool missing")
                self.tool_chip.setToolTip(info.install_hint)
        except Exception:  # pragma: no cover
            self.tool_chip.set_state("muted", "⚙ unknown")

    def refresh_all(self) -> None:
        self.refresh_progress_views()
        self.refresh_insights()
        self.analytics_view.refresh()
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
            self.provider_chip.set_state("warning", "AI: offline")
            return

        if self.provider.configured:
            for chat in self._all_chat_panels():
                chat.set_provider_ready(True)
                chat.set_provider_note(self.provider.describe())
                # Hand the provider over so the panel can list its models.
                # Fetches /models, which is a network call - it fails quietly
                # if it cannot be reached, leaving the picker as typed.
                chat.set_provider(self.provider)
            self.provider_chip.set_state("success", "AI: ready")
        else:
            for chat in self._all_chat_panels():
                chat.set_provider_ready(False)
            self.provider_chip.set_state("error", "AI: not set")

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
        if not network_allowed():
            chat.add_tutor_error("AI calls are blocked because MENTORSMITH_OFFLINE is set.")
            return

        if not self.provider.configured:
            try:
                self.provider.complete(CompletionRequest(system="", user=""))
            except ProviderError as exc:
                chat.add_tutor_error(str(exc))
            else:
                chat.add_tutor_error("The provider is not fully configured. Open Settings.")
            return

        if self._tutor_worker is not None and self._tutor_worker.isRunning():
            chat.add_system_note("Still waiting on the previous reply…")
            return

        chat.set_sending(True)
        self._pending_rubric_exercise = rubric_exercise
        service = TutorService(provider=self.provider, level=level)
        # Take the model from the chat panel's picker. Empty means "use
        # whatever Settings says", so leaving the picker untouched behaves
        # exactly as before this existed.
        service.model = chat.current_model()
        self._tutor_service = service
        self._tutor_worker = TutorWorker(service, context)
        self._tutor_worker.replied.connect(
            lambda reply: self._on_tutor_reply(reply, chat, rubric_exercise)
        )
        self._tutor_worker.failed.connect(chat.add_tutor_error)
        self._tutor_worker.cancelled.connect(
            lambda: chat.add_system_note(
                "Request cancelled. Nothing was charged for a reply that was "
                "not shown, though a provider may still count the tokens it "
                "already generated."
            )
        )
        self._tutor_worker.finished.connect(lambda: chat.set_sending(False))

        self._tutor_worker.start()

    def _cancel_tutor_request(self) -> None:
        """Stop the request in flight, if there is one."""
        worker = self._tutor_worker
        if worker is None or not worker.isRunning():
            return
        worker.cancel()

    # ------------------------------------------------------------------
    # Tutor entry points
    # ------------------------------------------------------------------
    def _on_lesson_tutor(self, message: str, level: str, context: TutorContext) -> None:
        self._send_to_tutor(self.lesson_view.chat(), context, level)

    def _on_practice_tutor(self, message: str, level: str, marker: str) -> None:
        if marker == "__back_to_lesson__":
            self.show_page(PAGE_LESSON)
            return

        chat    = self.practice_view.chat()
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
            self._send_to_tutor(chat, context, "guided", rubric_exercise=exercise_id)
            return

        context = TutorContext(
            lesson_title=session.exercise.concept_id,
            section=f"exercise: {session.exercise.title} ({session.exercise.type})",
            code=session.editor_code() if hasattr(session, "editor_code") else "",
            user_message=message,
        )
        view               = self.practice_view
        context.code       = view.editor.code()
        context.compile_output = view.result_view.toPlainText()[:4000]
        context.attempt_count  = session.session.attempts
        context.misconception_shown = session.session.hints_used > 0
        self._send_to_tutor(chat, context, level)

    def _on_tutor_reply(self, reply: TutorReply, chat, rubric_exercise: str | None) -> None:
        chat.add_tutor_message(reply.as_chat_text())

        # Meter the call. Recorded even when the tutor's own parser disliked
        # the reply: the tokens were spent either way.
        service = self._tutor_service
        if service is not None:
            chat.record_usage(service.last_model, service.last_usage)

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
        from ..services.practice import parse_verdict

        verdict, reason = parse_verdict(reply.raw)

        session  = self.practice_view.session
        exercise = self.bank.get(exercise_id)
        if session is None or exercise is None:
            return

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
            self.lesson_view.toolchain   = self.toolchain
            self.lesson_view.refresh_sandbox_status()
            self._refresh_provider_status()
            # Apply any theme change immediately
            new_theme = self.settings.get("theme", "dark_orange")
            if new_theme != theme.active_theme():
                theme.apply_theme(self, new_theme)
            self.statusBar().showMessage("Settings saved")

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        try:
            self.toolchain.stop()
        except Exception:  # pragma: no cover
            pass
        try:
            self.database.close()
        except Exception:  # pragma: no cover
            pass
        super().closeEvent(event)


def _db_path() -> str:
    from ..config import db_path
    return str(db_path())