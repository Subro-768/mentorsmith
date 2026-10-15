"""Database operations: migrations, lesson progress, attempts, activity, settings."""

from __future__ import annotations

from pathlib import Path

from mentorsmith.core.db import LATEST_SCHEMA_VERSION, Database


# ----------------------------------------------------------------------
# Schema and migrations
# ----------------------------------------------------------------------
def test_schema_is_created_on_connect(database: Database) -> None:
    assert database.schema_version() == LATEST_SCHEMA_VERSION


def test_migrations_are_idempotent(database: Database) -> None:
    """Connecting repeatedly must not re-apply or break anything."""
    for _ in range(3):
        database.connect()
    assert database.schema_version() == LATEST_SCHEMA_VERSION
    assert database.get_setting("nothing", "fallback") == "fallback"


def test_migrate_creates_all_expected_tables(database: Database) -> None:
    rows = database.connect().execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    names = {row["name"] for row in rows}
    assert {
        "activity",
        "app_settings",
        "exercise_attempts",
        "lesson_progress",
    } <= names


def test_progress_survives_reopening_a_file(temp_db_path: Path) -> None:
    """The persistence guarantee the UI relies on."""
    with Database(temp_db_path) as db:
        db.mark_lesson_complete("01-program-structure")
        db.record_exercise_attempt("01-program-structure", "ex1", compiled_ok=True, ran_ok=True)

    with Database(temp_db_path) as reopened:
        assert reopened.is_lesson_complete("01-program-structure")
        assert reopened.exercise_attempts("01-program-structure")


# ----------------------------------------------------------------------
# Lesson progress
# ----------------------------------------------------------------------
def test_mark_lesson_complete_is_recorded(database: Database) -> None:
    stamp = database.mark_lesson_complete("03-input-output")
    assert stamp
    assert database.is_lesson_complete("03-input-output")


def test_marking_complete_twice_keeps_the_first_timestamp(database: Database) -> None:
    first = database.mark_lesson_complete("03-input-output")
    second = database.mark_lesson_complete("03-input-output")
    assert first == second


def test_unmark_removes_completion(database: Database) -> None:
    database.mark_lesson_complete("03-input-output")
    database.unmark_lesson_complete("03-input-output")
    assert not database.is_lesson_complete("03-input-output")


def test_completed_lessons_lists_all(database: Database) -> None:
    database.mark_lesson_complete("a")
    database.mark_lesson_complete("b")
    assert set(database.completed_lessons()) == {"a", "b"}


def test_is_lesson_complete_is_false_for_unknown(database: Database) -> None:
    assert not database.is_lesson_complete("never-seen")


# ----------------------------------------------------------------------
# Exercise attempts
# ----------------------------------------------------------------------
def test_record_attempt_returns_id_and_stores_fields(database: Database) -> None:
    attempt_id = database.record_exercise_attempt(
        "05-conditions",
        "ex-1",
        source="int main(){}",
        compiled_ok=True,
        ran_ok=False,
        result="exit 1",
    )
    assert attempt_id > 0
    attempts = database.exercise_attempts("05-conditions", "ex-1")
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt["source"] == "int main(){}"
    assert attempt["compiled_ok"] == 1
    assert attempt["ran_ok"] == 0
    assert attempt["result"] == "exit 1"
    assert attempt["created_at"]


def test_attempts_are_ordered_newest_first(database: Database) -> None:
    database.record_exercise_attempt("l", "e", result="first")
    database.record_exercise_attempt("l", "e", result="second")
    database.record_exercise_attempt("l", "e", result="third")
    assert [a["result"] for a in database.exercise_attempts("l", "e")] == [
        "third",
        "second",
        "first",
    ]


def test_attempts_are_filtered_by_exercise(database: Database) -> None:
    database.record_exercise_attempt("l", "ex-a", result="a")
    database.record_exercise_attempt("l", "ex-b", result="b")
    assert database.attempt_count("l", "ex-a") == 1
    assert len(database.exercise_attempts("l")) == 2


def test_latest_attempt_returns_the_newest(database: Database) -> None:
    database.record_exercise_attempt("l", "e", result="old")
    database.record_exercise_attempt("l", "e", result="new")
    assert database.latest_attempt("l", "e")["result"] == "new"


def test_latest_attempt_is_none_when_empty(database: Database) -> None:
    assert database.latest_attempt("missing", "missing") is None


def test_attempts_from_other_lessons_are_not_counted(database: Database) -> None:
    database.record_exercise_attempt("lesson-one", "e")
    database.record_exercise_attempt("lesson-two", "e")
    assert database.attempt_count("lesson-one", "e") == 1


# ----------------------------------------------------------------------
# Activity feed
# ----------------------------------------------------------------------
def test_activity_is_returned_newest_first(database: Database) -> None:
    database.record_activity("exercise_attempt", "l", "first")
    database.record_activity("lesson_complete", "l", "second")
    entries = database.recent_activity(10)
    assert [e["detail"] for e in entries] == ["second", "first"]


def test_recent_activity_respects_limit(database: Database) -> None:
    for index in range(5):
        database.record_activity("exercise_attempt", "l", f"entry-{index}")
    assert len(database.recent_activity(3)) == 3


def test_clear_activity(database: Database) -> None:
    database.record_activity("exercise_attempt", "l", "x")
    database.clear_activity()
    assert database.recent_activity(10) == []


# ----------------------------------------------------------------------
# Settings
# ----------------------------------------------------------------------
def test_setting_round_trip(database: Database) -> None:
    database.set_setting("assistance_level", "guided")
    assert database.get_setting("assistance_level") == "guided"


def test_setting_upsert_overwrites(database: Database) -> None:
    database.set_setting("assistance_level", "hint")
    database.set_setting("assistance_level", "full")
    assert database.get_setting("assistance_level") == "full"
    assert database.all_settings() == {"assistance_level": "full"}


def test_missing_setting_returns_default(database: Database) -> None:
    assert database.get_setting("absent", "default") == "default"


# ----------------------------------------------------------------------
# Aggregates
# ----------------------------------------------------------------------
def test_lesson_stats_reports_completion_and_attempts(database: Database) -> None:
    database.mark_lesson_complete("done")
    database.record_exercise_attempt("done", "e")
    database.record_exercise_attempt("done", "e")
    database.record_exercise_attempt("todo", "e")

    stats = database.lesson_stats(["done", "todo", "untouched"])
    assert stats["done"] == {"completed": True, "attempts": 2}
    assert stats["todo"] == {"completed": False, "attempts": 1}
    assert stats["untouched"] == {"completed": False, "attempts": 0}


def test_lesson_stats_with_no_ids(database: Database) -> None:
    assert database.lesson_stats([]) == {}