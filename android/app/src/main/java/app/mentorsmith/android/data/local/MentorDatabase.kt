package app.mentorsmith.android.data.local

import androidx.room.Dao
import androidx.room.Database
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

@Dao
interface ProgressDao {

    // ---- lesson completion -------------------------------------------

    @Query(
        "SELECT * FROM lesson_progress WHERE language = :language " +
            "ORDER BY completedAt DESC"
    )
    fun observeCompletedLessons(language: String): Flow<List<LessonProgressEntity>>

    @Query(
        "SELECT COUNT(*) FROM lesson_progress WHERE language = :language"
    )
    fun observeCompletedCount(language: String): Flow<Int>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertLessonProgress(row: LessonProgressEntity)

    @Query(
        "DELETE FROM lesson_progress WHERE lessonId = :lessonId AND language = :language"
    )
    suspend fun deleteLessonProgress(lessonId: String, language: String)

    // ---- exercise attempts -------------------------------------------

    @Insert
    suspend fun insertAttempt(row: ExerciseAttemptEntity): Long

    @Query(
        "SELECT * FROM exercise_attempts WHERE language = :language AND conceptId = :conceptId " +
            "ORDER BY id DESC"
    )
    fun observeAttemptsForConcept(language: String, conceptId: String): Flow<List<ExerciseAttemptEntity>>

    @Query(
        "SELECT * FROM exercise_attempts WHERE language = :language ORDER BY id DESC LIMIT :limit"
    )
    fun observeRecentAttempts(language: String, limit: Int = 100): Flow<List<ExerciseAttemptEntity>>

    @Query(
        "SELECT * FROM exercise_attempts WHERE language = :language AND conceptId = :conceptId " +
            "ORDER BY id ASC"
    )
    suspend fun attemptsForConcept(language: String, conceptId: String): List<ExerciseAttemptEntity>

    @Query(
        "SELECT COUNT(*) FROM exercise_attempts WHERE language = :language AND correct = 1"
    )
    fun observeCorrectCount(language: String): Flow<Int>

    @Query(
        "SELECT COALESCE(SUM(hintsUsed), 0) FROM exercise_attempts WHERE language = :language"
    )
    fun observeHintsUsed(language: String): Flow<Int>

    @Query(
        "SELECT COUNT(*) FROM exercise_attempts WHERE language = :language " +
            "AND correct = 1 AND independent = 1"
    )
    fun observeIndependentCount(language: String): Flow<Int>

    @Query(
        "SELECT errorCategory, COUNT(*) AS n FROM exercise_attempts " +
            "WHERE language = :language AND errorCategory != '' " +
            "GROUP BY errorCategory ORDER BY n DESC"
    )
    fun observeErrorCategories(language: String): Flow<List<ErrorCategoryCount>>

    // ---- projects ----------------------------------------------------

    @Query(
        "SELECT * FROM project_milestones WHERE language = :language ORDER BY projectId, ordinal"
    )
    fun observeMilestones(language: String): Flow<List<ProjectMilestoneEntity>>

    @Query("SELECT * FROM project_milestones WHERE projectId = :projectId ORDER BY ordinal")
    fun observeMilestonesForProject(projectId: String): Flow<List<ProjectMilestoneEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertMilestone(row: ProjectMilestoneEntity)

    // ---- reviews -----------------------------------------------------

    @Query("SELECT * FROM reviews WHERE language = :language AND status = 'open' ORDER BY id DESC")
    fun observeOpenReviews(language: String): Flow<List<ReviewEntity>>

    @Query(
        "SELECT * FROM reviews WHERE language = :language AND conceptId = :conceptId " +
            "AND status = 'open' LIMIT 1"
    )
    suspend fun existingOpenReview(language: String, conceptId: String): ReviewEntity?

    @Insert
    suspend fun insertReview(row: ReviewEntity): Long

    @Query("UPDATE reviews SET status = :status, syncState = :syncState WHERE id = :id")
    suspend fun setReviewStatus(id: Long, status: String, syncState: String)
}

data class ErrorCategoryCount(val errorCategory: String, val n: Int)

@Dao
interface SyncDao {

    @Insert
    suspend fun enqueue(row: SyncQueueEntity): Long

    @Query("SELECT * FROM sync_queue WHERE syncState IN ('pending', 'failed') ORDER BY id ASC")
    suspend fun readyToSend(): List<SyncQueueEntity>

    @Query("SELECT COUNT(*) FROM sync_queue WHERE syncState = 'pending'")
    fun observePendingCount(): Flow<Int>

    @Query(
        "UPDATE sync_queue SET syncState = :state, lastError = :error, attempts = attempts + 1 " +
            "WHERE id = :id"
    )
    suspend fun markResult(id: Long, state: String, error: String)

    @Query("DELETE FROM sync_queue WHERE id = :id")
    suspend fun remove(id: Long)

    @Query("SELECT * FROM sync_queue WHERE syncState = 'conflict' ORDER BY id")
    fun observeConflicts(): Flow<List<SyncQueueEntity>>
}

@Dao
interface SettingsDao {

    @Query("SELECT value FROM app_settings WHERE key = :key")
    suspend fun get(key: String): String?

    @Query("SELECT value FROM app_settings WHERE key = :key")
    fun observe(key: String): Flow<String?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun put(row: AppSettingEntity)

    @Query("DELETE FROM app_settings WHERE key = :key")
    suspend fun remove(key: String)
}

/**
 * The local database.
 *
 * `exportSchema` is on so schemas land in `app/schemas/` and can be diffed in
 * review — a schema change should be a visible diff, not a surprise at runtime.
 */
@Database(
    entities = [
        LessonProgressEntity::class,
        ExerciseAttemptEntity::class,
        ProjectMilestoneEntity::class,
        ReviewEntity::class,
        AppSettingEntity::class,
        SyncQueueEntity::class,
    ],
    version = 1,
    exportSchema = true,
)
abstract class MentorDatabase : RoomDatabase() {
    abstract fun progressDao(): ProgressDao
    abstract fun syncDao(): SyncDao
    abstract fun settingsDao(): SettingsDao

    companion object {
        const val NAME = "mentorsmith.db"
    }
}