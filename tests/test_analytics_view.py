"""Tests for the analytics dashboard.

The dashboard had no tests at all, which is why three separate defects in it
went unnoticed:

* the XP comment said 10 per lesson while the line below it awarded 20;
* the progress bar started at 10%, a fabricated value;
* at the top level the footer read "12000 XP (Next level at 10000 XP)" -
  naming a threshold the learner had already passed, because the top level
  invented a threshold of ``top * 2``.

These tests drive the real widget against a real database rather than mocking
the queries out, so the numbers on screen are the numbers asserted on.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from mentorsmith.core.db import Database  # noqa: E402
from mentorsmith.ui import analytics_view as av  # noqa: E402
from mentorsmith.ui.analytics_view import AnalyticsView  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture()
def db(tmp_path):
    database = Database(tmp_path / "analytics.db")
    database.connect()
    yield database
    database.close()


@pytest.fixture()
def view(db, qapp):
    widget = AnalyticsView(db)
    yield widget
    widget.deleteLater()


def seed_lesson(db, lesson_id: str, language: str = "python", days_ago: int = 0) -> None:
    stamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
    db.connect().execute(
        "INSERT OR REPLACE INTO lesson_progress (lesson_id, language, completed_at)"
        " VALUES (?, ?, ?)",
        (lesson_id, language, stamp),
    )


def seed_attempt(
    db,
    exercise_id: str = "e1",
    language: str = "python",
    compiled_ok: bool = True,
    ran_ok: bool = True,
    days_ago: int = 0,
) -> None:
    stamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
    db.connect().execute(
        "INSERT INTO exercise_attempts"
        " (lesson_id, exercise_id, source, compiled_ok, ran_ok, result,"
        "  created_at, language)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("01-basics", exercise_id, "ui", int(compiled_ok), int(ran_ok),
         "ok" if ran_ok else "error", stamp, language),
    )


def seed_activity(
    db, kind: str = "lesson_complete", detail: str = "x",
    language: str = "python", days_ago: int = 0,
) -> None:
    stamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
    db.connect().execute(
        "INSERT INTO activity (kind, detail, created_at, language)"
        " VALUES (?, ?, ?, ?)",
        (kind, detail, stamp, language),
    )


# ======================================================================
# The XP rates
# ======================================================================
class TestXpRates:
    def test_the_rates_are_named_constants(self) -> None:
        """The formula and its description must not be able to drift apart."""
        assert av.XP_PER_LESSON == 20
        assert av.XP_PER_SUCCESS == 5
        assert av.XP_PER_ATTEMPT == 2

    def test_xp_matches_the_named_rates(self, db, view) -> None:
        seed_lesson(db, "01-a")
        seed_lesson(db, "02-b")
        seed_attempt(db, "e1", ran_ok=True)
        seed_attempt(db, "e2", ran_ok=False)
        view.refresh()
        expected = 2 * av.XP_PER_LESSON + 1 * av.XP_PER_SUCCESS + 2 * av.XP_PER_ATTEMPT
        assert f"{expected} XP" in view.xp_details.text()

    def test_a_failed_attempt_still_earns_the_attempt_xp(self, db, view) -> None:
        """The rate is per attempt, not per success - both are awarded."""
        seed_attempt(db, "e1", compiled_ok=False, ran_ok=False)
        view.refresh()
        assert f"{av.XP_PER_ATTEMPT} XP" in view.xp_details.text()


# ======================================================================
# The fabricated initial progress value
# ======================================================================
class TestNoFabricatedProgress:
    def test_the_bar_does_not_start_at_a_plausible_number(self, view) -> None:
        """Before refresh() there is no data, so the bar must read zero.

        It used to be seeded with 10, which is invisible in normal use because
        refresh() always overwrites it - and therefore survives every test that
        does not check.
        """
        assert view.xp_bar.value() == 0

    def test_a_fresh_account_shows_zero_everywhere(self, db, view) -> None:
        view.refresh()
        assert view.xp_bar.value() == 0
        assert view.card_lessons.val_lbl.text() == "0"
        assert view.card_attempts.val_lbl.text() == "0"
        assert view.card_accuracy.val_lbl.text() == "0%"
        assert view.card_streak.val_lbl.text() == "0 Days"

    def test_refresh_overwrites_the_initial_value(self, db, view) -> None:
        seed_lesson(db, "01-a", days_ago=0)
        seed_lesson(db, "02-b", days_ago=1)
        seed_attempt(db, "e1", ran_ok=True)
        view.refresh()
        assert view.xp_bar.value() != 0, "the placeholder was never replaced"


# ======================================================================
# The top level must not invent a threshold
# ======================================================================
class TestTopLevel:
    TOP = av.XP_PER_LESSON * 400  # comfortably past the 5000 XP cap

    def test_next_threshold_is_none_at_the_top(self, view) -> None:
        _level, _name, _pct, nxt = view._calculate_level(self.TOP)
        assert nxt is None, "there is no level above Master"

    def test_the_bar_is_full_at_the_top(self, view) -> None:
        _level, _name, pct, _nxt = view._calculate_level(self.TOP)
        assert pct == 100

    def test_the_footer_does_not_name_a_passed_threshold(self, db, view) -> None:
        """The defect: "12000 XP (Next level at 10000 XP)"."""
        conn = db.connect()
        for i in range(250):
            seed_lesson(db, f"lesson-{i}")
        del conn
        view.refresh()

        text = view.xp_details.text()
        assert "Top level reached" in text
        assert "Next level at" not in text

    def test_a_learner_past_the_top_is_never_told_to_reach_it(self, db, view) -> None:
        for i in range(250):
            seed_lesson(db, f"lesson-{i}")
        view.refresh()
        xp_shown = int(view.xp_details.text().split()[0])
        assert xp_shown >= 5000, "fixture should exceed the top threshold"
        assert "Next level at" not in view.xp_details.text()

    def test_mid_level_still_reports_the_next_threshold(self, view) -> None:
        _level, _name, _pct, nxt = view._calculate_level(250)
        assert nxt == 500


# ======================================================================
# Level thresholds
# ======================================================================
class TestLevelThresholds:
    @pytest.mark.parametrize(
        "xp, level, name",
        [
            (0, 1, "Novice"),
            (99, 1, "Novice"),
            (100, 2, "Apprentice"),
            (249, 2, "Apprentice"),
            (250, 3, "Coder"),
            (500, 4, "Developer"),
            (1000, 5, "Engineer"),
            (2000, 6, "Architect"),
            (5000, 7, "Master"),
        ],
    )
    def test_thresholds(self, view, xp, level, name) -> None:
        got_level, got_name, _pct, _nxt = view._calculate_level(xp)
        assert (got_level, got_name) == (level, name)

    def test_exactly_on_a_threshold_is_the_start_of_that_level(self, view) -> None:
        """250 XP means you just became a Coder, at 0% through it."""
        _level, _name, pct, _nxt = view._calculate_level(250)
        assert pct == 0

    def test_just_below_the_top_is_not_the_top(self, view) -> None:
        level, _name, _pct, nxt = view._calculate_level(4999)
        assert level == 6
        assert nxt == 5000

    @pytest.mark.parametrize("xp", range(0, 6000, 137))
    def test_the_bar_is_always_a_percentage(self, view, xp) -> None:
        _level, _name, pct, _nxt = view._calculate_level(xp)
        assert 0 <= pct <= 100


# ======================================================================
# The counters
# ======================================================================
class TestCounters:
    def test_accuracy_is_a_percentage(self, db, view) -> None:
        seed_attempt(db, "e1", ran_ok=True)
        seed_attempt(db, "e2", ran_ok=False)
        view.refresh()
        assert view.card_accuracy.val_lbl.text() == "50%"

    def test_all_attempts_passing_is_100_percent(self, db, view) -> None:
        for i in range(3):
            seed_attempt(db, f"e{i}", ran_ok=True)
        view.refresh()
        assert view.card_accuracy.val_lbl.text() == "100%"

    def test_no_attempts_is_zero_percent_not_a_division_error(self, db, view) -> None:
        view.refresh()
        assert view.card_accuracy.val_lbl.text() == "0%"

    def test_compiling_but_not_running_is_not_a_success(self, db, view) -> None:
        """ran_ok is what decides success, not compiled_ok alone."""
        seed_attempt(db, "e1", compiled_ok=True, ran_ok=False)
        view.refresh()
        assert view.card_accuracy.val_lbl.text() == "0%"

    def test_completed_lessons_are_counted(self, db, view) -> None:
        seed_lesson(db, "01-a")
        seed_lesson(db, "02-b")
        seed_lesson(db, "03-c")
        view.refresh()
        assert view.card_lessons.val_lbl.text() == "3"

    def test_the_same_lesson_in_two_languages_counts_twice(self, db, view) -> None:
        """lesson_progress is keyed (lesson_id, language) precisely so that two
        tracks may share a lesson id without colliding."""
        seed_lesson(db, "05-conditions", "python")
        seed_lesson(db, "05-conditions", "javascript")
        view.refresh()
        assert view.card_lessons.val_lbl.text() == "2"

    def test_recompleting_a_lesson_does_not_inflate_the_count(self, db, view) -> None:
        """INSERT OR REPLACE against the composite key must stay at one row."""
        for _ in range(5):
            seed_lesson(db, "01-a", "python")
        view.refresh()
        assert view.card_lessons.val_lbl.text() == "1"


# ======================================================================
# Streak
# ======================================================================
class TestStreak:
    def test_no_activity_is_no_streak(self, view) -> None:
        assert view._calculate_streak(set()) == 0

    def test_activity_today_counts(self, view) -> None:
        assert view._calculate_streak({date.today().isoformat()}) == 1

    def test_a_streak_survives_a_day_off_today(self, view) -> None:
        """Yesterday but not today: still a streak, just not extended."""
        dates = {
            (date.today() - timedelta(days=n)).isoformat()
            for n in (1, 2, 3)
        }
        assert view._calculate_streak(dates) == 3

    def test_a_two_day_gap_breaks_the_streak(self, view) -> None:
        dates = {
            (date.today() - timedelta(days=n)).isoformat()
            for n in (1, 2, 5, 6)
        }
        assert view._calculate_streak(dates) == 2

    def test_activity_only_in_the_past_is_no_streak(self, view) -> None:
        dates = {
            (date.today() - timedelta(days=n)).isoformat()
            for n in (5, 6, 7)
        }
        assert view._calculate_streak(dates) == 0

    def test_the_display_pluralises(self, db, view) -> None:
        seed_activity(db, "lesson_complete", "a", days_ago=0)
        view.refresh()
        assert view.card_streak.val_lbl.text() == "1 Day"

    def test_the_streak_is_derived_from_the_activity_log(self, db, view) -> None:
        """Not from exercise_attempts.

        Worth pinning down explicitly: running an exercise does not by itself
        extend the streak, only a logged activity does. That is a deliberate
        reading of "consecutive daily learning", but it is easy to assume
        otherwise when reading the card.
        """
        seed_attempt(db, "e1", days_ago=0)
        view.refresh()
        assert view.card_streak.val_lbl.text() == "0 Days"


# ======================================================================
# The dashboard is global, and says so
# ======================================================================
class TestGlobalScope:
    def test_it_sums_across_every_language(self, db, view) -> None:
        seed_lesson(db, "01-a", "python")
        seed_lesson(db, "01-b", "javascript")
        seed_lesson(db, "01-c", "cpp")
        view.refresh()
        assert view.card_lessons.val_lbl.text() == "3"

    def test_it_shows_a_card_per_track(self, db, view) -> None:
        view.refresh()
        assert view.lang_grid.count() > 0

    def test_refreshing_twice_does_not_stack_cards(self, db, view) -> None:
        view.refresh()
        first = view.lang_grid.count()
        view.refresh()
        assert view.lang_grid.count() == first

    def test_the_heatmap_renders(self, db, view) -> None:
        seed_attempt(db, "e1", days_ago=0)
        view.refresh()
        assert view.heatmap_view.toPlainText().strip(), "empty heatmap"

    def test_recent_activity_renders(self, db, view) -> None:
        seed_lesson(db, "01-a", days_ago=0)
        view.refresh()
        assert view.recent_view.toPlainText().strip(), "empty timeline"

    def test_the_heatmap_heading_matches_the_window_it_draws(self, view) -> None:
        """It said "LAST 90 DAYS" while rendering 90-96 days of whole weeks."""
        from PyQt6.QtWidgets import QLabel

        labels = [
            w.text() for w in view.findChildren(QLabel)
            if "HEATMAP" in w.text()
        ]
        assert labels, "no heatmap heading found"
        assert "90 DAYS" not in labels[0]


# ======================================================================
# Escaping
# ======================================================================
class TestEscaping:
    def test_activity_detail_is_escaped(self, db, view) -> None:
        """Activity detail is free text in the database and goes into HTML.

        Asserted on ``toHtml()``, not ``toPlainText()``: the plain-text view
        decodes entities, so it correctly *shows* the string "<script>" as
        visible text. What matters is that the widget never received it as
        markup, which is only visible in the HTML form.
        """
        seed_activity(db, "note", "<script>alert(1)</script>")
        view.refresh()

        rendered = view.recent_view.toHtml()
        assert "<script>" not in rendered.lower(), "raw markup reached the widget"
        assert "&lt;script&gt;" in rendered or "script" in view.recent_view.toPlainText()

    def test_the_language_tag_is_escaped(self, db, view) -> None:
        seed_activity(db, "note", "x", language="<img src=x>")
        view.refresh()
        assert "<img" not in view.recent_view.toHtml().lower()

    def test_a_note_containing_quotes_still_renders(self, db, view) -> None:
        """The rows are built with single-quoted style attributes, so a detail
        containing an apostrophe must not be able to break out of one."""
        seed_activity(db, "note", "it's <b>fine</b> & ok")
        view.refresh()
        assert "it's <b>fine</b> & ok" in view.recent_view.toPlainText()
        assert "<b>fine</b>" not in view.recent_view.toHtml()