"""Schema v4: the language dimension finished, and review persistence.

Phase 4 added ``language`` to ``lesson_progress`` and ``exercise_attempts`` but
missed four other tables. That was a real bug — a review flagged for C++
pointers was indistinguishable from a C pointer review, and project progress and
the activity feed leaked across tracks. These tests exist so it cannot come back.

They also cover a second gap: reviews were computed and shown for two phases
running, but nothing ever wrote them, so the ``reviews`` table stayed empty and
``close_review`` had nothing to act on.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from mentorsmith.core import curriculum_registry as registry
from mentorsmith.core.db import MIGRATIONS, Database, LATEST_SCHEMA_VERSION
from mentorsmith.services.insights import build_report


@pytest.fixture()
def v3_database(tmp_path: Path, monkeypatch) -> tuple[str, Database]:
    """A genuine schema-v3 database built by hand, then migrated in place."""
    path = str(tmp_path / "v3.db")

    saved = MIGRATIONS[4]
    del MIGRATIONS[4]
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    for version in (1, 2, 3):
        for statement in MIGRATIONS[version]:
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {version}")
    MIGRATIONS[4] = saved

    conn.execute(
        "INSERT INTO lesson_progress (lesson_id, language, completed_at) "
        "VALUES ('01-program-structure', 'cpp', '2026-01-01T00:00:00+00:00')"
    )
    conn.execute(
        "INSERT INTO exercise_attempts "
        "(lesson_id, exercise_id, language, source, compiled_ok, ran_ok, result, created_at) "
        "VALUES ('01', 'e1', 'cpp', 'int main(){}', 1, 1, 'ok', '2026-01-01T00:00:01+00:00')"
    )
    conn.execute(
        "INSERT INTO reviews (concept_id, reason, evidence, status, created_at) "
        "VALUES ('program-structure', 'weak', '', 'open', '2026-01-01T00:00:02+00:00')"
    )
    conn.execute(
        "INSERT INTO projects "
        "(id, title, purpose, concepts, difficulty, status, created_at, updated_at) "
        "VALUES ('p1', 'Calculator', '', 'variables', 'beginner', 'not_started', "
        "'2026-01-01', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO project_milestones "
        "(project_id, ordinal, title, requirements, acceptance_criteria, hint, status) "
        "VALUES ('p1', 1, 'Read input', 'use cin', 'it compiles', '', 'pending')"
    )
    conn.execute(
        "INSERT INTO concept_progress (concept_id, label, score, evidence, updated_at) "
        "VALUES ('program-structure', 'strong', 0.9, '', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO activity (kind, lesson_id, detail, created_at) "
        "VALUES ('lesson_complete', '01', 'done', '2026-01-01')"
    )
    conn.execute(
        "INSERT INTO project_activity "
        "(project_id, milestone_id, notes, needed_substantial_help, created_at) "
        "VALUES ('p1', 1, 'tried it', 0, '2026-01-01')"
    )
    conn.commit()
    conn.close()

    return path, Database(path)


class TestMigration4:
    def test_the_v3_database_reaches_the_latest_version(self, v3_database) -> None:
        """Migration 4 is applied, and the database ends at the latest.

        Written against LATEST_SCHEMA_VERSION rather than a fixed number:
        a schema version is a moving target, and a test that pins it only
        ever reports that somebody added a migration.
        """
        _path, database = v3_database
        assert LATEST_SCHEMA_VERSION >= 4
        assert database.schema_version() == LATEST_SCHEMA_VERSION

    @pytest.mark.parametrize(
        "table", ["reviews", "projects", "project_milestones",
                  "concept_progress", "activity", "project_activity"]
    )
    def test_every_track_scoped_table_has_language(self, v3_database, table) -> None:
        _path, database = v3_database
        columns = {
            row["name"] for row in
            database.connect().execute(f"PRAGMA table_info({table})")
        }
        assert "language" in columns, f"{table} is not scoped by language"

    def test_pre_existing_rows_survive(self, v3_database) -> None:
        _path, database = v3_database
        assert database.completed_lessons("cpp") == ["01-program-structure"]
        assert database.open_reviews("cpp")[0]["concept_id"] == "program-structure"
        assert [p["id"] for p in database.list_projects("cpp")] == ["p1"]
        assert database.milestones_for("p1", "cpp")[0]["title"] == "Read input"
        assert database.get_concept_progress("program-structure", "cpp")["label"] == "strong"
        assert len(database.recent_activity(10, "cpp")) == 1

    def test_old_rows_are_labelled_cpp(self, v3_database) -> None:
        """C++ was the only track before Phase 4, so that is the correct label."""
        _path, database = v3_database
        assert database.open_reviews("cpp")[0]["language"] == "cpp"
        assert database.list_projects("cpp")[0]["language"] == "cpp"

    def test_earlier_data_still_migrates_in_one_step(self, tmp_path: Path) -> None:
        """A schema-1 database reaches the latest without a manual upgrade."""
        path = str(tmp_path / "v1.db")
        saved = dict(MIGRATIONS)
        for version in list(MIGRATIONS):
            if version != 1:
                del MIGRATIONS[version]
        conn = sqlite3.connect(path)
        for statement in MIGRATIONS[1]:
            conn.execute(statement)
        conn.execute("PRAGMA user_version = 1")
        conn.execute(
            "INSERT INTO lesson_progress (lesson_id, completed_at) "
            "VALUES ('01-program-structure', '2026-01-01T00:00:00+00:00')"
        )
        conn.commit()
        conn.close()
        MIGRATIONS.clear()
        MIGRATIONS.update(saved)

        database = Database(path)
        database.connect()
        assert database.schema_version() == LATEST_SCHEMA_VERSION
        assert database.completed_lessons("cpp") == ["01-program-structure"]


class TestLanguageIsolation:
    @pytest.fixture()
    def database(self, tmp_path: Path) -> Database:
        db = Database(str(tmp_path / "iso.db"))
        db.connect()
        yield db
        db.close()

    def test_reviews_do_not_leak(self, database: Database) -> None:
        database.add_review("pointers", "cpp reason", "", "cpp")
        assert len(database.open_reviews("cpp")) == 1
        assert database.open_reviews("python") == []
        assert database.reviews_for("pointers", "python") == []

    def test_the_same_concept_id_can_be_reviewed_twice(self, database) -> None:
        first = database.add_review("pointers", "cpp reason", "", "cpp")
        second = database.add_review("pointers", "python reason", "", "python")
        assert first != second
        assert database.open_reviews("cpp")[0]["reason"] == "cpp reason"
        assert database.open_reviews("python")[0]["reason"] == "python reason"

    def test_reviews_deduplicate_within_a_language(self, database) -> None:
        first = database.add_review("pointers", "one", "", "cpp")
        second = database.add_review("pointers", "two", "", "cpp")
        assert first == second
        assert len(database.open_reviews("cpp")) == 1

    def test_the_concept_progress_cache_is_per_language(self, database) -> None:
        database.set_concept_progress("pointers", "strong", 0.9, "", "cpp")
        assert database.get_concept_progress("pointers", "cpp")["label"] == "strong"
        assert database.get_concept_progress("pointers", "python") is None
        database.set_concept_progress("pointers", "needs_review", 0.2, "", "python")
        assert database.get_concept_progress("pointers", "cpp")["label"] == "strong"
        assert database.get_concept_progress("pointers", "python")["label"] == "needs_review"

    def test_all_concept_progress_is_per_language(self, database) -> None:
        database.set_concept_progress("a", "strong", 0.9, "", "cpp")
        database.set_concept_progress("b", "strong", 0.9, "", "python")
        assert set(database.all_concept_progress("cpp")) == {"a"}
        assert set(database.all_concept_progress("python")) == {"b"}

    def test_activity_does_not_leak(self, database) -> None:
        database.record_activity("lesson_complete", "01", "done", "cpp")
        assert len(database.recent_activity(10, "cpp")) == 1
        assert database.recent_activity(10, "python") == []

    def test_clearing_activity_only_clears_one_language(self, database) -> None:
        database.record_activity("k", "01", "d", "cpp")
        database.record_activity("k", "01", "d", "python")
        database.clear_activity("cpp")
        assert database.recent_activity(10, "cpp") == []
        assert len(database.recent_activity(10, "python")) == 1

    def test_projects_do_not_leak(self, database) -> None:
        database.create_project("shared-id", "C++ project", language="cpp")
        database.create_project("shared-id", "Python project", language="python")
        assert database.get_project("shared-id", "cpp")["title"] == "C++ project"
        assert database.get_project("shared-id", "python")["title"] == "Python project"

    def test_milestones_do_not_leak(self, database) -> None:
        database.create_project(
            "p", "T", milestones=[{"title": "cpp step"}], language="cpp"
        )
        database.create_project(
            "p", "T", milestones=[{"title": "python step"}], language="python"
        )
        assert database.milestones_for("p", "cpp")[0]["title"] == "cpp step"
        assert database.milestones_for("p", "python")[0]["title"] == "python step"

    def test_regenerating_milestones_does_not_touch_the_other_language(self, database) -> None:
        database.create_project("p", "T", milestones=[{"title": "v1"}], language="cpp")
        database.create_project("p", "T", milestones=[{"title": "v1"}], language="python")
        database.create_project("p", "T", milestones=[{"title": "v2"}], language="cpp")
        assert database.milestones_for("p", "cpp")[0]["title"] == "v2"
        assert database.milestones_for("p", "python")[0]["title"] == "v1"

    def test_project_status_is_per_language(self, database) -> None:
        database.create_project("p", "T", language="cpp")
        database.create_project("p", "T", language="python")
        database.set_project_status("p", "in_progress", "cpp")
        assert database.get_project("p", "cpp")["status"] == "in_progress"
        assert database.get_project("p", "python")["status"] == "not_started"


@pytest.fixture(scope="module")
def cpp_track():
    """The C++ track. Module scope: loading it parses 16 lesson files."""
    return registry.load_track("cpp")


class TestReviewsArePersisted:
    """Reviews were shown for two phases but never written."""

    @pytest.fixture()
    def database(self, tmp_path: Path) -> Database:
        db = Database(str(tmp_path / "rev.db"))
        db.connect()
        yield db
        db.close()

    def _weaken(self, database: Database, concept: str) -> None:
        """Record attempts bad enough to trigger a review recommendation."""
        for index in range(2):
            database.record_exercise_attempt(
                "01-program-structure", f"e{index}",
                concept_id=concept, language="cpp",
                correct=False, hints_used=2, error_category="missing_semicolon",
            )

    def test_a_recommended_review_reaches_the_table(self, database, cpp_track) -> None:
        self._weaken(database, "program-structure")
        report = build_report(database, cpp_track.model, cpp_track.bank, language="cpp")
        assert report.reviews, "expected at least one review"
        assert len(database.open_reviews("cpp")) == len(report.reviews)

    def test_the_stored_review_carries_its_reason(self, database, cpp_track) -> None:
        self._weaken(database, "program-structure")
        build_report(database, cpp_track.model, cpp_track.bank, language="cpp")
        row = database.open_reviews("cpp")[0]
        assert row["concept_id"] == "program-structure"
        assert "missing_semicolon" in row["reason"] + row["evidence"]

    def test_rebuilding_does_not_duplicate(self, database, cpp_track) -> None:
        self._weaken(database, "program-structure")
        for _ in range(3):
            build_report(database, cpp_track.model, cpp_track.bank, language="cpp")
        assert len(database.open_reviews("cpp")) == 1

    def test_closing_a_review_sticks(self, database, cpp_track) -> None:
        self._weaken(database, "program-structure")
        build_report(database, cpp_track.model, cpp_track.bank, language="cpp")
        review_id = database.open_reviews("cpp")[0]["id"]
        database.close_review(review_id)
        assert database.open_reviews("cpp") == []

    def test_reviews_do_not_appear_in_another_language(self, database, cpp_track) -> None:
        self._weaken(database, "program-structure")
        build_report(database, cpp_track.model, cpp_track.bank, language="cpp")
        assert database.open_reviews("python") == []