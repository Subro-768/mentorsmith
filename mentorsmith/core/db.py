"""SQLite persistence for lesson progress, exercise attempts and activity.

This module is the only place that talks to SQLite. The UI never opens a
connection itself, which keeps persistence testable in isolation and keeps
schema changes in one file.

Schema changes are applied through the ordered :data:`MIGRATIONS` table. Each
entry is ``{version: [SQL statements]}`` and they are applied in ascending
order, so upgrading an existing database is the same code path as creating a
fresh one.

API keys are never stored here — see :mod:`mentorsmith.config`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Bump when adding a migration. Never edit an already-released entry.
MIGRATIONS: dict[int, list[str]] = {
    1: [
        """
        CREATE TABLE IF NOT EXISTS lesson_progress (
            lesson_id     TEXT PRIMARY KEY,
            completed_at  TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS exercise_attempts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id     TEXT NOT NULL,
            exercise_id   TEXT NOT NULL,
            source        TEXT NOT NULL DEFAULT '',
            compiled_ok   INTEGER NOT NULL DEFAULT 0,
            ran_ok        INTEGER NOT NULL DEFAULT 0,
            result        TEXT NOT NULL DEFAULT '',
            created_at    TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_attempts_lesson
            ON exercise_attempts (lesson_id, exercise_id, id)
        """,
        """
        CREATE TABLE IF NOT EXISTS activity (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            kind        TEXT NOT NULL,
            lesson_id   TEXT,
            detail      TEXT NOT NULL DEFAULT '',
            created_at  TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_activity_created
            ON activity (created_at DESC)
        """,
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            key    TEXT PRIMARY KEY,
            value  TEXT NOT NULL
        )
        """,
    ],
    2: [
        # --- Phase 2: adaptive learning ---------------------------------
        # Additive only. Every column has a default so existing Phase 1 rows
        # keep their data and the table can be migrated in place.
        """
        ALTER TABLE exercise_attempts ADD COLUMN exercise_type TEXT NOT NULL DEFAULT 'freeform'
        """,
        """
        ALTER TABLE exercise_attempts ADD COLUMN concept_id TEXT NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE exercise_attempts ADD COLUMN correct INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE exercise_attempts ADD COLUMN hints_used INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE exercise_attempts ADD COLUMN independent INTEGER NOT NULL DEFAULT 1
        """,
        """
        ALTER TABLE exercise_attempts ADD COLUMN error_category TEXT NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE exercise_attempts ADD COLUMN grade TEXT NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE exercise_attempts ADD COLUMN novelty INTEGER NOT NULL DEFAULT 0
        """,
        """
        ALTER TABLE exercise_attempts ADD COLUMN graded_by TEXT NOT NULL DEFAULT 'deterministic'
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_attempts_concept
            ON exercise_attempts (concept_id, exercise_type)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_attempts_error_category
            ON exercise_attempts (error_category)
        """,
        # Cached mastery label per concept, so the dashboard does not have to
        # recompute for every row. Always recomputable from exercise_attempts.
        """
        CREATE TABLE IF NOT EXISTS concept_progress (
            concept_id   TEXT PRIMARY KEY,
            label        TEXT NOT NULL,
            score        REAL NOT NULL DEFAULT 0.0,
            evidence     TEXT NOT NULL DEFAULT '',
            updated_at   TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id           TEXT PRIMARY KEY,
            title        TEXT NOT NULL,
            purpose      TEXT NOT NULL DEFAULT '',
            concepts     TEXT NOT NULL DEFAULT '',
            difficulty   TEXT NOT NULL DEFAULT 'unknown',
            status       TEXT NOT NULL DEFAULT 'not_started',
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS project_milestones (
            id                   INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id           TEXT NOT NULL,
            ordinal              INTEGER NOT NULL,
            title                TEXT NOT NULL,
            requirements         TEXT NOT NULL DEFAULT '',
            acceptance_criteria  TEXT NOT NULL DEFAULT '',
            hint                 TEXT NOT NULL DEFAULT '',
            status               TEXT NOT NULL DEFAULT 'pending',
            completed_at         TEXT
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_milestones_project
            ON project_milestones (project_id, ordinal)
        """,
        """
        CREATE TABLE IF NOT EXISTS project_activity (
            id                        INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id                TEXT NOT NULL,
            milestone_id              INTEGER,
            notes                     TEXT NOT NULL DEFAULT '',
            needed_substantial_help   INTEGER NOT NULL DEFAULT 0,
            created_at                TEXT NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            concept_id  TEXT NOT NULL,
            reason      TEXT NOT NULL,
            evidence    TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'open',
            created_at  TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_reviews_status
            ON reviews (status, concept_id)
        """,
    ],
    3: [
        # --- Phase 4: multiple language tracks -------------------------
        # Concept and lesson ids may now repeat across languages, so every
        # progress row is scoped by language.
        """
        ALTER TABLE exercise_attempts ADD COLUMN language TEXT NOT NULL DEFAULT 'cpp'
        """,
        """
        ALTER TABLE lesson_progress ADD COLUMN language TEXT NOT NULL DEFAULT 'cpp'
        """,
        # lesson_progress is keyed by lesson_id alone, which would collide
        # once two languages can both have "05-conditions". SQLite cannot add
        # a column to a primary key, so the table is rebuilt: copy, drop,
        # rename. Every existing row is preserved with language='cpp'.
        """
        CREATE TABLE lesson_progress_v3 (
            lesson_id     TEXT NOT NULL,
            language      TEXT NOT NULL DEFAULT 'cpp',
            completed_at  TEXT NOT NULL,
            PRIMARY KEY (lesson_id, language)
        )
        """,
        """
        INSERT INTO lesson_progress_v3 (lesson_id, language, completed_at)
            SELECT lesson_id, language, completed_at FROM lesson_progress
        """,
        """
        DROP TABLE lesson_progress
        """,
        """
        ALTER TABLE lesson_progress_v3 RENAME TO lesson_progress
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_attempts_language_concept
            ON exercise_attempts (language, concept_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_attempts_language_lesson
            ON exercise_attempts (language, lesson_id)
        """,
    ],
    5: [
        # --- Exam preparation attempts -----------------------------------
        # A student's answer to a question from their own papers. Kept
        # separate from `exercise_attempts`, which belongs to the coding
        # curriculum: an exam question has no concept, no exercise type and
        # no grader, and forcing it into that table would have invented
        # fields that mean something else.
        """
        CREATE TABLE IF NOT EXISTS exam_attempts (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id   TEXT NOT NULL,
            course_id     TEXT NOT NULL,
            session_id    TEXT NOT NULL DEFAULT '',
            chosen_answer TEXT NOT NULL DEFAULT '',
            correct       INTEGER,          -- NULL when there is no key to grade against
            topic_ids     TEXT NOT NULL DEFAULT '',
            unit          INTEGER NOT NULL DEFAULT 0,
            seconds_taken INTEGER NOT NULL DEFAULT 0,
            created_at    TEXT NOT NULL
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_exam_attempts_question
            ON exam_attempts (course_id, question_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_exam_attempts_session
            ON exam_attempts (session_id)
        """,
    ],
    4: [
        # --- Phase 5 audit: finish the language dimension ----------------
        # Phase 4 added `language` to lesson_progress and exercise_attempts but
        # missed four other tables. That was a real bug: a review flagged for
        # C++ pointers, project progress and the activity feed all looked
        # identical in Python, because there was nowhere to record the track.
        "ALTER TABLE reviews ADD COLUMN language TEXT NOT NULL DEFAULT 'cpp'",
        "ALTER TABLE project_milestones ADD COLUMN language TEXT NOT NULL DEFAULT 'cpp'",
        "ALTER TABLE activity ADD COLUMN language TEXT NOT NULL DEFAULT 'cpp'",
        "ALTER TABLE project_activity ADD COLUMN language TEXT NOT NULL DEFAULT 'cpp'",

        # concept_progress caches a mastery label, and mastery is computed per
        # language. Keyed by concept_id alone it would show one track's label
        # for another. Rebuilt with a composite key.
        """
        CREATE TABLE concept_progress_v4 (
            concept_id  TEXT NOT NULL,
            language    TEXT NOT NULL DEFAULT 'cpp',
            label       TEXT NOT NULL,
            score       REAL NOT NULL DEFAULT 0.0,
            evidence    TEXT NOT NULL DEFAULT '',
            updated_at  TEXT NOT NULL,
            PRIMARY KEY (concept_id, language)
        )
        """,
        """
        INSERT INTO concept_progress_v4
            (concept_id, language, label, score, evidence, updated_at)
            SELECT concept_id, 'cpp', label, score, evidence, updated_at
            FROM concept_progress
        """,
        "DROP TABLE concept_progress",
        "ALTER TABLE concept_progress_v4 RENAME TO concept_progress",

        # projects is keyed by id alone for the same reason. Only C++ ships
        # projects today, so existing rows are all C++.
        """
        CREATE TABLE projects_v4 (
            id          TEXT NOT NULL,
            language    TEXT NOT NULL DEFAULT 'cpp',
            title       TEXT NOT NULL,
            purpose     TEXT NOT NULL DEFAULT '',
            concepts    TEXT NOT NULL DEFAULT '',
            difficulty  TEXT NOT NULL DEFAULT 'unknown',
            status      TEXT NOT NULL DEFAULT 'not_started',
            created_at  TEXT NOT NULL,
            updated_at  TEXT NOT NULL,
            PRIMARY KEY (id, language)
        )
        """,
        """
        INSERT INTO projects_v4
            (id, language, title, purpose, concepts, difficulty, status,
             created_at, updated_at)
            SELECT id, 'cpp', title, purpose, concepts, difficulty, status,
                   created_at, updated_at
            FROM projects
        """,
        "DROP TABLE projects",
        "ALTER TABLE projects_v4 RENAME TO projects",

        "CREATE INDEX IF NOT EXISTS idx_reviews_language ON reviews (language, status)",
        "CREATE INDEX IF NOT EXISTS idx_milestones_language ON project_milestones (language, project_id)",
        "CREATE INDEX IF NOT EXISTS idx_activity_language ON activity (language, id)",
    ],
}

