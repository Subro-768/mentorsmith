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
    def mark_lesson_complete(self, lesson_id: str) -> str:
        """Record a lesson as completed and return the stored timestamp.

        Re-completing a lesson keeps the original timestamp so progress history
        is not falsified by clicking twice.
        """
        conn = self.connect()
        existing = conn.execute(
            "SELECT completed_at FROM lesson_progress WHERE lesson_id = ?",
            (lesson_id,),
        ).fetchone()
        if existing is not None:
            return str(existing["completed_at"])
        stamp = _utcnow()
        conn.execute(
            "INSERT INTO lesson_progress (lesson_id, completed_at) VALUES (?, ?)",
            (lesson_id, stamp),
        )
        conn.commit()
        return stamp

    def unmark_lesson_complete(self, lesson_id: str) -> None:
        """Remove a completion mark (used by the 'reset progress' action)."""
        conn = self.connect()
        conn.execute("DELETE FROM lesson_progress WHERE lesson_id = ?", (lesson_id,))
        conn.commit()

    def is_lesson_complete(self, lesson_id: str) -> bool:
        conn = self.connect()
        row = conn.execute(
            "SELECT 1 FROM lesson_progress WHERE lesson_id = ?", (lesson_id,)
        ).fetchone()
        return row is not None

    def completed_lessons(self) -> list[str]:
        """All completed lesson ids, in completion order."""
        conn = self.connect()
        rows = conn.execute(
            "SELECT lesson_id FROM lesson_progress ORDER BY completed_at, lesson_id"
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
    ) -> int:
        """Store one attempt at an exercise and return its row id.

        ``compiled_ok`` / ``ran_ok`` record what actually happened when the
        learner pressed Run, rather than what the tutor asserted.
        """
        conn = self.connect()
        cur = conn.execute(
            """
            INSERT INTO exercise_attempts
                (lesson_id, exercise_id, source, compiled_ok, ran_ok, result, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                lesson_id,
                exercise_id,
                source,
                int(bool(compiled_ok)),
                int(bool(ran_ok)),
                result,
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
    def record_activity(self, kind: str, lesson_id: str | None = None, detail: str = "") -> None:
        """Append an entry to the activity feed shown on the dashboard."""
        conn = self.connect()
        conn.execute(
            "INSERT INTO activity (kind, lesson_id, detail, created_at) VALUES (?, ?, ?, ?)",
            (kind, lesson_id, detail, _utcnow()),
        )
        conn.commit()

    def recent_activity(self, limit: int = 10) -> list[dict]:
        conn = self.connect()
        rows = conn.execute(
            "SELECT * FROM activity ORDER BY id DESC LIMIT ?", (int(limit),)
        ).fetchall()
        return [dict(r) for r in rows]

    def clear_activity(self) -> None:
        conn = self.connect()
        conn.execute("DELETE FROM activity")
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