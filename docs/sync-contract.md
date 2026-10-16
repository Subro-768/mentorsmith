"""Sync contract and conflict rules.

Both sides implement this: the Android client in
``android/app/src/main/java/app/mentorsmith/android/data/remote/`` and the
optional Python backend in ``sync_server/``. The Linux desktop app does not sync
— it is the source of truth for content and progress on that machine.

## Endpoint

```
POST /v1/sync
```

Request:

```json
{
  "device_id": "random-uuid",
  "client_version": 1,
  "since": "2026-10-16T00:00:00+00:00",
  "changes": [
    {
      "client_id": "unique-per-record",
      "entity_type": "exercise_attempt",
      "operation": "upsert",
      "language": "cpp",
      "updated_at": "2026-10-16T12:00:00+00:00",
      "payload": { "exercise_id": "...", "correct": "true", "hints_used": "0" }
    }
  ]
}
```

Response:

```json
{
  "server_time": "2026-10-16T12:00:01+00:00",
  "min_client_version": 1,
  "schema_version": 1,
  "accepted": [{ "client_id": "unique-per-record" }],
  "server_changes": [],
  "conflicts": []
}
```

Also available: `GET /health` (liveness and row counts) and
`GET /v1/contract` (machine-readable capabilities).

## The rule that matters most

**A row is only ever marked `synced` after the server names its `client_id` in
`accepted`.** Nothing is shown as synced optimistically, and a failed send stays
queued for retry.

## Idempotency

`client_id` is generated on the device and is the idempotency key. Re-sending a
change with the same `client_id` is a no-op, so a retry after a timeout cannot
duplicate history. The client may therefore retry freely.

## Conflict rules

The governing principle is **preserve history over overwrite newer data**.
Nothing is silently discarded.

| Entity | Strategy | Conflicts? |
|---|---|---|
| `lesson_progress` | Monotonic. A completion is a fact; a stale replay claiming "not completed" never undoes it. | No — there is nothing to disagree about |
| `exercise_attempt` | Append-only, deduplicated by `client_id`. | No |
| `review` | Append-only. | No |
| `project_milestone` | Field-level merge, newest `updated_at` wins the record. | Yes, when both sides changed `status` or `notes` to different values |

When a milestone conflicts, **the change is still stored** and every version is
retained in a history list. The conflict is reported so a human can decide. A
conflict is never resolved automatically by discarding one side.

## Language scoping

Every key includes `language`. The same lesson id in Python and in C are
different achievements, and sync preserves that separation.

## Authentication

**There is none, by design.** Phase 3 required asking before introducing
authentication, and a single-user local server does not need it.

The consequence must be stated plainly: **anyone who can reach this endpoint
can read and write the stored progress.** Run it on localhost or a trusted
network. It is not suitable for the public internet as it stands.

If it is ever exposed beyond a trusted network it needs, at minimum, a shared
token and TLS. That is not implemented and must not be assumed.

## Privacy

* The client never sends credentials. There is no API key field in the contract.
* No source files or project directories are uploaded. Only the small payloads
  listed above.
* The client does not send chat message contents or usage telemetry, because
  neither is treated as evidence of learning on the desktop and sending them
  would invite the same mistake here.