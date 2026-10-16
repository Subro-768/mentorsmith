"""The optional MentorSmith sync backend.

A small FastAPI service implementing the contract in ``docs/sync-contract.md``.
It exists for one reason: **an APK is not a secret store**, so the Android app
cannot hold an AI provider key. A backend like this can hold it and answer on
the user's behalf. It is entirely optional — with no endpoint configured the
Android app works fully offline and no server is ever contacted.

Deliberate omissions:

* **No user accounts and no authentication.** Phase 3 said to ask before
  introducing authentication, and a single-user local server does not need it.
  Anyone who can reach the endpoint can post to it, so it must be bound to
  localhost or a trusted network. `docs/sync-contract.md` says so plainly.
* **No cloud services.** It is a local SQLite file.
* **No tutor proxy.** That is the obvious next endpoint and it is deliberately
  not here yet; see the handoff notes.

Run it with::

    uvicorn sync_server.app:app --host 127.0.0.1 --port 8000

and point the Android app's Settings screen at ``http://<host>:8000``.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .store import ENTITY_TYPES, SCHEMA_VERSION, SyncChange, SyncStore

#: Bump when the wire format changes in a way an older client cannot read.
#: The client refuses to sync when the server asks for more than it supports.
MIN_CLIENT_VERSION = 1

app = FastAPI(
    title="MentorSmith sync",
    version="0.1.0",
    description=(
        "Offline-first progress sync for MentorSmith. Optional: the Android app "
        "works fully without it."
    ),
)

_DB_PATH = os.environ.get("MENTORSMITH_SYNC_DB", str(Path.home() / ".mentorsmith-sync.db"))
_store = SyncStore(_DB_PATH)


class ChangeModel(BaseModel):
    client_id: str = Field(min_length=1, max_length=200)
    entity_type: str
    operation: str = "upsert"
    language: str = "cpp"
    updated_at: str = ""
    payload: dict = Field(default_factory=dict)


class SyncRequestModel(BaseModel):
    device_id: str = Field(min_length=1, max_length=200)
    client_version: int = 1
    since: str | None = None
    changes: list[ChangeModel] = Field(default_factory=list)


class AcceptedModel(BaseModel):
    client_id: str


class ConflictModel(BaseModel):
    client_id: str
    entity_type: str
    language: str
    client_value: str
    server_value: str
    reason: str


class SyncResponseModel(BaseModel):
    server_time: str
    min_client_version: int
    schema_version: int
    accepted: list[AcceptedModel]
    server_changes: list[ChangeModel]
    conflicts: list[ConflictModel]


@app.get("/health")
def health() -> dict:
    """Liveness plus row counts, so state can be checked without a device."""
    return {"status": "ok", "schema_version": SCHEMA_VERSION, "counts": _store.stats()}


@app.get("/v1/contract")
def contract() -> dict:
    """Machine-readable description of what this server understands."""
    return {
        "schema_version": SCHEMA_VERSION,
        "min_client_version": MIN_CLIENT_VERSION,
        "entity_types": sorted(ENTITY_TYPES),
        "append_only": ["exercise_attempt", "review"],
        "monotonic": ["lesson_progress"],
        "mergeable": ["project_milestone"],
    }


@app.post("/v1/sync", response_model=SyncResponseModel)
def sync(request: SyncRequestModel) -> SyncResponseModel:
    """Apply inbound changes and return everything else that changed.

    Idempotent: re-sending a change with the same ``client_id`` does not
    duplicate anything.
    """
    if request.client_version < MIN_CLIENT_VERSION:
        raise HTTPException(
            status_code=426,
            detail="This server requires a newer client version.",
        )

    accepted: list[AcceptedModel] = []
    conflicts: list[ConflictModel] = []

    for model in request.changes:
        if model.entity_type not in ENTITY_TYPES:
            # Rejected rather than stored, so an unknown type cannot poison state.
            continue
        change = SyncChange(
            client_id=model.client_id,
            entity_type=model.entity_type,
            operation=model.operation,
            language=model.language,
            updated_at=model.updated_at,
            payload=model.payload,
        )
        outcome, found = _store.apply(change, device_id=request.device_id)
        if outcome == "applied":
            accepted.append(AcceptedModel(client_id=model.client_id))
        # A duplicate is deliberately NOT acknowledged again: the client keeps
        # it queued until the server confirms, and a repeated confirm is a no-op.

        conflicts.extend(
            ConflictModel(
                client_id=c.client_id,
                entity_type=c.entity_type,
                language=c.language,
                client_value=c.client_value,
                server_value=c.server_value,
                reason=c.reason,
            )
            for c in found
        )

    from datetime import datetime, timezone

    inbound = [
        ChangeModel(
            client_id=change.client_id,
            entity_type=change.entity_type,
            language=change.language,
            updated_at=change.updated_at,
            payload=change.payload,
        )
        for change in _store.changes_since(request.since, device_id=request.device_id)
    ]

    return SyncResponseModel(
        server_time=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        min_client_version=MIN_CLIENT_VERSION,
        schema_version=SCHEMA_VERSION,
        accepted=accepted,
        server_changes=inbound,
        conflicts=conflicts,
    )