LATEST_SCHEMA_VERSION = max(MIGRATIONS)


def _utcnow() -> str:
    """ISO-8601 UTC timestamp, second precision, always timezone-aware."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class Database:
    """Thin, explicit wrapper around a SQLite file.

    ``path`` may be ``":memory:"`` so tests can exercise real SQL without
    touching the user's disk.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        """Open the connection (if needed) and make sure the schema is current."""
        if self._conn is None:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            # Enforce declared foreign-key semantics rather than silently
            # ignoring them, which is the SQLite default.
            conn.execute("PRAGMA foreign_keys = ON")
            self._conn = conn
        self.migrate()
        return self._conn

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "Database":
        self.connect()
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Migrations
    # ------------------------------------------------------------------
    def schema_version(self) -> int:
        """Current schema version, or 0 for an untouched database."""
        conn = self.connect()
        row = conn.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0

    def migrate(self) -> int:
        """Apply every migration newer than the database's version.

        Returns the resulting schema version. Safe to call repeatedly; this is
        invoked on every :meth:`connect`.
        """
        conn = self.connect_raw()
        current = int(conn.execute("PRAGMA user_version").fetchone()[0])
        for version in sorted(MIGRATIONS):
            if version <= current:
                continue
            for statement in MIGRATIONS[version]:
                conn.execute(statement)
            conn.execute(f"PRAGMA user_version = {version}")
            current = version
        conn.commit()
        return current

    def connect_raw(self) -> sqlite3.Connection:
        """Get the connection without triggering :meth:`migrate`.

        ``migrate`` needs a connection before it can inspect the version, so it
        bootstraps through this to avoid infinite recursion.
        """
        if self._conn is None:
            conn = sqlite3.connect(self.path)
            conn.row_factory = sqlite3.Row
            self._conn = conn
        return self._conn

    # ------------------------------------------------------------------
    # Lesson progress
    # ------------------------------------------------------------------
    def mark_lesson_complete(self, lesson_id: str, language: str = "cpp") -> str:
        """Record a lesson as completed and return the stored timestamp.

        Re-completing a lesson keeps the original timestamp so progress history
        is not falsified by clicking twice. Completion is per language: the
        same lesson id in Python and in C are different achievements.
        """
        conn = self.connect()
        existing = conn.execute(
            "SELECT completed_at FROM lesson_progress "
            "WHERE lesson_id = ? AND language = ?",
            (lesson_id, language),
        ).fetchone()
        if existing is not None:
            return str(existing["completed_at"])
        stamp = _utcnow()
        conn.execute(
            "INSERT INTO lesson_progress (lesson_id, language, completed_at) "
            "VALUES (?, ?, ?)",
            (lesson_id, language, stamp),
        )
        conn.commit()
        return stamp

    def unmark_lesson_complete(self, lesson_id: str, language: str = "cpp") -> None:
        """Remove a completion mark (used by the 'reset progress' action)."""
        conn = self.connect()
        conn.execute(
            "DELETE FROM lesson_progress WHERE lesson_id = ? AND language = ?",
            (lesson_id, language),
        )
        conn.commit()

    def is_lesson_complete(self, lesson_id: str, language: str = "cpp") -> bool:
        conn = self.connect()
        row = conn.execute(
            "SELECT 1 FROM lesson_progress WHERE lesson_id = ? AND language = ?",
            (lesson_id, language),
        ).fetchone()
        return row is not None

    def completed_lessons(self, language: str = "cpp") -> list[str]:
        """All completed lesson ids for a language, in completion order."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT lesson_id FROM lesson_progress WHERE language = ? "
            "ORDER BY completed_at, lesson_id",
            (language,),
        ).fetchall()
        return [str(r["lesson_id"]) for r in rows]

    # ------------------------------------------------------------------
    # Exercise attempts
    # ------------------------------------------------------------------
    def record_exercise_attempt(
        self,
        lesson_id: str,
        exercise_id: str,
        *,
        source: str = "",
        compiled_ok: bool = False,
        ran_ok: bool = False,
        result: str = "",
        exercise_type: str = "freeform",
        concept_id: str = "",
        correct: bool = False,
        hints_used: int = 0,
        independent: bool | None = None,
        error_category: str = "",
        grade: str = "",
        novelty: bool = False,
        graded_by: str = "deterministic",
        language: str = "cpp",
    ) -> int:
        """Store one attempt at an exercise and return its row id.

        ``compiled_ok`` / ``ran_ok`` record what actually happened when the
        learner pressed Run, rather than what the tutor asserted.

        Phase 2 additions are keyword-only with defaults, so existing Phase 1
        callers are unaffected. ``graded_by`` distinguishes a deterministic
        check from an interpretive AI judgement, which the UI labels.

        ``independent`` defaults to ``None``, meaning "derive it": an attempt
        counts as independent only when it was correct and used no hints. Pass
        it explicitly to override, which :mod:`mentorsmith.services.practice`
        does so it can also account for escalation.
        """
        independent_flag = (
            bool(correct and hints_used == 0)
            if independent is None
            else bool(independent)
        )
        conn = self.connect()
        cur = conn.execute(
            """
            INSERT INTO exercise_attempts
                (lesson_id, exercise_id, source, compiled_ok, ran_ok, result,
                 exercise_type, concept_id, correct, hints_used, independent,
                 error_category, grade, novelty, graded_by, language, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lesson_id,
                exercise_id,
                source,
                int(bool(compiled_ok)),
                int(bool(ran_ok)),
                result,
                exercise_type,
                concept_id,
                int(bool(correct)),
                int(hints_used),
                int(independent_flag),
                error_category,
                grade,
                int(bool(novelty)),
                graded_by,
                language,
                _utcnow(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)

    def exercise_attempts(self, lesson_id: str, exercise_id: str | None = None) -> list[dict]:
        """Attempts for a lesson, newest first, optionally filtered."""
        conn = self.connect()
        if exercise_id is None:
            rows = conn.execute(
                "SELECT * FROM exercise_attempts WHERE lesson_id = ? ORDER BY id DESC",
                (lesson_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM exercise_attempts
                WHERE lesson_id = ? AND exercise_id = ?
                ORDER BY id DESC
                """,
                (lesson_id, exercise_id),
            ).fetchall()
        return [dict(r) for r in rows]

    def latest_attempt(self, lesson_id: str, exercise_id: str) -> dict | None:
        attempts = self.exercise_attempts(lesson_id, exercise_id)
        return attempts[0] if attempts else None

    def attempt_count(self, lesson_id: str, exercise_id: str) -> int:
        conn = self.connect()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM exercise_attempts WHERE lesson_id = ? AND exercise_id = ?",
            (lesson_id, exercise_id),
        ).fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------
    # Recent activity
    # ------------------------------------------------------------------
    def record_activity(
        self,
        kind: str,
        lesson_id: str | None = None,
        detail: str = "",
        language: str = "cpp",
    ) -> None:
        """Append an entry to the activity feed shown on the dashboard.

        Scoped by language: a C++ lesson event must not appear in the Python
        activity list just because the lesson id happens to match.
        """
        conn = self.connect()
        conn.execute(
            "INSERT INTO activity (kind, lesson_id, detail, language, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (kind, lesson_id, detail, language, _utcnow()),
        )
        conn.commit()

    def recent_activity(self, limit: int = 10, language: str = "cpp") -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM activity WHERE language = ? ORDER BY id DESC LIMIT ?",
            (language, int(limit)),
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_activity(self, language: str = "cpp") -> None:
        conn = self.connect()
        conn.execute("DELETE FROM activity WHERE language = ?", (language,))
        conn.commit()

    # ------------------------------------------------------------------
    # Non-secret settings
    # ------------------------------------------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        conn = self.connect()
        row = conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row is not None else default

    def set_setting(self, key: str, value: Any) -> None:
        """Upsert a non-secret setting.

        Callers must not pass credentials through this method.
        """
        conn = self.connect()
        conn.execute(
            "INSERT INTO app_settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        conn.commit()

    def all_settings(self) -> dict[str, str]:
        conn = self.connect()
        rows = conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {str(r["key"]): str(r["value"]) for r in rows}

    # ------------------------------------------------------------------
    # Phase 2: adaptive learning evidence
    # ------------------------------------------------------------------
    def attempts_for_concept(self, concept_id: str, language: str = "cpp") -> list[dict]:
        """Every graded attempt for a concept in one language, newest first."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM exercise_attempts "
            "WHERE concept_id = ? AND language = ? ORDER BY id DESC",
            (concept_id, language),
        ).fetchall()
        return [dict(r) for r in rows]

    def concept_evidence(
        self, concept_ids: Sequence[str], language: str = "cpp"
    ) -> dict[str, dict]:
        """Aggregate raw evidence per concept in a single pass.

        Returns counts only. Interpretation lives in
        :mod:`mentorsmith.core.mastery` so the numbers here stay objective and
        the labels stay explainable.
        """
        ids = list(concept_ids)
        summary: dict[str, dict] = {
            concept_id: {
                "attempts": 0,
                "correct": 0,
                "incorrect": 0,
                "hints_used": 0,
                "independent": 0,
                "first_try_correct": 0,
                "freeform_attempts": 0,
                "freeform_correct": 0,
                "novel_attempts": 0,
                "error_categories": {},
                "exercise_types": {},
            }
            for concept_id in ids
        }
        if not ids:
            return summary

        placeholders = ",".join("?" for _ in ids)
        rows = self.connect().execute(
            f"SELECT * FROM exercise_attempts "
            f"WHERE concept_id IN ({placeholders}) AND language = ? ORDER BY id ASC",
            (*ids, language),
        ).fetchall()

        # Track the earliest attempt per concept to spot first-try success.
        seen_first: set[str] = set()
        for row in rows:
            record = dict(row)
            concept_id = str(record["concept_id"])
            entry = summary.get(concept_id)
            if entry is None:
                continue
            entry["attempts"] += 1
            if record["correct"]:
                entry["correct"] += 1
            else:
                entry["incorrect"] += 1
            entry["hints_used"] += int(record.get("hints_used") or 0)
            if record.get("independent"):
                entry["independent"] += 1
            if record.get("exercise_type") == "explain-code":
                entry["freeform_attempts"] += 1
                if record["correct"]:
                    entry["freeform_correct"] += 1
            if record.get("novelty"):
                entry["novel_attempts"] += 1
            category = record.get("error_category") or ""
            if category:
                entry["error_categories"][category] = (
                    entry["error_categories"].get(category, 0) + 1
                )
            exercise_type = record.get("exercise_type") or ""
            if exercise_type:
                entry["exercise_types"][exercise_type] = (
                    entry["exercise_types"].get(exercise_type, 0) + 1
                )
            if concept_id not in seen_first:
                seen_first.add(concept_id)
                if record["correct"]:
                    entry["first_try_correct"] += 1
        return summary

    def error_category_counts(self, limit: int = 10) -> list[tuple[str, int]]:
        """Most frequent error categories across all attempts."""
        rows = self.connect().execute(
            "SELECT error_category, COUNT(*) AS n FROM exercise_attempts "
            "WHERE error_category != '' GROUP BY error_category "
            "ORDER BY n DESC, error_category LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [(str(r["error_category"]), int(r["n"])) for r in rows]

    def total_hints_used(self) -> int:
        row = self.connect().execute(
            "SELECT COALESCE(SUM(hints_used), 0) AS n FROM exercise_attempts"
        ).fetchone()
        return int(row["n"]) if row else 0

    def independent_attempt_count(self) -> int:
        """Attempts the learner solved without substantial help."""
        row = self.connect().execute(
            "SELECT COUNT(*) AS n FROM exercise_attempts "
            "WHERE correct = 1 AND independent = 1"
        ).fetchone()
        return int(row["n"]) if row else 0

    # ------------------------------------------------------------------
    # Concept progress cache
    # ------------------------------------------------------------------
    def set_concept_progress(
        self,
        concept_id: str,
        label: str,
        score: float,
        evidence: str = "",
        language: str = "cpp",
    ) -> None:
        """Cache a computed mastery label.

        Purely a cache: it can always be rebuilt from ``concept_evidence``. It is
        keyed by ``(concept_id, language)`` because mastery is computed per
        language, so one track's cached label must never be served for another.
        """
        conn = self.connect()
        conn.execute(
            "INSERT INTO concept_progress "
            "(concept_id, language, label, score, evidence, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(concept_id, language) DO UPDATE SET "
            "label = excluded.label, score = excluded.score, "
            "evidence = excluded.evidence, updated_at = excluded.updated_at",
            (concept_id, language, label, float(score), evidence, _utcnow()),
        )
        conn.commit()

    def get_concept_progress(self, concept_id: str, language: str = "cpp") -> dict | None:
        row = self.connect().execute(
            "SELECT * FROM concept_progress WHERE concept_id = ? AND language = ?",
            (concept_id, language),
        ).fetchone()
        return dict(row) if row else None

    def all_concept_progress(self, language: str = "cpp") -> dict[str, dict]:
        rows = self.connect().execute(
            "SELECT * FROM concept_progress WHERE language = ? ORDER BY concept_id",
            (language,),
        ).fetchall()
        return {str(r["concept_id"]): dict(r) for r in rows}

    # ------------------------------------------------------------------
    # Projects and milestones
    # ------------------------------------------------------------------
    def create_project(
        self,
        project_id: str,
        title: str,
        *,
        purpose: str = "",
        concepts: Sequence[str] = (),
        difficulty: str = "unknown",
        milestones: Sequence[dict] = (),
        language: str = "cpp",
    ) -> str:
        """Insert a project and its milestones. Returns the project id.

        Re-adding an existing project updates it rather than duplicating, so
        regenerating recommendations is safe. Keyed by ``(id, language)``: the
        same project id may exist in two tracks.
        """
        conn = self.connect()
        stamp = _utcnow()
        conn.execute(
            "INSERT INTO projects "
            "(id, language, title, purpose, concepts, difficulty, status, "
            " created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'not_started', ?, ?) "
            "ON CONFLICT(id, language) DO UPDATE SET title = excluded.title, "
            "purpose = excluded.purpose, concepts = excluded.concepts, "
            "difficulty = excluded.difficulty, updated_at = excluded.updated_at",
            (
                project_id, language, title, purpose,
                ",".join(concepts), difficulty, stamp, stamp,
            ),
        )
        if milestones:
            conn.execute(
                "DELETE FROM project_milestones "
                "WHERE project_id = ? AND language = ?",
                (project_id, language),
            )
            for ordinal, milestone in enumerate(milestones, start=1):
                conn.execute(
                    "INSERT INTO project_milestones "
                    "(project_id, language, ordinal, title, requirements, "
                    " acceptance_criteria, hint, status) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')",
                    (
                        project_id,
                        language,
                        ordinal,
                        str(milestone.get("title", f"Milestone {ordinal}")),
                        str(milestone.get("requirements", "")),
                        ",".join(
                            str(c) for c in milestone.get("acceptance_criteria", [])
                        ),
                        str(milestone.get("hint", "")),
                    ),
                )
        conn.commit()
        return project_id

    def get_project(self, project_id: str, language: str = "cpp") -> dict | None:
        row = self.connect().execute(
            "SELECT * FROM projects WHERE id = ? AND language = ?",
            (project_id, language),
        ).fetchone()
        return dict(row) if row else None

    def list_projects(self, language: str = "cpp") -> list[dict]:
        rows = self.connect().execute(
            "SELECT * FROM projects WHERE language = ? ORDER BY created_at, id",
            (language,),
        ).fetchall()
        return [dict(r) for r in rows]

    def set_project_status(
        self, project_id: str, status: str, language: str = "cpp"
    ) -> None:
        conn = self.connect()
        conn.execute(
            "UPDATE projects SET status = ?, updated_at = ? "
            "WHERE id = ? AND language = ?",
            (status, _utcnow(), project_id, language),
        )
        conn.commit()

    def milestones_for(self, project_id: str, language: str = "cpp") -> list[dict]:
        rows = self.connect().execute(
            "SELECT * FROM project_milestones "
            "WHERE project_id = ? AND language = ? ORDER BY ordinal",
            (project_id, language),
        ).fetchall()
        return [dict(r) for r in rows]

    def set_milestone_status(self, milestone_id: int, status: str) -> None:
        completed = _utcnow() if status == "done" else None
        conn = self.connect()
        conn.execute(
            "UPDATE project_milestones SET status = ?, completed_at = ? WHERE id = ?",
            (status, completed, milestone_id),
        )
        conn.commit()

    def record_project_activity(
        self,
        project_id: str,
        notes: str,
        *,
        milestone_id: int | None = None,
        needed_substantial_help: bool = False,
        language: str = "cpp",
    ) -> int:
        conn = self.connect()
        cur = conn.execute(
            "INSERT INTO project_activity "
            "(project_id, language, milestone_id, notes, needed_substantial_help, "
            " created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                project_id,
                language,
                milestone_id,
                notes,
                int(bool(needed_substantial_help)),
                _utcnow(),
            ),
        )
        conn.commit()
        return int(cur.lastrowid or 0)

    def project_activity_for(
        self, project_id: str, language: str = "cpp"
    ) -> list[dict]:
        rows = self.connect().execute(
            "SELECT * FROM project_activity "
            "WHERE project_id = ? AND language = ? ORDER BY id DESC",
            (project_id, language),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------
    def add_review(
        self,
        concept_id: str,
        reason: str,
        evidence: str = "",
        language: str = "cpp",
    ) -> int:
        """Flag a concept for review.

        Deduplicates on ``(concept_id, language, open)``. A C++ pointer review
        and a C pointer review are different flags: they point at different
        mistakes even when the concept ids differ only by track.
        """
        conn = self.connect()
        existing = conn.execute(
            "SELECT id FROM reviews "
            "WHERE concept_id = ? AND language = ? AND status = 'open'",
            (concept_id, language),
        ).fetchone()
        if existing is not None:
            return int(existing["id"])
        cur = conn.execute(
            "INSERT INTO reviews "
            "(concept_id, language, reason, evidence, status, created_at) "
            "VALUES (?, ?, ?, ?, 'open', ?)",
            (concept_id, language, reason, evidence, _utcnow()),
        )
        conn.commit()
        return int(cur.lastrowid or 0)

    def open_reviews(self, language: str = "cpp") -> list[dict]:
        rows = self.connect().execute(
            "SELECT * FROM reviews "
            "WHERE language = ? AND status = 'open' ORDER BY id",
            (language,),
        ).fetchall()
        return [dict(r) for r in rows]

    def close_review(self, review_id: int) -> None:
        conn = self.connect()
        conn.execute("UPDATE reviews SET status = 'done' WHERE id = ?", (review_id,))
        conn.commit()

    def reviews_for(self, concept_id: str, language: str = "cpp") -> list[dict]:
        rows = self.connect().execute(
            "SELECT * FROM reviews "
            "WHERE concept_id = ? AND language = ? ORDER BY id DESC",
            (concept_id, language),
        ).fetchall()
        return [dict(r) for r in rows]


    # ------------------------------------------------------------------
    # Aggregates used by the progress view
    # ------------------------------------------------------------------
    def lesson_stats(self, lesson_ids: Iterable[str]) -> dict[str, dict]:
        """Completion flags and attempt counts keyed by lesson id."""
        ids: Sequence[str] = list(lesson_ids)
        conn = self.connect()
        stats: dict[str, dict] = {}
        for lesson_id in ids:
            stats[lesson_id] = {
                "completed": self.is_lesson_complete(lesson_id),
                "attempts": 0,
            }
        if not ids:
            return stats
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT lesson_id, COUNT(*) AS n FROM exercise_attempts "
            f"WHERE lesson_id IN ({placeholders}) GROUP BY lesson_id",
            tuple(ids),
        ).fetchall()
        for row in rows:
            key = str(row["lesson_id"])
            if key in stats:
                stats[key]["attempts"] = int(row["n"])
        return stats