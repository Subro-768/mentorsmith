package app.mentorsmith.android.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.room.Room
import app.mentorsmith.android.data.CurriculumRepository
import app.mentorsmith.android.data.ProgressRepository
import app.mentorsmith.android.data.SyncRepository
import app.mentorsmith.android.data.local.MentorDatabase
import app.mentorsmith.android.data.remote.SyncClient
import app.mentorsmith.android.domain.Concept
import app.mentorsmith.android.domain.Curriculum
import app.mentorsmith.android.domain.CurriculumFormat
import app.mentorsmith.android.domain.Mastery
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/** Where a screen should be, so navigation is one flat enum. */
enum class Screen(val title: String) {
    DASHBOARD("Dashboard"),
    CURRICULUM("Curriculum"),
    LESSON("Lesson"),
    QUIZ("Quiz"),
    PREDICT("Predict"),
    FIND_BUG("Find the bug"),
    REVISION("Revision"),
    PROJECTS("Projects"),
    HISTORY("History"),
    TUTOR("Tutor"),
    SETTINGS("Settings"),
}

/**
 * The single ViewModel.
 *
 * One ViewModel for the whole app is a deliberate simplification for this
 * size of project: the screens share almost all their state, and splitting it
 * would mean passing the same three objects through every navigation argument.
 */
class MentorViewModel(application: Application) : AndroidViewModel(application) {

    private val database: MentorDatabase = Room
        .databaseBuilder(application, MentorDatabase::class.java, MentorDatabase.NAME)
        .fallbackToDestructiveMigration()
        .build()

    private val curriculumRepository = CurriculumRepository(application)
    private val progressRepository = ProgressRepository(database)

    /**
     * Cached mirror of the saved sync URL.
     *
     * [SyncClient.baseUrlProvider] is a plain (non-suspend) lambda, but the
     * value lives in the database. A cached copy avoids blocking a network call
     * on a database read, and is refreshed whenever the setting changes.
     */
    @Volatile
    private var cachedSyncUrl: String? = null

    private val syncRepository = SyncRepository(
        database,
        SyncClient(baseUrlProvider = { cachedSyncUrl }),
    )

    private val _language = MutableStateFlow("cpp")
    val language: StateFlow<String> = _language.asStateFlow()

    private val _curriculum = MutableStateFlow<Curriculum?>(null)
    val curriculum: StateFlow<Curriculum?> = _curriculum.asStateFlow()

    private val _screen = MutableStateFlow(Screen.DASHBOARD)
    val screen: StateFlow<Screen> = _screen.asStateFlow()

    private val _selectedLessonId = MutableStateFlow<String?>(null)
    val selectedLessonId: StateFlow<String?> = _selectedLessonId.asStateFlow()

    private val _selectedExerciseId = MutableStateFlow<String?>(null)
    val selectedExerciseId: StateFlow<String?> = _selectedExerciseId.asStateFlow()

    private val _assessments = MutableStateFlow<Map<String, Mastery.Assessment>>(emptyMap())
    val assessments: StateFlow<Map<String, Mastery.Assessment>> = _assessments.asStateFlow()

    private val _completedLessons = MutableStateFlow<Set<String>>(emptySet())
    val completedLessons: StateFlow<Set<String>> = _completedLessons.asStateFlow()

    private val _statusMessage = MutableStateFlow<String>("")
    val statusMessage: StateFlow<String> = _statusMessage.asStateFlow()

