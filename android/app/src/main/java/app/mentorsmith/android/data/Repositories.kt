package app.mentorsmith.android.data

import android.content.Context
import app.mentorsmith.android.data.local.AppSettingEntity
import app.mentorsmith.android.data.local.ExerciseAttemptEntity
import app.mentorsmith.android.data.local.LessonProgressEntity
import app.mentorsmith.android.data.local.MentorDatabase
import app.mentorsmith.android.data.local.ProjectMilestoneEntity
import app.mentorsmith.android.data.local.ReviewEntity
import app.mentorsmith.android.data.local.SyncQueueEntity
import app.mentorsmith.android.data.local.SyncState
import app.mentorsmith.android.data.remote.EntityType
import app.mentorsmith.android.data.remote.SyncChange
import app.mentorsmith.android.data.remote.SyncClient
import app.mentorsmith.android.domain.Concept
import app.mentorsmith.android.domain.Curriculum
import app.mentorsmith.android.domain.CurriculumFormat
import app.mentorsmith.android.domain.CurriculumFormatException
import app.mentorsmith.android.domain.CurriculumParser
import app.mentorsmith.android.domain.Exercise
import app.mentorsmith.android.domain.Lesson
import app.mentorsmith.android.domain.Mastery
import app.mentorsmith.android.domain.Project
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.withContext
import org.json.JSONObject

/** Fixed timestamp helper so records are comparable across devices. */
object Timestamps {
    fun now(): String = java.time.Instant.now().truncatedTo(java.time.temporal.ChronoUnit.SECONDS).toString()
}

/**
 * Loads the bundled curriculum from assets.
 *
 * Content is shipped with the app, so lessons, quizzes and revision work with
 * no network at all. Android never executes code: that stays on Linux.
 */
class CurriculumRepository(private val context: Context) {

    private val cache = mutableMapOf<String, Curriculum>()

    suspend fun load(language: String): Curriculum = withContext(Dispatchers.IO) {
        cache[language] ?: synchronized(cache) {
            cache[language] ?: readAsset(language).also { cache[language] = it }
        }
    }

    /** Languages that actually have bundled content, and load correctly. */
    suspend fun availableLanguages(): List<String> = CurriculumFormat.LANGUAGES.filter { language ->
        try {
            load(language)
            true
        } catch (_: Exception) {
            false
        }
    }

    private fun readAsset(language: String): Curriculum {
        val path = "curriculum/$language.json"
        val json = try {
            context.assets.open(path).bufferedReader().use { it.readText() }
        } catch (error: Exception) {
            throw CurriculumFormatException("bundled curriculum missing: $path")
        }
        return CurriculumParser.parse(json)
    }
}

/**
 * Progress, always local first.
 *
 * Nothing here talks to the network. Writes land in Room immediately and are
 * queued for sync; a row is only marked `synced` once the server has confirmed
 * it, so the UI never claims more than it knows.
 */
class ProgressRepository(private val database: MentorDatabase) {

    private val progress = database.progressDao()
    private val sync = database.syncDao()

    // ---- observation -------------------------------------------------

    fun completedLessons(language: String): Flow<List<LessonProgressEntity>> =
        progress.observeCompletedLessons(language)

    fun attempts(language: String, limit: Int = 200): Flow<List<ExerciseAttemptEntity>> =
        progress.observeRecentAttempts(language, limit)

    fun correctCount(language: String): Flow<Int> = progress.observeCorrectCount(language)
    fun hintsUsed(language: String): Flow<Int> = progress.observeHintsUsed(language)
    fun independentCount(language: String): Flow<Int> = progress.observeIndependentCount(language)
    fun errorCategories(language: String) = progress.observeErrorCategories(language)
    fun openReviews(language: String): Flow<List<ReviewEntity>> =
        progress.observeOpenReviews(language)
    fun milestones(language: String): Flow<List<ProjectMilestoneEntity>> =
        progress.observeMilestones(language)

