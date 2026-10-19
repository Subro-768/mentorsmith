"""Dashboard: lesson card grid, progress arc, activity timeline."""

from __future__ import annotations

import html as html_module

from PyQt6.QtCore import Qt, QPropertyAnimation, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.curriculum import Lesson
from ..core.mastery import LABEL_DESCRIPTIONS
from . import theme


# ---------------------------------------------------------------------------
# Lesson card widget
# ---------------------------------------------------------------------------

class LessonCard(QFrame):
    """A clickable card showing one lesson's status, number and title."""

    clicked = pyqtSignal(str)  # emits lesson_id

    def __init__(
        self,
        lesson: Lesson,
        number: int,
        done: bool,
        attempts: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._lesson_id = lesson.id
        self._done      = done

        if done:
            self.setObjectName("lesson_card_done")
        else:
            self.setObjectName("lesson_card")

        self.setMinimumHeight(72)
        self.setMaximumHeight(90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 10)
        lay.setSpacing(12)

        # Number badge
        badge = QLabel(str(number))
        badge.setFixedSize(28, 28)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if done:
            badge.setStyleSheet(
                f"background-color: {theme.SUCCESS}; color: #0d1117; "
                f"border-radius: 14px; font-size: 11px; font-weight: 700;"
            )
        else:
            badge.setStyleSheet(
                f"background-color: {theme.SURFACE_HOV}; color: {theme.MUTED}; "
                f"border-radius: 14px; font-size: 11px; font-weight: 700;"
            )
        lay.addWidget(badge)

        # Title + meta
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        text_col.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel(lesson.display_title)
        title_lbl.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: "
            f"{'#3fb950' if done else theme.FOREGROUND};"
        )
        title_lbl.setWordWrap(False)
        text_col.addWidget(title_lbl)

        if attempts:
            meta = QLabel(f"{attempts} attempt{'s' if attempts != 1 else ''}")
            meta.setStyleSheet(f"font-size: 11px; color: {theme.MUTED};")
            text_col.addWidget(meta)

        lay.addLayout(text_col, 1)

        # Status icon
        status = QLabel("✓" if done else "○")
        status.setStyleSheet(
            f"font-size: 16px; color: {'#3fb950' if done else theme.PLACEHOLDER};"
        )
        lay.addWidget(status)

        self.setToolTip(f"{lesson.title}\n\n{lesson.section('objectives')[:300]}")

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._lesson_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._lesson_id)
        super().mouseDoubleClickEvent(event)


# ---------------------------------------------------------------------------
# Backwards-compatibility shim so existing tests keep working
# ---------------------------------------------------------------------------

class _LessonListProxy:
    """Minimal proxy that mimics QListWidget.count() for the card grid.

    The old DashboardView exposed a QListWidget as ``lesson_list``; smoke tests
    assert ``window.dashboard.lesson_list.count() == 16``. Rather than patching
    every test, we expose this tiny adapter on DashboardView.
    """

    def __init__(self, dashboard: "DashboardView") -> None:
        self._dashboard = dashboard

    def count(self) -> int:
        return len(self._dashboard._lessons)


# ---------------------------------------------------------------------------
# Dashboard view
# ---------------------------------------------------------------------------

