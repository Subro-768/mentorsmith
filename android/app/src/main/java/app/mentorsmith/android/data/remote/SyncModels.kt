package app.mentorsmith.android.data.remote

import org.json.JSONArray
import org.json.JSONObject

/**
 * The sync wire contract, shared with the Python backend.
 *
 * Documented in `docs/sync-contract.md`. Mapped to JSON with `org.json`
 * rather than a serialization library, so the APK carries no extra plugin or
 * runtime for what is a handful of fields.
 *
 * **No credential is ever sent from this app.** See [SyncClient].
 */

const val CURRENT_CLIENT_VERSION = 1

/**
 * One outbound change.
 *
 * [clientId] is the idempotency key. The server records it and ignores a
 * repeat, so a retry after a timeout cannot create a duplicate row.
 */
data class SyncChange(
    val clientId: String,
    val entityType: String,
    val operation: String,
    val language: String,
    val updatedAt: String,
    val payload: Map<String, String> = emptyMap(),
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("client_id", clientId)
        put("entity_type", entityType)
        put("operation", operation)
        put("language", language)
        put("updated_at", updatedAt)
        put("payload", JSONObject(payload))
    }

    companion object {
        fun fromJson(json: JSONObject): SyncChange {
            val payloadJson = json.optJSONObject("payload") ?: JSONObject()
            val payload = mutableMapOf<String, String>()
            payloadJson.keys().forEach { key -> payload[key] = payloadJson.optString(key) }
            return SyncChange(
                clientId = json.getString("client_id"),
                entityType = json.optString("entity_type"),
                operation = json.optString("operation", "upsert"),
                language = json.optString("language"),
                updatedAt = json.optString("updated_at"),
                payload = payload,
            )
        }
    }
}

data class SyncRequest(
    val deviceId: String,
    val clientVersion: Int = CURRENT_CLIENT_VERSION,
    val since: String? = null,
    val changes: List<SyncChange> = emptyList(),
) {
    fun toJson(): JSONObject = JSONObject().apply {
        put("device_id", deviceId)
        put("client_version", clientVersion)
        since?.let { put("since", it) }
        put("changes", JSONArray().apply { changes.forEach { put(it.toJson()) } })
    }
}

/**
 * A genuine divergence.
 *
 * Never resolved automatically. The rule is "preserve history": both sides are
 * kept, the conflict is surfaced, and a human chooses.
 */
data class ConflictRecord(
    val clientId: String,
    val entityType: String,
    val language: String,
    val clientValue: String,
    val serverValue: String,
    val reason: String,
)

data class SyncResponse(
    val serverTime: String,
    val minClientVersion: Int,
    val accepted: List<String>,
    val serverChanges: List<SyncChange>,
    val conflicts: List<ConflictRecord>,
) {
    val hasBreakingChange: Boolean get() = minClientVersion > CURRENT_CLIENT_VERSION

    companion object {
        /**
         * Parse a server response, tolerating a newer server that adds fields
         * but refusing one that requires a newer client.
         */
        fun fromJson(json: JSONObject): SyncResponse {
            val acceptedJson = json.optJSONArray("accepted")
            val accepted = mutableListOf<String>()
            if (acceptedJson != null) {
                for (index in 0 until acceptedJson.length()) {
                    val item = acceptedJson.optJSONObject(index)
                    if (item != null) accepted += item.optString("client_id")
                }
            }

            val changesJson = json.optJSONArray("server_changes")
            val changes = mutableListOf<SyncChange>()
            if (changesJson != null) {
                for (index in 0 until changesJson.length()) {
                    changesJson.optJSONObject(index)?.let { changes += SyncChange.fromJson(it) }
                }
            }

            val conflictsJson = json.optJSONArray("conflicts")
            val conflicts = mutableListOf<ConflictRecord>()
            if (conflictsJson != null) {
                for (index in 0 until conflictsJson.length()) {
                    val item = conflictsJson.optJSONObject(index) ?: continue
                    conflicts += ConflictRecord(
                        clientId = item.optString("client_id"),
                        entityType = item.optString("entity_type"),
                        language = item.optString("language"),
                        clientValue = item.optString("client_value"),
                        serverValue = item.optString("server_value"),
                        reason = item.optString("reason"),
                    )
                }
            }

            return SyncResponse(
                serverTime = json.optString("server_time"),
                minClientVersion = json.optInt("min_client_version", CURRENT_CLIENT_VERSION),
                accepted = accepted,
                serverChanges = changes,
                conflicts = conflicts,
            )
        }
    }
}

/** Entity kinds the contract understands. Unknown kinds are rejected server-side. */
object EntityType {
    const val LESSON_PROGRESS = "lesson_progress"
    const val EXERCISE_ATTEMPT = "exercise_attempt"
    const val PROJECT_MILESTONE = "project_milestone"
    const val REVIEW = "review"

    val ALL = setOf(LESSON_PROGRESS, EXERCISE_ATTEMPT, PROJECT_MILESTONE, REVIEW)
}