    /**
     * Mastery for every concept, computed from graded attempts only.
     *
     * Lesson completion is deliberately excluded: reading a lesson is not
     * evidence of understanding.
     */
    suspend fun assessments(curriculum: Curriculum, language: String):
        Map<String, Mastery.Assessment> {
        val result = mutableMapOf<String, Mastery.Assessment>()
        curriculum.concepts.forEach { concept ->
            val records = progress.attemptsForConcept(language, concept.id).map {
                Mastery.AttemptRecord(
                    id = it.id,
                    exerciseType = it.exerciseType,
                    correct = it.correct,
                    hintsUsed = it.hintsUsed,
                    errorCategory = it.errorCategory,
                    novel = it.novel,
                )
            }
            result[concept.id] = Mastery.assess(concept.id, Mastery.evidenceFrom(records))
        }
        return result
    }

    /** Prerequisites of each concept that are not yet strong. */
    fun blockingPrerequisites(
        curriculum: Curriculum,
        assessments: Map<String, Mastery.Assessment>,
    ): Map<String, List<String>> {
        val mastered = assessments.filterValues { it.isMastered }.keys
        return curriculum.concepts.associate { concept ->
            concept.id to concept.prerequisites.filterNot { it in mastered }
        }
    }

    // ---- writes ------------------------------------------------------

    suspend fun markLessonComplete(lessonId: String, language: String) {
        val clientId = java.util.UUID.randomUUID().toString()
        val completedAt = Timestamps.now()
        progress.upsertLessonProgress(
            LessonProgressEntity(
                lessonId = lessonId,
                language = language,
                completedAt = completedAt,
                syncState = SyncState.PENDING,
            )
        )
        enqueue(
            entityType = EntityType.LESSON_PROGRESS,
            entityId = clientId,
            language = language,
            payload = mapOf(
                "lesson_id" to lessonId,
                "completed_at" to completedAt,
            ),
            clientId = clientId,
        )
    }

    /**
     * Record a graded attempt.
     *
     * `independent` is false once hints or escalation were needed, because
     * that distinction is what makes the mastery label meaningful.
     */
    suspend fun recordAttempt(
        lessonId: String,
        exercise: Exercise,
        language: String,
        correct: Boolean,
        hintsUsed: Int,
        escalated: Boolean,
        errorCategory: String = "",
        grade: String = "",
        source: String = "",
    ): Long {
        val independent = correct && hintsUsed == 0 && !escalated
        val clientId = java.util.UUID.randomUUID().toString()
        val createdAt = Timestamps.now()

        val id = progress.insertAttempt(
            ExerciseAttemptEntity(
                lessonId = lessonId,
                exerciseId = exercise.id,
                language = language,
                conceptId = exercise.conceptId,
                exerciseType = exercise.type,
                source = source,
                correct = correct,
                hintsUsed = hintsUsed,
                independent = independent,
                errorCategory = errorCategory,
                grade = grade,
                novel = exercise.novel,
                gradedBy = exercise.gradedBy,
                createdAt = createdAt,
                clientId = clientId,
                syncState = SyncState.PENDING,
            )
        )

        enqueue(
            entityType = EntityType.EXERCISE_ATTEMPT,
            entityId = clientId,
            language = language,
            payload = mapOf(
                "exercise_id" to exercise.id,
                "concept_id" to exercise.conceptId,
                "lesson_id" to lessonId,
                "exercise_type" to exercise.type,
                "correct" to correct.toString(),
                "hints_used" to hintsUsed.toString(),
                "independent" to independent.toString(),
                "error_category" to errorCategory,
                "novel" to exercise.novel.toString(),
                "graded_by" to exercise.gradedBy,
                "created_at" to createdAt,
            ),
            clientId = clientId,
        )
        return id
    }

    suspend fun updateMilestone(
        language: String,
        milestone: ProjectMilestoneEntity,
        status: String,
        notes: String,
        neededSubstantialHelp: Boolean,
    ) {
        val clientId = milestone.clientId
        val updatedAt = Timestamps.now()
        progress.upsertMilestone(
            milestone.copy(
                status = status,
                notes = notes,
                neededSubstantialHelp = neededSubstantialHelp,
                updatedAt = updatedAt,
                syncState = SyncState.PENDING,
            )
        )
        enqueue(
            entityType = EntityType.PROJECT_MILESTONE,
            entityId = clientId,
            language = language,
            payload = mapOf(
                "project_id" to milestone.projectId,
                "ordinal" to milestone.ordinal.toString(),
                "title" to milestone.title,
                "status" to status,
                "notes" to notes,
                "needed_substantial_help" to neededSubstantialHelp.toString(),
                "updated_at" to updatedAt,
            ),
            clientId = clientId,
        )
    }

