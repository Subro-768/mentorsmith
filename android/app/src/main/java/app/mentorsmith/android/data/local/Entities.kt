package app.mentorsmith.android.data.local

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/**
 * Room entities mirroring the desktop schema.
 *
 * Two things are deliberate:
 *
 * * `language` is part of every key. Lesson and exercise ids repeat across
 *   tracks, and progress must never leak between them.
 * * Every mutable row carries `syncState`. The app is offline-first: a row is
 *   written locally first and only claims "synced" once the server has
 *   confirmed it. Nothing ever shows "synced" optimistically.
 */

/**
 * Where a row stands with respect to the sync server.
 *
 * [SYNCED] is only ever set after a server acknowledgement, never by the
 * client assuming success.
 */
object SyncState {
    /** Written on this device, never sent. */
    const val LOCAL = "local"

    /** Queued, not yet sent. */
    const val PENDING = "pending"

    /** Accepted by the server and confirmed. */
    const val SYNCED = "synced"

    /** The server has different data; a human decides. Never auto-resolved. */
    const val CONFLICT = "conflict"

    /** The send failed and can be retried. */
    const val FAILED = "failed"
}

@Entity(
    tableName = "lesson_progress",
    primaryKeys = ["lessonId", "language"],
)
data class LessonProgressEntity(
    val lessonId: String,
    val language: String,
    val completedAt: String,
    val syncState: String = SyncState.LOCAL,
)

@Entity(
    tableName = "exercise_attempts",
    indices = [
        Index(value = ["language", "conceptId"]),
        Index(value = ["syncState"]),
    ],
)
data class ExerciseAttemptEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val lessonId: String,
    val exerciseId: String,
    val language: String,
    val conceptId: String,
    val exerciseType: String,
    val source: String,
    val correct: Boolean,
    val hintsUsed: Int,
    /** False once the tutor escalated or several hints were needed. */
    val independent: Boolean,
    val errorCategory: String,
    val grade: String,
    val novel: Boolean,
    val gradedBy: String,
    /** ISO-8601, seconds precision. */
    val createdAt: String,
    /** Stable client id, so a re-send cannot duplicate on the server. */
    val clientId: String = java.util.UUID.randomUUID().toString(),
    val syncState: String = SyncState.PENDING,
)

@Entity(tableName = "project_milestones")
data class ProjectMilestoneEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val projectId: String,
    val language: String,
    val ordinal: Int,
    val title: String,
    val requirements: String,
    val acceptanceCriteria: String,
    val status: String = "pending",
    val notes: String = "",
    val neededSubstantialHelp: Boolean = false,
    val updatedAt: String,
    val clientId: String = java.util.UUID.randomUUID().toString(),
    val syncState: String = SyncState.PENDING,
)

@Entity(tableName = "reviews")
data class ReviewEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val conceptId: String,
    val language: String,
    val reason: String,
    val evidence: String,
    val status: String = "open",
    val createdAt: String,
    val clientId: String = java.util.UUID.randomUUID().toString(),
    val syncState: String = SyncState.PENDING,
)

/**
 * Settings that are safe to store locally.
 *
 * Deliberately no field for an API key or any other credential: the Android app
 * never holds one. See `SyncClient` for why.
 */
@Entity(tableName = "app_settings")
data class AppSettingEntity(
    @PrimaryKey val key: String,
    val value: String,
)

/**
 * A single outbound change, queued while offline.
 *
 * Kept as its own table rather than a column so a failed send can be retried
 * without touching the underlying rows.
 */
@Entity(tableName = "sync_queue", indices = [Index(value = ["syncState"])])
data class SyncQueueEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val entityType: String,
    val entityId: String,
    val language: String,
    val operation: String,
    val payload: String,
    val createdAt: String,
    val attempts: Int = 0,
    val lastError: String = "",
    val syncState: String = SyncState.PENDING,
)