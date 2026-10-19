"""Analytics & Home Dashboard.

Shows overall learning progress, daily streak, XP and level calculation,
per-language breakdown, interactive activity heatmap, and recent history.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
import html as html_module

#: The XP rates that define a level. Named so the formula and its description
#: cannot drift apart - they did once, with a comment claiming 10 XP per lesson
#: above a line awarding 20.
XP_PER_LESSON = 20
XP_PER_SUCCESS = 5
XP_PER_ATTEMPT = 2

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core import curriculum_registry
from ..core.db import Database
from . import theme


# ---------------------------------------------------------------------------
# Stat Metric Card
# ---------------------------------------------------------------------------

class MetricCard(QFrame):
    """Large modern stat card with an icon, metric value, and label."""

    def __init__(
        self,
        icon: str,
        value: str,
        title: str,
        subtitle: str = "",
        highlight_color: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"MetricCard {{ "
            f"  background-color: {theme.SURFACE}; "
            f"  border: 1px solid {theme.BORDER}; "
            f"  border-radius: 12px; "
            f"  padding: 12px; "
            f"}}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 20px;")
        top_row.addWidget(icon_lbl)

        title_lbl = QLabel(title.upper())
        title_lbl.setStyleSheet(
            f"font-size: 11px; font-weight: 700; color: {theme.MUTED}; letter-spacing: 0.5px;"
        )
        top_row.addWidget(title_lbl)
        top_row.addStretch(1)
        lay.addLayout(top_row)

        self.val_lbl = QLabel(value)
        color = highlight_color or theme.FOREGROUND
        self.val_lbl.setStyleSheet(f"font-size: 28px; font-weight: 800; color: {color};")
        lay.addWidget(self.val_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setStyleSheet(f"font-size: 11px; color: {theme.PLACEHOLDER};")
            lay.addWidget(sub_lbl)

    def set_value(self, val: str) -> None:
        self.val_lbl.setText(val)


# ---------------------------------------------------------------------------
# Language Progress Card
# ---------------------------------------------------------------------------

class LanguageProgressCard(QFrame):
    """Card displaying a language's completion percentage and attempt stats."""

    language_clicked = pyqtSignal(str)

    def __init__(
        self,
        lang_id: str,
        lang_name: str,
        completed_lessons: int,
        total_lessons: int,
        attempts: int,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.lang_id = lang_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"LanguageProgressCard {{ "
            f"  background-color: {theme.SURFACE}; "
            f"  border: 1px solid {theme.BORDER}; "
            f"  border-radius: 12px; "
            f"}} "
            f"LanguageProgressCard:hover {{ "
            f"  border-color: {theme.ACCENT}; "
            f"  background-color: {theme.SURFACE_ALT}; "
            f"}}"
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(8)

        # Header
        hdr = QHBoxLayout()
        name_lbl = QLabel(lang_name)
        name_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.FOREGROUND};")
        hdr.addWidget(name_lbl)
        hdr.addStretch(1)

        pct = int(round(completed_lessons * 100 / total_lessons)) if total_lessons else 0
        pct_lbl = QLabel(f"{pct}%")
        pct_lbl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {theme.ACCENT_LIGHT};")
        hdr.addWidget(pct_lbl)
        lay.addLayout(hdr)

        # Progress bar
        pbar = QProgressBar()
        pbar.setRange(0, 100)
        pbar.setValue(pct)
        pbar.setFixedHeight(6)
        pbar.setTextVisible(False)
        pbar.setStyleSheet(
            f"QProgressBar {{ background-color: {theme.SURFACE_HOV}; border: none; border-radius: 3px; }} "
            f"QProgressBar::chunk {{ background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 {theme.ACCENT}, stop:1 {theme.CYAN}); border-radius: 3px; }}"
        )
        lay.addWidget(pbar)

        # Meta
        meta_row = QHBoxLayout()
        meta_txt = f"{completed_lessons}/{total_lessons} lessons · {attempts} attempts"
        meta_lbl = QLabel(meta_txt)
        meta_lbl.setStyleSheet(f"font-size: 11px; color: {theme.MUTED};")
        meta_row.addWidget(meta_lbl)
        meta_row.addStretch(1)

        arrow = QLabel("➔")
        arrow.setStyleSheet(f"color: {theme.PLACEHOLDER}; font-size: 12px;")
        meta_row.addWidget(arrow)
        lay.addLayout(meta_row)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.language_clicked.emit(self.lang_id)
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Analytics View
# ---------------------------------------------------------------------------