    /**
     * Counts that are evidence, kept apart from things that are not.
     *
     * These follow the selected language, so switching tracks switches the
     * numbers rather than silently showing another language's totals.
     */
    val correctCount: StateFlow<Int> = _language
        .flatMapLatest { progressRepository.correctCount(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    val hintsUsed: StateFlow<Int> = _language
        .flatMapLatest { progressRepository.hintsUsed(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    val independentCount: StateFlow<Int> = _language
        .flatMapLatest { progressRepository.independentCount(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), 0)

    /** Attempts recorded for the current language, newest first. */
    val recentAttempts = _language
        .flatMapLatest { progressRepository.attempts(it) }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init {
        viewModelScope.launch {
            cachedSyncUrl = database.settingsDao()
                .get(SETTING_SYNC_URL)
                ?.takeIf { it.isNotBlank() }
        }
        loadLanguage("cpp")
        observeProgress()
    }

    private var progressJob: kotlinx.coroutines.Job? = null

    private fun observeProgress() {
        progressJob?.cancel()
        progressJob = viewModelScope.launch {
            progressRepository.completedLessons(language.value).collect { rows ->
                _completedLessons.value = rows.map { it.lessonId }.toSet()
            }
        }
    }

    fun setLanguage(next: String) {
        if (next == language.value) return
        _language.value = next
        loadLanguage(next)
        observeProgress()
    }

    private fun loadLanguage(next: String) = viewModelScope.launch {
        val loaded = runCatching { curriculumRepository.load(next) }.getOrNull()
        if (loaded == null) {
            _statusMessage.value = "No bundled curriculum for ${CurriculumFormat.label(next)}."
            return@launch
        }
        _curriculum.value = loaded
        refreshAssessments()
    }

    fun refreshAssessments() = viewModelScope.launch {
        val loaded = _curriculum.value ?: return@launch
        _assessments.value = progressRepository.assessments(loaded, language.value)
    }

    fun navigate(target: Screen) {
        _screen.value = target
    }

    fun openLesson(lessonId: String) {
        _selectedLessonId.value = lessonId
        _screen.value = Screen.LESSON
    }

    fun openExercise(exerciseId: String) {
        _selectedExerciseId.value = exerciseId
        val exercise = _curriculum.value?.exercises?.firstOrNull { it.id == exerciseId }
        val target = when (exercise?.type) {
            "predict-output" -> Screen.PREDICT
            "find-a-bug" -> Screen.FIND_BUG
            "explain-code" -> Screen.TUTOR
            else -> Screen.QUIZ
        }
        _screen.value = target
    }

    fun markLessonComplete(lessonId: String) = viewModelScope.launch {
        progressRepository.markLessonComplete(lessonId, language.value)
        _statusMessage.value = "Marked complete. Saved on this device."
    }

    fun recordAttempt(
        exerciseId: String,
        correct: Boolean,
        hintsUsed: Int,
        escalated: Boolean,
        errorCategory: String,
        grade: String,
    ) = viewModelScope.launch {
        val loaded = _curriculum.value ?: return@launch
        val exercise = loaded.exercises.firstOrNull { it.id == exerciseId } ?: return@launch
        progressRepository.recordAttempt(
            lessonId = exercise.lessonId,
            exercise = exercise,
            language = language.value,
            correct = correct,
            hintsUsed = hintsUsed,
            escalated = escalated,
            errorCategory = errorCategory,
            grade = grade,
        )
        refreshAssessments()
    }

    fun flagForReview(concept: Concept, reason: String) = viewModelScope.launch {
        progressRepository.flagForReview(concept, language.value, reason, "")
    }

    fun setSyncBaseUrl(url: String?) = viewModelScope.launch {
        val clean = url?.trim()?.takeIf { it.isNotEmpty() }
        cachedSyncUrl = clean
        if (clean == null) {
            database.settingsDao().remove(SETTING_SYNC_URL)
        } else {
            database.settingsDao().put(
                app.mentorsmith.android.data.local.AppSettingEntity(
                    key = SETTING_SYNC_URL,
                    value = clean,
                )
            )
        }
        _statusMessage.value = if (clean == null) {
            "Sync disabled. The app works fully offline."
        } else {
            "Sync endpoint saved."
        }
    }

    /** Push the offline queue. Never claims success without confirmation. */
    fun pushSync() = viewModelScope.launch {
        _statusMessage.value = when (val outcome = syncRepository.push()) {
            is SyncRepository.Outcome.Ok ->
                "Synced ${outcome.accepted} change(s), pulled ${outcome.pulled}. " +
                    (if (outcome.conflicts > 0) "${outcome.conflicts} conflict(s) to review." else "")
            is SyncRepository.Outcome.Failed -> "Sync failed: ${outcome.message}"
            SyncRepository.Outcome.Offline -> "No sync endpoint configured."
        }
    }

    companion object {
        const val SETTING_SYNC_URL = "sync_base_url"

        fun factory(application: Application): ViewModelProvider.Factory =
            object : ViewModelProvider.Factory {
                @Suppress("UNCHECKED_CAST")
                override fun <T : ViewModel> create(modelClass: Class<T>): T {
                    return MentorViewModel(application) as T
                }
            }
    }
}