class DashboardView(QWidget):
    """Landing page: lesson card grid + activity feed."""

    lesson_selected = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lessons: list[Lesson] = []
        self._cards:   list[LessonCard] = []
        self._selected_lesson_id: str | None = None
        # Backwards-compatible attribute so existing tests can call .count()
        self.lesson_list = _LessonListProxy(self)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(0)

        # ── Header row ───────────────────────────────────────────────────
        header_row = QHBoxLayout()

        heading_col = QVBoxLayout()
        heading_col.setSpacing(2)
        title = QLabel("Dashboard")
        title.setObjectName("title")
        heading_col.addWidget(title)
        self.subtitle = QLabel(
            "Pick a lesson to work on. Progress is stored locally and survives restarts."
        )
        self.subtitle.setObjectName("subtitle")
        heading_col.addWidget(self.subtitle)
        header_row.addLayout(heading_col)
        header_row.addStretch(1)

        # Progress summary badge
        self.progress_label = QLabel("0 of 0 complete")
        self.progress_label.setObjectName("badge_muted")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header_row.addWidget(self.progress_label)
        root.addLayout(header_row)

        root.addSpacing(10)

        # ── Progress bar ─────────────────────────────────────────────────
        from PyQt6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {theme.SURFACE_ALT}; border: none; "
            f"border-radius: 4px; }} "
            f"QProgressBar::chunk {{ background: qlineargradient("
            f"x1:0,y1:0,x2:1,y2:0, stop:0 {theme.ACCENT}, stop:1 {theme.CYAN}); "
            f"border-radius: 4px; }}"
        )
        root.addWidget(self.progress_bar)

        root.addSpacing(20)

        # ── Main split: cards | activity ─────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # Left: scrollable card grid
        cards_container = QWidget()
        cards_outer = QVBoxLayout(cards_container)
        cards_outer.setContentsMargins(0, 0, 0, 0)
        cards_outer.setSpacing(8)

        section_lbl = QLabel("CURRICULUM")
        section_lbl.setObjectName("section_header")
        section_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {theme.PLACEHOLDER}; "
            f"letter-spacing: 0.8px; margin-bottom: 6px;"
        )
        cards_outer.addWidget(section_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet("background: transparent;")
        self._grid = QVBoxLayout(self._cards_widget)
        self._grid.setSpacing(8)
        self._grid.setContentsMargins(0, 0, 8, 8)
        self._grid.addStretch(1)

        scroll.setWidget(self._cards_widget)
        cards_outer.addWidget(scroll, 1)

        # Open button at bottom
        btn_row = QHBoxLayout()
        self.open_button = QPushButton("▶  Open Selected Lesson")
        self.open_button.setObjectName("primary")
        self.open_button.setFixedHeight(38)
        self.open_button.setEnabled(False)
        btn_row.addWidget(self.open_button)
        btn_row.addStretch(1)
        cards_outer.addLayout(btn_row)

        splitter.addWidget(cards_container)

        # Right: activity feed
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 0, 0, 0)
        right_layout.setSpacing(8)

        activity_lbl = QLabel("RECENT ACTIVITY")
        activity_lbl.setObjectName("section_header")
        activity_lbl.setStyleSheet(
            f"font-size: 10px; font-weight: 700; color: {theme.PLACEHOLDER}; letter-spacing: 0.8px;"
        )
        right_layout.addWidget(activity_lbl)

        self.activity_view = QTextBrowser()
        self.activity_view.setOpenExternalLinks(False)
        self.activity_view.setStyleSheet(
            f"QTextBrowser {{ background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 10px; padding: 12px; }}"
        )
        right_layout.addWidget(self.activity_view, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        root.addWidget(splitter, 1)

        self.open_button.clicked.connect(self._on_open)

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def set_lessons(self, lessons: list[Lesson]) -> None:
        self._lessons = lessons
        self.refresh(set())

    def refresh(self, completed: set[str], stats: dict[str, dict] | None = None) -> None:
        # Remove old cards
        for card in self._cards:
            card.deleteLater()
        self._cards.clear()

        # Clear stretch
        while self._grid.count():
            item = self._grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        stats = stats or {}
        for number, lesson in enumerate(self._lessons, start=1):
            info     = stats.get(lesson.id, {})
            done     = lesson.id in completed
            attempts = int(info.get("attempts", 0))

            card = LessonCard(lesson, number, done, attempts)
            card.clicked.connect(self._on_card_clicked)
            self._grid.addWidget(card)
            self._cards.append(card)

        self._grid.addStretch(1)

        total      = len(self._lessons)
        done_count = len([l for l in self._lessons if l.id in completed])
        percent    = int(round(done_count * 100 / total)) if total else 0
        self.progress_bar.setValue(percent)

        done_str = f"{done_count} of {total} complete"
        if done_count == total and total > 0:
            self.progress_label.setObjectName("badge_success")
        elif done_count == 0:
            self.progress_label.setObjectName("badge_muted")
        else:
            self.progress_label.setObjectName("badge_info")
        self.progress_label.setText(done_str)
        self.progress_label.style().unpolish(self.progress_label)
        self.progress_label.style().polish(self.progress_label)

        self._selected_lesson_id = None
        self.open_button.setEnabled(False)

    def set_activity(self, entries: list[dict]) -> None:
        if not entries:
            self.activity_view.setHtml(
                f"<div style='padding:20px; text-align:center;'>"
                f"<p style='color:{theme.PLACEHOLDER}; font-size:28px; margin:0'>📭</p>"
                f"<p style='color:{theme.MUTED}; margin-top:8px'>Nothing recorded yet.</p>"
                f"<p style='color:{theme.PLACEHOLDER}; font-size:12px'>Open a lesson and press "
                f"<b style='color:{theme.MUTED}'>Compile &amp; Run</b> to start building history.</p>"
                f"</div>"
            )
            return

        event_conf = {
            "lesson_complete":  (theme.SUCCESS, "✓", "Lesson complete"),
            "exercise_attempt": (theme.INFO,    "◈", "Exercise attempt"),
            "exercise_passed":  (theme.SUCCESS, "✓", "Exercise passed"),
            "exercise_failed":  (theme.WARNING, "✗", "Exercise failed"),
        }

        rows = []
        for entry in entries:
            kind   = str(entry.get("kind", ""))
            colour, icon, label = event_conf.get(kind, (theme.MUTED, "•", kind))
            time_str = str(entry.get("created_at", ""))
            detail   = _escape(str(entry.get("detail", "")))
            rows.append(
                f"<div style='display:flex; padding:8px 0; border-bottom:1px solid {theme.BORDER_SUB};'>"
                f"<span style='color:{colour}; font-size:16px; width:20px; flex-shrink:0'>{icon}</span>"
                f"<div style='margin-left:10px; flex:1'>"
                f"<div style='color:{colour}; font-size:12px; font-weight:600'>{label}</div>"
                f"<div style='color:{theme.FOREGROUND}; font-size:12px'>{detail}</div>"
                f"<div style='color:{theme.PLACEHOLDER}; font-size:11px'>{_escape(time_str)}</div>"
                f"</div></div>"
            )
        self.activity_view.setHtml(
            f"<div style='font-family: system-ui, sans-serif; padding: 4px;'>"
            + "".join(rows)
            + "</div>"
        )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def _on_card_clicked(self, lesson_id: str) -> None:
        self._selected_lesson_id = lesson_id
        self.open_button.setEnabled(True)
        # Highlight selected card
        for card in self._cards:
            if card._lesson_id == lesson_id:
                card.setObjectName("lesson_card_active")
            elif card._done:
                card.setObjectName("lesson_card_done")
            else:
                card.setObjectName("lesson_card")
            card.style().unpolish(card)
            card.style().polish(card)

    def _on_open(self) -> None:
        if self._selected_lesson_id:
            self.lesson_selected.emit(self._selected_lesson_id)

    def selected_lesson_id(self) -> str | None:
        return self._selected_lesson_id


# ---------------------------------------------------------------------------
# Insights panel
# ---------------------------------------------------------------------------

class InsightsPanel(QWidget):
    """Phase 2 panel: next activity, mastery, projects, recurring errors."""

    activity_requested = pyqtSignal(str)
    practice_requested = pyqtSignal()
    projects_requested = pyqtSignal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Title
        title = QLabel("Progress Insights")
        title.setObjectName("title")
        layout.addWidget(title)

        self.summary = QLabel()
        self.summary.setObjectName("subtitle")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)

        # Next activity card
        next_box = QGroupBox("Suggested next activity")
        next_layout = QVBoxLayout(next_box)
        next_layout.setSpacing(8)

        self.next_label = QLabel("Nothing to suggest yet.")
        self.next_label.setWordWrap(True)
        self.next_label.setStyleSheet(f"font-size: 14px; font-weight: 600; color: {theme.FOREGROUND};")
        next_layout.addWidget(self.next_label)

        self.next_reason = QLabel()
        self.next_reason.setWordWrap(True)
        self.next_reason.setObjectName("muted")
        next_layout.addWidget(self.next_reason)

        buttons = QHBoxLayout()
        self.start_button    = QPushButton("▶  Start this exercise")
        self.start_button.setObjectName("primary")
        self.start_button.setFixedHeight(36)
        self.practice_button = QPushButton("⚡  Open practice")
        self.practice_button.setFixedHeight(36)
        self.projects_button = QPushButton("🏗  Open projects")
        self.projects_button.setFixedHeight(36)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.practice_button)
        buttons.addWidget(self.projects_button)
        buttons.addStretch(1)
        next_layout.addLayout(buttons)
        layout.addWidget(next_box)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)

        work_box    = self._metric_box("Independent work")
        work_layout = QVBoxLayout(work_box)
        self.independent_label = QLabel("0")
        self.independent_label.setStyleSheet(
            f"font-size: 32px; font-weight: 800; color: {theme.ACCENT_LIGHT};"
        )
        work_layout.addWidget(self.independent_label)
        note = QLabel("graded attempts solved with no hints")
        note.setObjectName("muted")
        note.setWordWrap(True)
        work_layout.addWidget(note)
        self.hints_label = QLabel("0 hints used")
        self.hints_label.setObjectName("muted")
        work_layout.addWidget(self.hints_label)
        stats_row.addWidget(work_box)

        project_box    = self._metric_box("Projects & milestones")
        project_layout = QVBoxLayout(project_box)
        self.project_label = QLabel("No projects started")
        self.project_label.setWordWrap(True)
        self.project_label.setStyleSheet(f"font-size: 14px; color: {theme.FOREGROUND};")
        project_layout.addWidget(self.project_label)
        self.milestone_label = QLabel()
        self.milestone_label.setObjectName("muted")
        project_layout.addWidget(self.milestone_label)
        stats_row.addWidget(project_box)

        layout.addLayout(stats_row)

        # Review box
        review_box    = QGroupBox("Concepts to review")
        review_layout = QVBoxLayout(review_box)
        self.review_view = QTextBrowser()
        self.review_view.setMaximumHeight(160)
        self.review_view.setStyleSheet(
            f"background: {theme.BASE}; border: none; border-radius: 6px;"
        )
        review_layout.addWidget(self.review_view)
        layout.addWidget(review_box)

        # Error box
        error_box    = QGroupBox("Recurring error categories")
        error_layout = QVBoxLayout(error_box)
        self.error_view = QTextBrowser()
        self.error_view.setMaximumHeight(100)
        self.error_view.setStyleSheet(
            f"background: {theme.BASE}; border: none; border-radius: 6px;"
        )
        error_layout.addWidget(self.error_view)
        layout.addWidget(error_box)

        # Mastery table
        mastery_box    = QGroupBox("Concepts & evidence")
        mastery_layout = QVBoxLayout(mastery_box)
        self.mastery_view = QTextBrowser()
        self.mastery_view.setMaximumHeight(280)
        self.mastery_view.setStyleSheet(
            f"background: {theme.BASE}; border: none; border-radius: 6px;"
        )
        mastery_layout.addWidget(self.mastery_view)
        layout.addWidget(mastery_box)

        self.disclaimer = QLabel()
        self.disclaimer.setWordWrap(True)
        self.disclaimer.setObjectName("muted")
        layout.addWidget(self.disclaimer)
        layout.addStretch(1)

        scroll.setWidget(inner)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._next_exercise_id: str | None = None
        self.start_button.clicked.connect(
            lambda: self._next_exercise_id and self.activity_requested.emit(self._next_exercise_id)
        )
        self.practice_button.clicked.connect(self.practice_requested)
        self.projects_button.clicked.connect(self.projects_requested)

    def _metric_box(self, title: str) -> QGroupBox:
        box = QGroupBox(title)
        return box

    def set_report(self, report) -> None:
        self.summary.setText(report.summary_line())
        self.disclaimer.setText(f"{report.disclaimer}  {report.not_evidence_note}")

        if report.next_activity is not None:
            self.next_label.setText(
                f"<b>{_escape(report.next_activity.title)}</b> — "
                f"{_escape(report.next_activity.concept_id)} "
                f"({_escape(report.next_activity.exercise_type)})"
            )
            self.next_reason.setText(f"<b>Why:</b> {_escape(report.next_activity_reason)}")
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
                f"<p style='color:{theme.MUTED}'>Nothing flagged for review. That is not "
                "the same as knowing everything — it means no recorded attempt looks weak "
                "or stale yet.</p>"
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

        done  = report.milestone_totals.get("done", 0)
        total = report.milestone_totals.get("total", 0)
        self.milestone_label.setText(f"{done} of {total} milestones complete")

        if report.error_categories:
            rows = "".join(
                f"<li><b>{_escape(name)}</b> — {count} time(s)</li>"
                for name, count in report.error_categories
            )
            self.error_view.setHtml(f"<ul style='margin:0; padding-left:16px'>{rows}</ul>")
        else:
            self.error_view.setHtml(
                f"<p style='color:{theme.MUTED}'>No error categories recorded yet.</p>"
            )

        label_colour = {
            "strong":      theme.SUCCESS,
            "developing":  theme.INFO,
            "needs_review":theme.WARNING,
            "not_started": theme.MUTED,
        }
        rows = []
        for row in report.concepts:
            colour = label_colour.get(row.label, theme.MUTED)
            evidence = (
                f"<br><span style='color:{theme.MUTED}'>"
                + " ".join(_escape(item) for item in row.evidence[:2])
                + "</span>"
                if row.evidence else ""
            )
            missing = (
                f"<br><span style='color:{theme.ERROR}'>blocked by: "
                + _escape(", ".join(row.missing_prerequisites))
                + "</span>"
                if row.missing_prerequisites else ""
            )
            label_pill = (
                f"<span style='background:{colour}22; color:{colour}; "
                f"border:1px solid {colour}; border-radius:8px; "
                f"padding:1px 6px; font-size:11px; font-weight:600'>"
                f"{row.label.replace('_', ' ')}</span>"
            )
            rows.append(
                f"<tr>"
                f"<td style='padding:5px 10px'>{_escape(row.title)}</td>"
                f"<td style='padding:5px 10px'>{label_pill}</td>"
                f"<td style='padding:5px 10px; color:{theme.MUTED}'>{row.attempts}</td>"
                f"<td style='padding:5px 10px; color:{theme.SUCCESS}'>{row.correct}</td>"
                f"<td style='padding:5px 10px; color:{theme.MUTED}'>{row.independent}</td>"
                f"<td style='padding:5px 10px; color:{theme.WARNING}'>{row.hints_used}</td>"
                f"<td style='padding:5px 10px'>{row.score:.2f}{evidence}{missing}</td>"
                f"</tr>"
            )

        legend = "".join(
            f"<tr><td style='padding:2px 10px'><b>{label.replace('_', ' ')}</b></td>"
            f"<td style='padding:2px 10px; color:{theme.MUTED}'>{_escape(description)}</td></tr>"
            for label, description in LABEL_DESCRIPTIONS.items()
        )

        self.mastery_view.setHtml(
            f"<table width='100%' cellspacing='0' cellpadding='0' "
            f"style='font-family:system-ui,sans-serif'>"
            f"<tr style='color:{theme.MUTED}; font-size:11px; font-weight:700; "
            f"text-transform:uppercase; letter-spacing:0.5px'>"
            f"<th align='left' style='padding:6px 10px'>Concept</th>"
            f"<th align='left' style='padding:6px 10px'>Label</th>"
            f"<th align='left' style='padding:6px 10px'>Tries</th>"
            f"<th align='left' style='padding:6px 10px'>✓</th>"
            f"<th align='left' style='padding:6px 10px'>Alone</th>"
            f"<th align='left' style='padding:6px 10px'>Hints</th>"
            f"<th align='left' style='padding:6px 10px'>Score</th></tr>"
            + "".join(rows)
            + "</table>"
            + f"<p style='margin-top:14px; color:{theme.MUTED}; font-size:12px'>"
              f"<b style='color:{theme.FOREGROUND}'>What the labels mean</b></p>"
            + "<table width='100%' cellspacing='0' cellpadding='0'>" + legend + "</table>"
        )


