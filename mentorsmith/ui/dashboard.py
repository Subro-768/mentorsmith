"""Dashboard: curriculum navigation, overall progress and recent activity."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
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