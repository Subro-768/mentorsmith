"""Dashboard: curriculum navigation, overall progress and recent activity."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.curriculum import Lesson
from . import theme


class DashboardView(QWidget):
    """Landing page: pick a lesson, see how far you have got."""

    #: Emitted with a lesson id when the learner chooses one.
    lesson_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lessons: list[Lesson] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Dashboard")
        title.setObjectName("title")
        root.addWidget(title)

        self.subtitle = QLabel(
            "Pick a lesson to work on. Progress is stored locally and survives restarts."
        )
        self.subtitle.setObjectName("subtitle")
        root.addWidget(self.subtitle)

        progress_row = QHBoxLayout()
        progress_row.addWidget(QLabel("Curriculum progress:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_row.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("muted")
        progress_row.addWidget(self.progress_label)
        root.addLayout(progress_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.lesson_list = QListWidget()
        self.lesson_list.setAlternatingRowColors(False)
        self.lesson_list.itemDoubleClicked.connect(self._on_activate)
        self.lesson_list.itemClicked.connect(self._on_click)
        splitter.addWidget(self.lesson_list)

        self.activity_view = QTextBrowser()
        splitter.addWidget(self.activity_view)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        buttons = QHBoxLayout()
        self.open_button = QPushButton("Open selected lesson")
        self.open_button.setObjectName("primary")
        buttons.addWidget(self.open_button)
        buttons.addStretch(1)
        root.addLayout(buttons)

        self.open_button.clicked.connect(self._on_activate)
        self.lesson_list.itemDoubleClicked.connect(lambda _: self._on_activate())

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def set_lessons(self, lessons: list[Lesson]) -> None:
        self._lessons = lessons
        self.refresh([])

    def refresh(self, completed: set[str], stats: dict[str, dict] | None = None) -> None:
        """Rebuild the lesson list from the current database state."""
        self.lesson_list.clear()
        stats = stats or {}
        for lesson in self._lessons:
            info = stats.get(lesson.id, {})
            done = lesson.id in completed
            attempts = int(info.get("attempts", 0))

            mark = "✓" if done else "○"
            label = f"{mark}  {lesson.display_title}"
            if attempts:
                label += f"   ({attempts} attempt{'s' if attempts != 1 else ''})"

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, lesson.id)
            if done:
                item.setForeground(Qt.GlobalColor.green)
            else:
                item.setForeground(Qt.GlobalColor.lightGray)
            tooltip = f"{lesson.title}\n\n{lesson.section('objectives')[:400]}"
            item.setToolTip(tooltip)
            self.lesson_list.addItem(item)

        total = len(self._lessons)
        done_count = len([l for l in self._lessons if l.id in completed])
        percent = int(round(done_count * 100 / total)) if total else 0
        self.progress_bar.setValue(percent)
        self.progress_bar.setFormat(f"{percent}%")
        self.progress_label.setText(f"{done_count} of {total} lessons complete")

    def set_activity(self, entries: list[dict]) -> None:
        """Render the recent activity feed."""
        if not entries:
            self.activity_view.setHtml(
                f"<p style='color:{theme.MUTED}'>Nothing recorded yet. Open a "
                "lesson and press <b>Compile &amp; Run</b> to start building a "
                "history.</p>"
            )
            return

        rows = []
        for entry in entries:
            colour = {
                "lesson_complete": theme.SUCCESS,
                "exercise_attempt": theme.INFO,
                "exercise_passed": theme.SUCCESS,
                "exercise_failed": theme.WARNING,
            }.get(str(entry.get("kind")), theme.MUTED)
            rows.append(
                f"<tr>"
                f"<td style='color:{theme.MUTED};padding:2px 8px;white-space:nowrap'>"
                f"{entry.get('created_at', '')}</td>"
                f"<td style='color:{colour};padding:2px 8px'>"
                f"{_escape(str(entry.get('kind', '')))}</td>"
                f"<td style='padding:2px 8px'>{_escape(str(entry.get('detail', '')))}</td>"
                f"</tr>"
            )
        self.activity_view.setHtml(
            "<h3>Recent activity</h3>"
            "<table width='100%' cellspacing='0' cellpadding='0'>"
            + "".join(rows)
            + "</table>"
        )

    def select_lesson(self, lesson_id: str) -> None:
        for index in range(self.lesson_list.count()):
            item = self.lesson_list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) == lesson_id:
                self.lesson_list.setCurrentItem(item)
                return

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def selected_lesson_id(self) -> str | None:
        item = self.lesson_list.currentItem()
        return str(item.data(Qt.ItemDataRole.UserRole)) if item is not None else None

    def _on_activate(self) -> None:
        lesson_id = self.selected_lesson_id()
        if lesson_id:
            self.lesson_selected.emit(lesson_id)

    def _on_click(self, item: QListWidgetItem) -> None:
        self.open_button.setEnabled(True)


class InsightsPanel(QWidget):
    """Phase 2 panel: next activity with its reason, reviews, real statistics.

    Every number here comes from graded attempts. Chat message counts and time
    spent in the app are deliberately excluded, and the panel says so.
    """

    #: (exercise_id,) when the learner chooses the suggested activity.
    activity_requested = pyqtSignal(str)
    practice_requested = pyqtSignal()
    projects_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        self.summary = QLabel()
        self.summary.setObjectName("subtitle")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        # --- suggested next activity, with its reason ---
        next_box = QGroupBox("Suggested next activity")
        next_layout = QVBoxLayout(next_box)

        self.next_label = QLabel("Nothing to suggest yet.")
        self.next_label.setWordWrap(True)
        next_layout.addWidget(self.next_label)

        self.next_reason = QLabel()
        self.next_reason.setWordWrap(True)
        self.next_reason.setObjectName("muted")
        next_layout.addWidget(self.next_reason)

        buttons = QHBoxLayout()
        self.start_button = QPushButton("Start this exercise")
        self.start_button.setObjectName("primary")
        self.practice_button = QPushButton("Open practice")
        self.projects_button = QPushButton("Open projects")
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.practice_button)
        buttons.addWidget(self.projects_button)
        buttons.addStretch(1)
        next_layout.addLayout(buttons)
        layout.addWidget(next_box)

        # --- concepts to review ---
        review_box = QGroupBox("Concepts to review")
        review_layout = QVBoxLayout(review_box)
        self.review_view = QTextBrowser()
        self.review_view.setMaximumHeight(170)
        review_layout.addWidget(self.review_view)
        layout.addWidget(review_box)

        # --- independent work, hints, projects, recurring errors ---
        stats_row = QHBoxLayout()

        work_box = QGroupBox("Independent work")
        work_layout = QVBoxLayout(work_box)
        self.independent_label = QLabel("0")
        self.independent_label.setObjectName("title")
        work_layout.addWidget(self.independent_label)
        note = QLabel("graded attempts solved with no hints")
        note.setObjectName("muted")
        note.setWordWrap(True)
        work_layout.addWidget(note)
        self.hints_label = QLabel("0 hints used")
        self.hints_label.setObjectName("muted")
        work_layout.addWidget(self.hints_label)
        stats_row.addWidget(work_box)

        project_box = QGroupBox("Projects and milestones")
        project_layout = QVBoxLayout(project_box)
        self.project_label = QLabel("No projects started")
        self.project_label.setWordWrap(True)
        project_layout.addWidget(self.project_label)
        self.milestone_label = QLabel()
        self.milestone_label.setObjectName("muted")
        project_layout.addWidget(self.milestone_label)
        stats_row.addWidget(project_box)

        error_box = QGroupBox("Recurring error categories")
        error_layout = QVBoxLayout(error_box)
        self.error_view = QTextBrowser()
        self.error_view.setMaximumHeight(110)
        error_layout.addWidget(self.error_view)
        stats_row.addWidget(error_box)

        layout.addLayout(stats_row)

        # --- concept mastery table ---
        mastery_box = QGroupBox("Concepts and the evidence behind each label")
        mastery_layout = QVBoxLayout(mastery_box)
        self.mastery_view = QTextBrowser()
        self.mastery_view.setMaximumHeight(260)
        mastery_layout.addWidget(self.mastery_view)
        layout.addWidget(mastery_box)

        self.disclaimer = QLabel()
        self.disclaimer.setWordWrap(True)
        self.disclaimer.setObjectName("muted")
        layout.addWidget(self.disclaimer)

        self._next_exercise_id: str | None = None
        self.start_button.clicked.connect(
            lambda: self._next_exercise_id and self.activity_requested.emit(self._next_exercise_id)
        )
        self.practice_button.clicked.connect(self.practice_requested)
        self.projects_button.clicked.connect(self.projects_requested)

    def set_report(self, report) -> None:
        """Render a :class:`~mentorsmith.services.insights.DashboardReport`."""
        self.summary.setText(report.summary_line())
        self.disclaimer.setText(f"{report.disclaimer}  {report.not_evidence_note}")

        if report.next_activity is not None:
            self.next_label.setText(
                f"<b>{_escape(report.next_activity.title)}</b> — "
                f"{_escape(report.next_activity.concept_id)} "
                f"({_escape(report.next_activity.exercise_type)})"
            )
            self.next_reason.setText(
                f"<b>Why:</b> {_escape(report.next_activity_reason)}"
            )
            self._next_exercise_id = report.next_activity.exercise_id
            self.start_button.setEnabled(True)
        else:
            self.next_label.setText(report.next_activity_reason)
            self.next_reason.setText("")
            self._next_exercise_id = None
            self.start_button.setEnabled(False)

        if report.reviews:
            rows = []
            for item in report.reviews:
                rows.append(
                    f"<p><b>{_escape(item.title)}</b><br>"
                    f"<span style='color:{theme.MUTED}'>{_escape(item.reason)}</span></p>"
                )
            self.review_view.setHtml("".join(rows))
        else:
            self.review_view.setHtml(
                f"<p style='color:{theme.MUTED}'>Nothing flagged for review. "
                "That is not the same as knowing everything — it means no "
                "recorded attempt looks weak or stale yet.</p>"
            )

        self.independent_label.setText(str(report.independent_results))
        self.hints_label.setText(
            f"{report.hints_used} hint(s) used across {report.total_attempts} attempts"
        )

        if report.projects:
            in_progress = [
                p for p in report.projects if p.get("status") in ("in_progress", "not_started")
            ]
            self.project_label.setText(
                f"{len(report.projects)} started · {len(in_progress)} in progress"
            )
        else:
            self.project_label.setText("No projects started")
        done = report.milestone_totals.get("done", 0)
        total = report.milestone_totals.get("total", 0)
        self.milestone_label.setText(f"{done} of {total} milestones complete")

        if report.error_categories:
            rows = "".join(
                f"<li><b>{_escape(name)}</b> — {count} time(s)</li>"
                for name, count in report.error_categories
            )
            self.error_view.setHtml(f"<ul>{rows}</ul>")
        else:
            self.error_view.setHtml(
                f"<p style='color:{theme.MUTED}'>No error categories recorded yet.</p>"
            )

        rows = []
        for row in report.concepts:
            colour = {
                "strong": theme.SUCCESS,
                "developing": theme.INFO,
                "needs_review": theme.WARNING,
                "not_started": theme.MUTED,
            }.get(row.label, theme.MUTED)
            evidence = (
                "<br><span style='color:"
                + theme.MUTED
                + "'>"
                + " ".join(_escape(item) for item in row.evidence[:2])
                + "</span>"
                if row.evidence
                else ""
            )
            missing = (
                "<br><span style='color:"
                + theme.ERROR
                + "'>blocked by: "
                + _escape(", ".join(row.missing_prerequisites))
                + "</span>"
                if row.missing_prerequisites
                else ""
            )
            rows.append(
                f"<tr>"
                f"<td style='padding:3px 8px'>{_escape(row.title)}</td>"
                f"<td style='color:{colour};padding:3px 8px'>{row.label}</td>"
                f"<td style='padding:3px 8px'>{row.attempts}</td>"
                f"<td style='padding:3px 8px'>{row.correct}</td>"
                f"<td style='padding:3px 8px'>{row.independent}</td>"
                f"<td style='padding:3px 8px'>{row.hints_used}</td>"
                f"<td style='padding:3px 8px'>{row.score:.2f}"
                f"{evidence}{missing}</td>"
                f"</tr>"
            )
        self.mastery_view.setHtml(
            "<table width='100%' cellspacing='0' cellpadding='0'>"
            "<tr style='color:"
            + theme.MUTED
            + "'><th align='left'>Concept</th><th align='left'>Label</th>"
            "<th align='left'>Attempts</th><th align='left'>Correct</th>"
            "<th align='left'>Alone</th><th align='left'>Hints</th>"
            "<th align='left'>Score &amp; evidence</th></tr>"
            + "".join(rows)
            + "</table>"
        )


class ProgressView(QWidget):
    """Detailed progress, attempt history and data management."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Progress")
        title.setObjectName("title")
        root.addWidget(title)

        self.summary = QLabel()
        self.summary.setObjectName("subtitle")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.details = QTextBrowser()
        root.addWidget(self.details, 1)

        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        buttons.addWidget(self.refresh_button)
        buttons.addStretch(1)
        self.reset_button = QPushButton("Reset all progress")
        self.reset_button.setObjectName("danger")
        buttons.addWidget(self.reset_button)
        root.addLayout(buttons)

    def set_lessons(self, lessons: list[Lesson]) -> None:
        self._lessons = lessons

    def refresh(self, database, completed: list[str]) -> None:
        """Render per-lesson completion and attempt counts."""
        self._lessons = getattr(self, "_lessons", [])
        total = len(self._lessons)
        self.summary.setText(
            f"{len(completed)} of {total} lessons complete. "
            "Completion and every compile attempt are recorded in a local "
            "SQLite database and persist across restarts."
        )

        rows = []
        for lesson in self._lessons:
            attempts = database.exercise_attempts(lesson.id)
            done = lesson.id in completed
            compiled = sum(1 for a in attempts if a.get("compiled_ok"))
            ran_ok = sum(1 for a in attempts if a.get("ran_ok"))
            rows.append(
                f"<tr>"
                f"<td style='padding:3px 10px'>{_escape(lesson.display_title)}</td>"
                f"<td style='color:{theme.SUCCESS if done else theme.MUTED};padding:3px 10px'>"
                f"{'complete' if done else 'not started'}</td>"
                f"<td style='padding:3px 10px'>{len(attempts)}</td>"
                f"<td style='padding:3px 10px'>{compiled}</td>"
                f"<td style='padding:3px 10px'>{ran_ok}</td>"
                f"</tr>"
            )

        self.details.setHtml(
            "<table width='100%' cellspacing='0' cellpadding='0'>"
            "<tr style='color:"
            + theme.MUTED
            + "'>"
            "<th align='left' style='padding:4px 10px'>Lesson</th>"
            "<th align='left' style='padding:4px 10px'>Status</th>"
            "<th align='left' style='padding:4px 10px'>Attempts</th>"
            "<th align='left' style='padding:4px 10px'>Compiled</th>"
            "<th align='left' style='padding:4px 10px'>Ran clean</th>"
            "</tr>"
            + "".join(rows)
            + "</table>"
        )

    def confirm_reset(self) -> bool:
        """Ask before destroying recorded progress."""
        answer = QMessageBox.warning(
            self,
            "Reset all progress",
            "This permanently deletes every recorded lesson completion and "
            "exercise attempt.\n\nThis cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes


def _escape(text: str) -> str:
    import html as html_module

    return html_module.escape(text or "")