# ---------------------------------------------------------------------------
# Progress view
# ---------------------------------------------------------------------------

class ProgressView(QWidget):
    """Detailed progress, attempt history and data management."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        title = QLabel("History")
        title.setObjectName("title")
        root.addWidget(title)

        self.summary = QLabel()
        self.summary.setObjectName("subtitle")
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.details = QTextBrowser()
        self.details.setStyleSheet(
            f"QTextBrowser {{ background-color: {theme.SURFACE}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 10px; padding: 12px; }}"
        )
        root.addWidget(self.details, 1)

        buttons = QHBoxLayout()
        self.refresh_button = QPushButton("↺  Refresh")
        self.refresh_button.setFixedHeight(36)
        buttons.addWidget(self.refresh_button)
        buttons.addStretch(1)
        self.reset_button = QPushButton("Reset all progress")
        self.reset_button.setObjectName("danger")
        self.reset_button.setFixedHeight(36)
        buttons.addWidget(self.reset_button)
        root.addLayout(buttons)

    def set_lessons(self, lessons: list[Lesson]) -> None:
        self._lessons = lessons

    def refresh(self, database, completed: list[str]) -> None:
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
            done     = lesson.id in completed
            compiled = sum(1 for a in attempts if a.get("compiled_ok"))
            ran_ok   = sum(1 for a in attempts if a.get("ran_ok"))

            status_pill = (
                f"<span style='background:{theme.SUCCESS}22; color:{theme.SUCCESS}; "
                f"border:1px solid {theme.SUCCESS}; border-radius:8px; padding:1px 8px; "
                f"font-size:11px; font-weight:600'>complete</span>"
                if done else
                f"<span style='background:{theme.SURFACE_HOV}; color:{theme.MUTED}; "
                f"border:1px solid {theme.BORDER}; border-radius:8px; padding:1px 8px; "
                f"font-size:11px'>not started</span>"
            )
            rows.append(
                f"<tr style='border-bottom:1px solid {theme.BORDER_SUB}'>"
                f"<td style='padding:8px 12px; color:{theme.FOREGROUND}'>{_escape(lesson.display_title)}</td>"
                f"<td style='padding:8px 12px'>{status_pill}</td>"
                f"<td style='padding:8px 12px; color:{theme.MUTED}'>{len(attempts)}</td>"
                f"<td style='padding:8px 12px; color:{theme.MUTED}'>{compiled}</td>"
                f"<td style='padding:8px 12px; color:{theme.MUTED}'>{ran_ok}</td>"
                f"</tr>"
            )

        self.details.setHtml(
            f"<table width='100%' cellspacing='0' cellpadding='0' "
            f"style='font-family:system-ui,sans-serif'>"
            f"<tr style='color:{theme.PLACEHOLDER}; font-size:11px; font-weight:700; text-transform:uppercase'>"
            f"<th align='left' style='padding:8px 12px'>Lesson</th>"
            f"<th align='left' style='padding:8px 12px'>Status</th>"
            f"<th align='left' style='padding:8px 12px'>Attempts</th>"
            f"<th align='left' style='padding:8px 12px'>Compiled</th>"
            f"<th align='left' style='padding:8px 12px'>Ran ok</th></tr>"
            + "".join(rows)
            + "</table>"
        )

    def confirm_reset(self) -> bool:
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
    return html_module.escape(text or "")