    /** Flag a concept for review. Deduplicated on (concept, language, open). */
    suspend fun flagForReview(concept: Concept, language: String, reason: String, evidence: String) {
        if (progress.existingOpenReview(language, concept.id) != null) return
        val clientId = java.util.UUID.randomUUID().toString()
        val createdAt = Timestamps.now()
        progress.insertReview(
            ReviewEntity(
                conceptId = concept.id,
                language = language,
                reason = reason,
                evidence = evidence,
                createdAt = createdAt,
                clientId = clientId,
                syncState = SyncState.PENDING,
            )
        )
        enqueue(
            entityType = EntityType.REVIEW,
            entityId = clientId,
            language = language,
            payload = mapOf(
                "concept_id" to concept.id,
                "reason" to reason,
                "evidence" to evidence,
                "created_at" to createdAt,
            ),
            clientId = clientId,
        )
    }

    private suspend fun enqueue(
        entityType: String,
        entityId: String,
        language: String,
        payload: Map<String, String>,
        clientId: String,
    ) {
        sync.enqueue(
            SyncQueueEntity(
                entityType = entityType,
                entityId = entityId,
                language = language,
                operation = "upsert",
                payload = JSONObject(payload).toString(),
                createdAt = Timestamps.now(),
            )
        )
    }
}

/**
 * Drains the offline queue.
 *
 * Rules that matter:
 * * A row is `synced` only after the server names it in `accepted`.
 * * A failure increments an attempt count and records the reason; it never
 *   discards the change.
 * * A conflict is surfaced, never auto-resolved.
 */
class SyncRepository(
    private val database: MentorDatabase,
    private val client: SyncClient,
) {

    private val sync = database.syncDao()

    fun pendingCount(): Flow<Int> = sync.observePendingCount()
    fun conflicts() = sync.observeConflicts()

    sealed class Outcome {
        data class Ok(val accepted: Int, val pulled: Int, val conflicts: Int) : Outcome()
        data class Failed(val message: String) : Outcome()
        object Offline : Outcome()
    }

    suspend fun push(): Outcome {
        val queued = sync.readyToSend()
        if (queued.isEmpty()) return Outcome.Ok(0, 0, 0)

        val changes = queued.map { row ->
            SyncChange(
                clientId = row.entityId,
                entityType = row.entityType,
                operation = row.operation,
                language = row.language,
                updatedAt = row.createdAt,
                payload = JSONObject(row.payload).toStringMap(),
            )
        }

        return when (val result = client.sync(changes = changes)) {
            is SyncClient.Result.Success -> {
                val response = result.response
                val accepted = response.accepted.toSet()
                // Conflicts are keyed by client_id, which is queue.entityId.
                val conflicted = response.conflicts.map { it.clientId }.toSet()

                queued.forEach { row ->
                    when {
                        row.entityId in accepted -> sync.remove(row.id)
                        row.entityId in conflicted ->
                            sync.markResult(row.id, SyncState.CONFLICT, "diverged from server")
                        else ->
                            sync.markResult(row.id, SyncState.FAILED, "not acknowledged")
                    }
                }
                Outcome.Ok(
                    accepted = response.accepted.size,
                    pulled = response.serverChanges.size,
                    conflicts = response.conflicts.size,
                )
            }
            is SyncClient.Result.Failure -> {
                // Keep the queued changes so nothing is lost, and record why.
                queued.forEach { row ->
                    sync.markResult(row.id, SyncState.FAILED, result.message)
                }
                Outcome.Failed(result.message)
            }
            SyncClient.Result.NotConfigured -> Outcome.Offline
        }
    }
}

/** Flatten a JSON object into a plain string map for the wire format. */
private fun JSONObject.toStringMap(): Map<String, String> =
    keys().asSequence().associateWith { optString(it) }