class AnalyticsView(QWidget):
    """Comprehensive user analytics home dashboard."""

    language_switch_requested = pyqtSignal(str)

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.database = database
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet(f"background: {theme.BASE};")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(28, 24, 28, 24)
        lay.setSpacing(20)

        # ── Welcome / Header ──────────────────────────────────────────────
        header = QHBoxLayout()
        header_text = QVBoxLayout()
        header_text.setSpacing(2)

        self.welcome_title = QLabel("Welcome back, Learner! 👋")
        self.welcome_title.setObjectName("title")
        header_text.addWidget(self.welcome_title)

        subtitle = QLabel("Here is an overview of your coding journey across all languages.")
        subtitle.setObjectName("subtitle")
        header_text.addWidget(subtitle)
        header.addLayout(header_text)
        header.addStretch(1)

        # Level / XP banner
        self.xp_card = QFrame()
        self.xp_card.setStyleSheet(
            f"background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 12px; padding: 6px 14px;"
        )
        xp_lay = QVBoxLayout(self.xp_card)
        xp_lay.setContentsMargins(12, 8, 12, 8)
        xp_lay.setSpacing(4)

        self.level_lbl = QLabel("Level 1 · Novice")
        self.level_lbl.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {theme.CYAN};")
        xp_lay.addWidget(self.level_lbl)

        self.xp_bar = QProgressBar()
        self.xp_bar.setRange(0, 100)
        # 0, not a plausible-looking placeholder. refresh() sets the real value
        # before the view is ever shown, but a bar that starts at 10% is a small
        # lie that becomes a real one the moment refresh() fails.
        self.xp_bar.setValue(0)
        self.xp_bar.setFixedWidth(140)
        self.xp_bar.setFixedHeight(5)
        self.xp_bar.setTextVisible(False)
        self.xp_bar.setStyleSheet(
            f"QProgressBar {{ background-color: {theme.SURFACE_HOV}; border: none; border-radius: 2px; }} "
            f"QProgressBar::chunk {{ background-color: {theme.CYAN}; border-radius: 2px; }}"
        )
        xp_lay.addWidget(self.xp_bar)

        self.xp_details = QLabel("0 XP")
        self.xp_details.setStyleSheet(f"font-size: 10px; color: {theme.MUTED};")
        xp_lay.addWidget(self.xp_details)

        header.addWidget(self.xp_card)
        lay.addLayout(header)

        # ── Metrics Row ───────────────────────────────────────────────────
        self.metrics_layout = QGridLayout()
        self.metrics_layout.setSpacing(14)

        self.card_lessons = MetricCard("📚", "0", "Total Completed", "across all tracks", theme.SUCCESS)
        self.card_attempts = MetricCard("⚡", "0", "Exercises Attempted", "total runs and checks", theme.INFO)
        self.card_accuracy = MetricCard("🎯", "0%", "Success Rate", "passed without errors", theme.ACCENT_LIGHT)
        self.card_streak = MetricCard("🔥", "0 Days", "Active Streak", "consecutive daily learning", theme.WARNING)

        self.metrics_layout.addWidget(self.card_lessons, 0, 0)
        self.metrics_layout.addWidget(self.card_attempts, 0, 1)
        self.metrics_layout.addWidget(self.card_accuracy, 0, 2)
        self.metrics_layout.addWidget(self.card_streak, 0, 3)
        lay.addLayout(self.metrics_layout)

        # ── Languages Breakdown ───────────────────────────────────────────
        sec_lang = QLabel("TRACKS & LANGUAGES")
        sec_lang.setObjectName("section_header")
        lay.addWidget(sec_lang)

        self.lang_grid = QGridLayout()
        self.lang_grid.setSpacing(12)
        lay.addLayout(self.lang_grid)

        # ── Activity Heatmap ──────────────────────────────────────────────
        sec_heat = QLabel("ACTIVITY HEATMAP (LAST 14 WEEKS)")
        sec_heat.setObjectName("section_header")
        lay.addWidget(sec_heat)

        self.heatmap_view = QTextBrowser()
        self.heatmap_view.setFixedHeight(140)
        self.heatmap_view.setStyleSheet(
            f"background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 12px; padding: 10px;"
        )
        lay.addWidget(self.heatmap_view)

        # ── Recent Timeline ───────────────────────────────────────────────
        sec_recent = QLabel("RECENT GLOBAL ACTIVITY")
        sec_recent.setObjectName("section_header")
        lay.addWidget(sec_recent)

        self.recent_view = QTextBrowser()
        self.recent_view.setFixedHeight(180)
        self.recent_view.setStyleSheet(
            f"background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 12px; padding: 10px;"
        )
        lay.addWidget(self.recent_view)

        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # Data Refresh
    # ------------------------------------------------------------------

    def refresh(self) -> None:
        conn = self.database.connect()

        # 1. Total Completed Lessons across languages
        comp_rows = conn.execute("SELECT language, lesson_id FROM lesson_progress").fetchall()
        total_completed = len(comp_rows)
        comp_by_lang: dict[str, set[str]] = {}
        for r in comp_rows:
            comp_by_lang.setdefault(str(r["language"]), set()).add(str(r["lesson_id"]))

        # 2. Exercise Attempts
        att_rows = conn.execute(
            "SELECT language, compiled_ok, ran_ok FROM exercise_attempts"
        ).fetchall()
        total_attempts = len(att_rows)
        successful_attempts = sum(1 for r in att_rows if r["compiled_ok"] and r["ran_ok"])
        accuracy = int(round(successful_attempts * 100 / total_attempts)) if total_attempts else 0

        attempts_by_lang: dict[str, int] = {}
        for r in att_rows:
            lang = str(r["language"])
            attempts_by_lang[lang] = attempts_by_lang.get(lang, 0) + 1

        # 3. Activity dates for Streak and Heatmap
        act_rows = conn.execute("SELECT created_at, kind, detail, language FROM activity ORDER BY id ASC").fetchall()

        dates_with_activity: dict[str, int] = {}
        for r in act_rows:
            stamp = str(r["created_at"])
            dt = stamp.split("T")[0] if "T" in stamp else stamp.split(" ")[0]
            if dt:
                dates_with_activity[dt] = dates_with_activity.get(dt, 0) + 1

        streak = self._calculate_streak(set(dates_with_activity.keys()))

        # 4. XP and Level
        # 20 XP per lesson completed, 5 XP per successful attempt, 2 XP per
        # attempt. The rates below are the definition of a level, so they are
        # named rather than inlined - the comment here used to say 10 XP per
        # lesson while the line beneath it awarded 20, which is the kind of
        # drift that makes a progression system impossible to reason about.
        xp = (total_completed * XP_PER_LESSON
              + successful_attempts * XP_PER_SUCCESS
              + total_attempts * XP_PER_ATTEMPT)
        level, lvl_name, pct_level, next_xp = self._calculate_level(xp)

        # Update cards
        self.card_lessons.set_value(str(total_completed))
        self.card_attempts.set_value(str(total_attempts))
        self.card_accuracy.set_value(f"{accuracy}%")
        self.card_streak.set_value(f"{streak} Day{'s' if streak != 1 else ''}")

        self.level_lbl.setText(f"Level {level} · {lvl_name}")
        self.xp_bar.setValue(pct_level)
        if next_xp is None:
            # Top level reached. There is no next one, so say that rather than
            # naming a threshold the learner has already passed - which is what
            # this used to display.
            self.xp_details.setText(f"{xp} XP · Top level reached")
        else:
            self.xp_details.setText(f"{xp} XP (Next level at {next_xp} XP)")

        # 5. Populate Language Cards
        # Clear existing
        while self.lang_grid.count():
            item = self.lang_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tracks = curriculum_registry.load_all()
        col = 0
        row = 0
        for lang_id in curriculum_registry.LANGUAGE_IDS:
            track = tracks.get(lang_id)
            total_l = len(track.lessons) if track else 0
            done_l = len(comp_by_lang.get(lang_id, set()))
            atts = attempts_by_lang.get(lang_id, 0)
            label = curriculum_registry.display_name(lang_id)

            card = LanguageProgressCard(lang_id, label, done_l, total_l, atts)
            card.language_clicked.connect(self.language_switch_requested.emit)
            self.lang_grid.addWidget(card, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1

        # 6. Render Heatmap
        self._render_heatmap(dates_with_activity)

        # 7. Render Recent Global Activity
        self._render_recent_timeline(act_rows[-10:])

    def _calculate_streak(self, active_dates: set[str]) -> int:
        if not active_dates:
            return 0
        today = date.today()
        cur = today
        # Check if active today or yesterday
        today_str = today.isoformat()
        yesterday_str = (today - timedelta(days=1)).isoformat()

        if today_str not in active_dates and yesterday_str not in active_dates:
            return 0

        if today_str not in active_dates:
            cur = today - timedelta(days=1)

        streak = 0
        while cur.isoformat() in active_dates:
            streak += 1
            cur -= timedelta(days=1)
        return streak

    def _calculate_level(self, xp: int) -> tuple[int, str, int, int | None]:
        """Return (level, name, percent_through_this_level, next_threshold).

        ``next_threshold`` is None at the top level, because there is no next
        one. Reporting a fabricated threshold there produced the text "12000 XP
        (Next level at 10000 XP)" for a learner who was already past it.
        """
        levels = [
            (0, "Novice"),
            (100, "Apprentice"),
            (250, "Coder"),
            (500, "Developer"),
            (1000, "Engineer"),
            (2000, "Architect"),
            (5000, "Master"),
        ]
        curr_lvl = 1
        curr_name = "Novice"
        next_threshold = levels[1][0]
        prev_threshold = 0

        for i, (threshold, name) in enumerate(levels):
            if xp >= threshold:
                curr_lvl = i + 1
                curr_name = name
                prev_threshold = threshold
                next_threshold = levels[i + 1][0] if i + 1 < len(levels) else None
            else:
                break

        if next_threshold is None:
            # Top level: the bar is simply full, and there is nothing to reach.
            return curr_lvl, curr_name, 100, None

        span = next_threshold - prev_threshold
        progress_in_level = xp - prev_threshold
        pct = min(100, max(0, int(progress_in_level * 100 / span))) if span else 100
        return curr_lvl, curr_name, pct, next_threshold

    def _render_heatmap(self, dates_with_activity: dict[str, int]) -> None:
        today = date.today()
        # Go back 90 days, then align back to Monday so the columns are whole
        # weeks. That alignment can add up to six more days, so the window is
        # 90-96 days, not 90 - which is why the heading says 14 weeks rather
        # than 90 days.
        start_date = today - timedelta(days=90)
        start_date -= timedelta(days=start_date.weekday())

        days_count = (today - start_date).days + 1
        weeks: list[list[date]] = []
        curr_week: list[date] = []

        for d_offset in range(days_count):
            d = start_date + timedelta(days=d_offset)
            curr_week.append(d)
            if len(curr_week) == 7:
                weeks.append(curr_week)
                curr_week = []
        if curr_week:
            weeks.append(curr_week)

        # Build HTML table
        cells_by_day_of_week = [[] for _ in range(7)]
        for week in weeks:
            for day_idx in range(7):
                if day_idx < len(week):
                    d = week[day_idx]
                    count = dates_with_activity.get(d.isoformat(), 0)
                    if count == 0:
                        bg = theme.SURFACE_HOV
                    elif count < 3:
                        bg = "#234e34"
                    elif count < 6:
                        bg = "#2ea043"
                    else:
                        bg = "#3fb950"
                    tip = f"{d.strftime('%b %d, %Y')}: {count} action{'s' if count != 1 else ''}"
                    cells_by_day_of_week[day_idx].append(
                        f"<td title='{tip}' style='width:12px; height:12px; background:{bg}; "
                        f"border-radius:2px;'></td>"
                    )
                else:
                    cells_by_day_of_week[day_idx].append("<td style='width:12px; height:12px;'></td>")

        day_labels = ["Mon", "", "Wed", "", "Fri", "", ""]
        table_rows = []
        for day_idx in range(7):
            label = day_labels[day_idx]
            row_html = (
                f"<tr><td style='font-size:9px; color:{theme.MUTED}; width:24px; padding-right:4px;'>{label}</td>"
                + "".join(cells_by_day_of_week[day_idx])
                + "</tr>"
            )
            table_rows.append(row_html)

        html = (
            f"<div style='font-family:system-ui,sans-serif;'>"
            f"<table cellspacing='3' cellpadding='0'>"
            + "".join(table_rows)
            + "</table>"
            f"<div style='margin-top:6px; font-size:10px; color:{theme.MUTED}; display:flex; align-items:center;'>"
            f"<span>Less</span>"
            f"<span style='display:inline-block; width:10px; height:10px; background:{theme.SURFACE_HOV}; margin:0 3px; border-radius:2px;'></span>"
            f"<span style='display:inline-block; width:10px; height:10px; background:#234e34; margin:0 3px; border-radius:2px;'></span>"
            f"<span style='display:inline-block; width:10px; height:10px; background:#2ea043; margin:0 3px; border-radius:2px;'></span>"
            f"<span style='display:inline-block; width:10px; height:10px; background:#3fb950; margin:0 3px; border-radius:2px;'></span>"
            f"<span>More</span>"
            f"</div>"
            f"</div>"
        )
        self.heatmap_view.setHtml(html)

    def _render_recent_timeline(self, recent_entries: list) -> None:
        if not recent_entries:
            self.recent_view.setHtml(
                f"<p style='color:{theme.MUTED}; font-size:12px; margin:10px;'>No activity recorded yet.</p>"
            )
            return

        icon_map = {
            "lesson_complete": ("✓", theme.SUCCESS),
            "exercise_passed": ("✓", theme.SUCCESS),
            "exercise_failed": ("✗", theme.WARNING),
            "exercise_attempt": ("◈", theme.INFO),
        }

        rows = []
        for item in reversed(recent_entries):
            kind = str(item["kind"])
            detail = html_module.escape(str(item["detail"]))
            lang = html_module.escape(str(item["language"] or "").upper())
            stamp = str(item["created_at"])[:16].replace("T", " ")
            icon, color = icon_map.get(kind, ("•", theme.MUTED))

            rows.append(
                f"<div style='padding:5px 0; border-bottom:1px solid {theme.BORDER_SUB}; font-family:system-ui;'>"
                f"<span style='color:{color}; font-weight:700; width:16px; display:inline-block;'>{icon}</span> "
                f"<span style='background:{theme.SURFACE_HOV}; color:{theme.CYAN}; border-radius:4px; padding:1px 5px; font-size:10px; font-weight:700;'>{lang}</span> "
                f"<span style='color:{theme.FOREGROUND}; font-size:12px;'>{detail}</span> "
                f"<span style='color:{theme.PLACEHOLDER}; font-size:11px; float:right;'>{stamp}</span>"
                f"</div>"
            )

        self.recent_view.setHtml("".join(rows))
