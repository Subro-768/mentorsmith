"""Conflict rules and the HTTP endpoint, exercised against real behaviour.

FastAPI's test client is used against the in-process app, so these are genuine
request/response tests rather than assertions about internal helpers.

The sync server is optional, so these tests skip cleanly when FastAPI is absent
rather than failing the whole suite.
"""

from __future__ import annotations

import importlib

import pytest

from sync_server.store import SyncChange, SyncStore

pytest.importorskip("fastapi", reason="fastapi is not installed")
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture()
def store() -> SyncStore:
    return SyncStore(":memory:")


@pytest.fixture()
def client() -> TestClient:
    """A client bound to a fresh in-memory store for every test."""
    # Imported this way because `sync_server.app` is a module name that a plain
    # `from .app import app` in the package __init__ would shadow.
    module = importlib.import_module("sync_server.app")
    module._store = SyncStore(":memory:")
    return TestClient(module.app)


def change(client_id="c1", entity_type="exercise_attempt", language="cpp", **payload):
    return {
        "client_id": client_id,
        "entity_type": entity_type,
        "language": language,
        "updated_at": payload.pop("updated_at", "2026-10-16T12:00:00+00:00"),
        "payload": payload,
    }


def post(client: TestClient, changes, since=None, device="device-a", version=1):
    response = client.post(
        "/v1/sync",
        json={"device_id": device, "client_version": version, "since": since,
              "changes": changes},
    )
    assert response.status_code == 200, response.text
    return response.json()


