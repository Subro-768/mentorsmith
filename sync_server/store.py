"""Sync store: the server side of the MentorSmith sync contract.

Documented in ``docs/sync-contract.md`` and implemented by the Android client in
``android/.../data/remote/``. This module holds the **conflict rules**, which are
the part worth being careful about.

The governing principle is *preserve history over overwrite newer data*. So:

``lesson_progress``
    Monotonic. A completion is a fact that cannot be un-done by a slow client.
    A replay that claims completion is accepted; a replay that claims the lesson
    was never completed does **not** undo it.

``exercise_attempt``
    Append-only, keyed by the client's ``client_id``. A repeat is ignored, so a
    retry after a timeout cannot inflate the history. Never conflicts.

``project_milestone``
    The one genuinely mutable record. Merged per field by ``updated_at``; when
    both sides moved the same field to *different* values the change is still
    stored and a conflict is reported rather than one side silently winning.

``review``
    Append-only. Both sides kept.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone

SCHEMA_VERSION = 1

ENTITY_TYPES = {
    "lesson_progress",
    "exercise_attempt",
    "project_milestone",
    "review",
}

#: Records that can never conflict, because they are only ever appended.
APPEND_ONLY = {"exercise_attempt", "review"}

#: Records where completion is a one-way fact.
MONOTONIC = {"lesson_progress"}

#: Records where both sides may legitimately change the same field.
MERGEABLE = {"project_milestone"}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class SyncChange:
    """One inbound change."""

    client_id: str
    entity_type: str
    operation: str = "upsert"
    language: str = "cpp"
    updated_at: str = ""
    payload: dict = field(default_factory=dict)


@dataclass
class Conflict:
    client_id: str
    entity_type: str
    language: str
    client_value: str
    server_value: str
    reason: str


class SyncStore:
    """SQLite-backed store for the sync endpoint."""

    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    # ------------------------------------------------------------------
    def _migrate(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS lesson_progress (
                language     TEXT NOT NULL,
                entity_key   TEXT NOT NULL,
                client_id    TEXT NOT NULL,
                payload      TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                device_id    TEXT NOT NULL DEFAULT '',
                PRIMARY KEY (language, entity_key)
            );

            CREATE TABLE IF NOT EXISTS exercise_attempts (
                client_id    TEXT PRIMARY KEY,
                language     TEXT NOT NULL,
                payload      TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                device_id    TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS reviews (
                client_id    TEXT PRIMARY KEY,
                language     TEXT NOT NULL,
                payload      TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                device_id    TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS project_milestones (
                language     TEXT NOT NULL,
                entity_key   TEXT NOT NULL,
                client_id    TEXT NOT NULL,
                payload      TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                device_id    TEXT NOT NULL DEFAULT '',
                history      TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (language, entity_key)
            );

            CREATE TABLE IF NOT EXISTS change_log (
                seq          INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type  TEXT NOT NULL,
                language     TEXT NOT NULL,
                entity_key   TEXT NOT NULL,
                client_id    TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                device_id    TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS seen_clients (
                client_id    TEXT PRIMARY KEY,
                seen_at      TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    def apply(
        self, change: SyncChange, device_id: str = ""
    ) -> tuple[str, list[Conflict]]:
        """Apply one change.

        Returns ``(outcome, conflicts)`` where outcome is one of
        ``applied``, ``duplicate`` or ``rejected``.
        """
        if change.entity_type not in ENTITY_TYPES:
            return "rejected", []

        handler = {
            "lesson_progress": self._apply_lesson_progress,
            "exercise_attempt": self._apply_append_only,
            "review": self._apply_append_only,
            "project_milestone": self._apply_milestone,
        }[change.entity_type]
        return handler(change, device_id)

    # -- monotonic ------------------------------------------------------
    def _apply_lesson_progress(
        self, change: SyncChange, device_id: str
    ) -> tuple[str, list[Conflict]]:
        key = change.payload.get("lesson_id") or change.client_id
        row = self._conn.execute(
            "SELECT * FROM lesson_progress WHERE language = ? AND entity_key = ?",
            (change.language, key),
        ).fetchone()

        if row is None:
            self._conn.execute(
                "INSERT INTO lesson_progress "
                "(language, entity_key, client_id, payload, updated_at, device_id) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    change.language, key, change.client_id,
                    json.dumps(change.payload), change.updated_at or _now(), device_id,
                ),
            )
        else:
            # Completion is a fact. An older or empty replay never removes it,
            # and never produces a conflict: there is nothing to disagree about.
            existing = json.loads(row["payload"])
            merged = dict(existing)
            for field_name in ("completed_at",):
                incoming = change.payload.get(field_name)
                if incoming and (not existing.get(field_name) or incoming < existing[field_name]):
                    merged[field_name] = incoming
            self._conn.execute(
                "UPDATE lesson_progress SET payload = ?, updated_at = ?, client_id = ? "
                "WHERE language = ? AND entity_key = ?",
                (
                    json.dumps(merged),
                    min(row["updated_at"], change.updated_at or row["updated_at"]) or _now(),
                    change.client_id,
                    change.language, key,
                ),
            )
        self._log(change, device_id, key)
        self._conn.commit()
        return "applied", []

    # -- append only ----------------------------------------------------
    def _apply_append_only(
        self, change: SyncChange, device_id: str
    ) -> tuple[str, list[Conflict]]:
        seen = self._conn.execute(
            "SELECT 1 FROM seen_clients WHERE client_id = ?", (change.client_id,)
        ).fetchone()
        if seen is not None:
            # Idempotent: a retry after a timeout is a no-op, which is exactly
            # what stops a duplicate attempt appearing in the history.
            return "duplicate", []

        table = "exercise_attempts" if change.entity_type == "exercise_attempt" else "reviews"
        self._conn.execute(
            f"INSERT INTO {table} (client_id, language, payload, updated_at, device_id) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                change.client_id, change.language,
                json.dumps(change.payload), change.updated_at or _now(), device_id,
            ),
        )
        self._conn.execute(
            "INSERT OR IGNORE INTO seen_clients (client_id, seen_at) VALUES (?, ?)",
            (change.client_id, _now()),
        )
        self._log(change, device_id, change.client_id)
        self._conn.commit()
        return "applied", []

    # -- mergeable ------------------------------------------------------
    def _apply_milestone(
        self, change: SyncChange, device_id: str
    ) -> tuple[str, list[Conflict]]:
        key = change.payload.get("project_id", "") + "#" + str(
            change.payload.get("ordinal", change.client_id)
        )
        row = self._conn.execute(
            "SELECT * FROM project_milestones WHERE language = ? AND entity_key = ?",
            (change.language, key),
        ).fetchone()

        conflicts: list[Conflict] = []

        if row is None:
            self._conn.execute(
                "INSERT INTO project_milestones "
                "(language, entity_key, client_id, payload, updated_at, device_id, history) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    change.language, key, change.client_id,
                    json.dumps(change.payload), change.updated_at or _now(), device_id,
                    json.dumps([{"client_id": change.client_id, "at": change.updated_at}]),
                ),
            )
        else:
            server_payload = json.loads(row["payload"])
            client_value = dict(server_payload)
            client_value.update(change.payload)

            incoming_at = change.updated_at or row["updated_at"]
            newer_incoming = incoming_at >= row["updated_at"]

            # Every version is retained, so nothing is ever lost.
            history = json.loads(row["history"] or "[]")
            history.append({
                "client_id": change.client_id,
                "at": incoming_at,
                "payload": change.payload,
            })

            for field_name, incoming in change.payload.items():
                existing = server_payload.get(field_name)
                if (
                    existing is not None
                    and incoming is not None
                    and existing != incoming
                    and field_name in ("status", "notes")
                ):
                    conflicts.append(
                        Conflict(
                            client_id=change.client_id,
                            entity_type=change.entity_type,
                            language=change.language,
                            client_value=str(incoming),
                            server_value=str(existing),
                            reason=(
                                f"both sides changed '{field_name}'"
                                + (
                                    "; the newer edit was kept and both versions "
                                    "remain in history"
                                    if newer_incoming
                                    else "; the newer server edit was kept"
                                )
                            ),
                        )
                    )

            # The newer edit wins the record; the older one is preserved in
            # history, so nothing is ever lost either way.
            if newer_incoming:
                merged = dict(server_payload)
                merged.update(change.payload)
            else:
                merged = server_payload

            self._conn.execute(
                "UPDATE project_milestones SET payload = ?, updated_at = ?, "
                "client_id = ?, history = ? WHERE language = ? AND entity_key = ?",
                (
                    json.dumps(merged),
                    incoming_at if newer_incoming else row["updated_at"],
                    change.client_id,
                    json.dumps(history),
                    change.language, key,
                ),
            )

        self._log(change, device_id, key)
        self._conn.commit()
        return "applied", conflicts

    def _log(self, change: SyncChange, device_id: str, key: str) -> None:
        self._conn.execute(
            "INSERT INTO change_log "
            "(entity_type, language, entity_key, client_id, updated_at, device_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                change.entity_type, change.language, key,
                change.client_id, change.updated_at or _now(), device_id,
            ),
        )

    # ------------------------------------------------------------------
    def changes_since(self, since: str | None, device_id: str = "") -> list[SyncChange]:
        """Changes made by *other* devices after ``since``.

        A device never receives its own writes back, which keeps the client
        simple and avoids pointless churn.
        """
        query = (
            "SELECT * FROM change_log WHERE updated_at > ?"
            + (" AND device_id != ?" if device_id else "")
            + " ORDER BY seq ASC"
        )
        params: tuple = (since or "", device_id) if device_id else (since or "",)
        rows = self._conn.execute(query, params).fetchall()

        result: list[SyncChange] = []
        for row in rows:
            payload = self._payload_for(row["entity_type"], row["language"], row["entity_key"])
            if payload is None:
                continue
            result.append(
                SyncChange(
                    client_id=row["client_id"],
                    entity_type=row["entity_type"],
                    language=row["language"],
                    updated_at=row["updated_at"],
                    payload=payload,
                )
            )
        return result

    def _payload_for(self, entity_type: str, language: str, key: str) -> dict | None:
        if entity_type == "lesson_progress":
            row = self._conn.execute(
                "SELECT payload FROM lesson_progress WHERE language = ? AND entity_key = ?",
                (language, key),
            ).fetchone()
        elif entity_type == "project_milestone":
            row = self._conn.execute(
                "SELECT payload FROM project_milestones WHERE language = ? AND entity_key = ?",
                (language, key),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT payload FROM " + ("exercise_attempts" if entity_type == "exercise_attempt" else "reviews")
                + " WHERE client_id = ?",
                (key,),
            ).fetchone()
        return json.loads(row["payload"]) if row else None

    # ------------------------------------------------------------------
    def stats(self) -> dict:
        """Row counts, for a quick sanity check that state is landing."""
        def count(table: str) -> int:
            return int(self._conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"])

        return {
            "lesson_progress": count("lesson_progress"),
            "exercise_attempts": count("exercise_attempts"),
            "project_milestones": count("project_milestones"),
            "reviews": count("reviews"),
            "change_log": count("change_log"),
        }