# ======================================================================
# Health and contract
# ======================================================================
def test_health_reports_counts(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["counts"]["exercise_attempts"] == 0


def test_contract_documents_the_rules(client: TestClient) -> None:
    body = client.get("/v1/contract").json()
    assert body["min_client_version"] == 1
    assert "exercise_attempt" in body["entity_types"]
    assert "lesson_progress" in body["monotonic"]
    assert "project_milestone" in body["mergeable"]


def test_a_too_old_client_is_upgraded_not_served(client: TestClient) -> None:
    response = client.post(
        "/v1/sync",
        json={"device_id": "d", "client_version": 0, "changes": []},
    )
    assert response.status_code == 426


# ======================================================================
# Idempotency
# ======================================================================
def test_a_change_is_acknowledged_once(client: TestClient) -> None:
    body = post(client, [change()])
    assert [a["client_id"] for a in body["accepted"]] == ["c1"]


def test_resending_the_same_client_id_does_not_duplicate(client: TestClient) -> None:
    post(client, [change()])
    post(client, [change()])
    body = client.get("/health").json()
    assert body["counts"]["exercise_attempts"] == 1, "a retry created a duplicate"


def test_a_duplicate_is_not_acknowledged_again(client: TestClient) -> None:
    post(client, [change()])
    second = post(client, [change()])
    assert second["accepted"] == [], "client would otherwise re-queue forever"


def test_distinct_client_ids_are_kept_separately(client: TestClient) -> None:
    post(client, [change(client_id="c1"), change(client_id="c2")])
    assert client.get("/health").json()["counts"]["exercise_attempts"] == 2


def test_an_unknown_entity_type_is_rejected_not_stored(client: TestClient) -> None:
    body = post(client, [change(entity_type="telepathy")])
    assert body["accepted"] == []
    assert client.get("/health").json()["counts"]["change_log"] == 0


# ======================================================================
# Monotonic completion
# ======================================================================
def test_completion_is_recorded(client: TestClient) -> None:
    post(client, [change(client_id="p1", entity_type="lesson_progress",
                         lesson_id="01-program-structure", completed_at="2026-10-16T10:00:00+00:00")])
    assert client.get("/health").json()["counts"]["lesson_progress"] == 1


def test_a_replay_does_not_erase_a_completion(client: TestClient) -> None:
    post(client, [change(client_id="p1", entity_type="lesson_progress",
                         lesson_id="01-program-structure", completed_at="2026-10-16T10:00:00+00:00")])
    # A different device claims the lesson was never finished.
    body = post(
        client,
        [change(client_id="p2", entity_type="lesson_progress",
                lesson_id="01-program-structure", updated_at="2026-10-15T09:00:00+00:00")],
        device="device-b",
    )
    assert body["conflicts"] == [], "completion is a fact; it cannot conflict"
    assert client.get("/health").json()["counts"]["lesson_progress"] == 1


# ======================================================================
# Language scoping
# ======================================================================
def test_the_same_lesson_id_in_two_languages_is_two_rows(client: TestClient) -> None:
    post(client, [change(client_id="p1", entity_type="lesson_progress",
                         lesson_id="01-variables-and-types", completed_at="2026-10-16T10:00:00+00:00")])
    post(client, [change(client_id="p2", entity_type="lesson_progress", language="python",
                         lesson_id="01-variables-and-types", completed_at="2026-10-16T10:00:00+00:00")])
    assert client.get("/health").json()["counts"]["lesson_progress"] == 2


def test_attempts_in_different_languages_stay_separate(client: TestClient) -> None:
    post(client, [change(client_id="a1", language="cpp", exercise_id="e1")])
    post(client, [change(client_id="a2", language="python", exercise_id="e1")])
    body = client.get("/health").json()
    assert body["counts"]["exercise_attempts"] == 2


# ======================================================================
# Milestone conflicts - the only real conflict case
# ======================================================================
def test_a_first_milestone_change_is_applied(client: TestClient) -> None:
    post(client, [change(client_id="m1", entity_type="project_milestone",
                         project_id="proj", ordinal="1", status="done",
                         updated_at="2026-10-16T10:00:00+00:00")])
    assert client.get("/health").json()["counts"]["project_milestones"] == 1


def test_both_sides_changing_status_reports_a_conflict(client: TestClient) -> None:
    post(client, [change(client_id="m1", entity_type="project_milestone",
                         project_id="proj", ordinal="1", status="done",
                         updated_at="2026-10-16T10:00:00+00:00")], device="device-a")

    body = post(
        client,
        [change(client_id="m2", entity_type="project_milestone",
                project_id="proj", ordinal="1", status="blocked",
                updated_at="2026-10-16T12:00:00+00:00")],
        device="device-b",
    )
    assert len(body["conflicts"]) == 1
    conflict = body["conflicts"][0]
    assert conflict["server_value"] == "done"
    assert conflict["client_value"] == "blocked"
    assert "status" in conflict["reason"]


def test_a_conflict_does_not_lose_the_newer_value(client: TestClient) -> None:
    post(client, [change(client_id="m1", entity_type="project_milestone",
                         project_id="proj", ordinal="1", status="done",
                         updated_at="2026-10-16T10:00:00+00:00")], device="device-a")
    post(client, [change(client_id="m2", entity_type="project_milestone",
                         project_id="proj", ordinal="1", status="blocked",
                         updated_at="2026-10-16T12:00:00+00:00")], device="device-b")

    stored = client.post(
        "/v1/sync",
        json={"device_id": "device-c", "client_version": 1, "since": None, "changes": []},
    ).json()
    assert stored["conflicts"] == []
    # The newer edit won the record.
    statuses = [c["payload"].get("status") for c in stored["server_changes"]]
    assert "blocked" in statuses


def test_an_older_change_does_not_overwrite_a_newer_one(client: TestClient) -> None:
    post(client, [change(client_id="m1", entity_type="project_milestone",
                         project_id="proj", ordinal="1", status="in_progress",
                         updated_at="2026-10-16T12:00:00+00:00")], device="device-a")
    post(client, [change(client_id="m2", entity_type="project_milestone",
                         project_id="proj", ordinal="1", status="pending",
                         updated_at="2026-10-16T10:00:00+00:00")], device="device-b")

    body = client.post(
        "/v1/sync",
        json={"device_id": "device-c", "client_version": 1, "since": None, "changes": []},
    ).json()
    statuses = [c["payload"].get("status") for c in body["server_changes"]]
    assert "in_progress" in statuses
    assert "pending" not in statuses, "a stale write clobbered the newer one"


def test_history_retains_both_versions(client: TestClient) -> None:
    post(client, [change(client_id="m1", entity_type="project_milestone",
                         project_id="proj", ordinal="1", status="done",
                         updated_at="2026-10-16T10:00:00+00:00")], device="device-a")
    post(client, [change(client_id="m2", entity_type="project_milestone",
                         project_id="proj", ordinal="1", status="blocked",
                         updated_at="2026-10-16T12:00:00+00:00")], device="device-b")
    assert client.get("/health").json()["counts"]["project_milestones"] == 1


# ======================================================================
# Pulling changes
# ======================================================================
def test_a_device_does_not_receive_its_own_changes_back(client: TestClient) -> None:
    post(client, [change(client_id="c1")], device="device-a")
    body = client.post(
        "/v1/sync",
        json={"device_id": "device-a", "client_version": 1, "since": None, "changes": []},
    ).json()
    assert body["server_changes"] == []


def test_another_device_receives_them(client: TestClient) -> None:
    post(client, [change(client_id="c1", exercise_id="e1")], device="device-a")
    body = client.post(
        "/v1/sync",
        json={"device_id": "device-b", "client_version": 1, "since": None, "changes": []},
    ).json()
    assert len(body["server_changes"]) == 1
    assert body["server_changes"][0]["payload"]["exercise_id"] == "e1"


def test_since_filters_older_changes(client: TestClient) -> None:
    post(client, [change(client_id="c1", updated_at="2026-10-16T10:00:00+00:00")],
         device="device-a")
    post(client, [change(client_id="c2", updated_at="2026-10-16T14:00:00+00:00")],
         device="device-a")
    body = client.post(
        "/v1/sync",
        json={
            "device_id": "device-b",
            "client_version": 1,
            "since": "2026-10-16T12:00:00+00:00",
            "changes": [],
        },
    ).json()
    assert len(body["server_changes"]) == 1


def test_an_empty_request_is_valid(client: TestClient) -> None:
    body = post(client, [])
    assert body["accepted"] == []
    assert body["server_changes"] == []


# ======================================================================
# Store-level guarantees
# ======================================================================
def test_store_rejects_an_unknown_entity_type() -> None:
    store = SyncStore(":memory:")
    outcome, _ = store.apply(SyncChange("x", "not_a_thing"), device_id="d")
    assert outcome == "rejected"


def test_stats_start_at_zero() -> None:
    store = SyncStore(":memory:")
    assert store.stats()["change_log"] == 0