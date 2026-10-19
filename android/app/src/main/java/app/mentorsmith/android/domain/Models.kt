package app.mentorsmith.android.domain

import org.json.JSONArray
import org.json.JSONObject

/**
 * The documented curriculum format shared with the desktop app.
 *
 * This is the *only* thing shared between the two implementations. No Kotlin
 * code depends on the Python side, and the desktop does not depend on Kotlin —
 * they agree on this file format and nothing else.
 *
 * `FORMAT_VERSION` is checked on read. A file claiming a newer version is
 * rejected rather than misread, so an old app fails loudly instead of showing
 * half a lesson.
 */
object CurriculumFormat {
    const val SUPPORTED_VERSION = 1

    /** Languages the app knows, in display order. */
    val LANGUAGES = listOf("cpp", "python", "c", "javascript")

    fun label(language: String): String = when (language) {
        "cpp" -> "C++"
        "python" -> "Python"
        "c" -> "C"
        "javascript" -> "JavaScript"
        else -> language.replaceFirstChar { it.uppercase() }
    }
}

class CurriculumFormatException(message: String) : IllegalArgumentException(message)

data class KnowledgeCheck(val question: String, val answer: String)

data class Lesson(
    val id: String,
    val title: String,
    val order: Int,
    /**
     * Progression tier: "foundation", "core" or "advanced".
     *
     * Empty when the export does not say, which is the case for a curriculum
     * exported before tiers existed. The screen shows nothing in that case
     * rather than guessing.
     */
    val tier: String,
    val sections: Map<String, String>,
    val exampleCode: String,
    val starterCode: String,
    val checks: List<KnowledgeCheck>,
) {
    /** Section body, or an empty string when the lesson omits it. */
    fun section(name: String): String = sections[name].orEmpty()

    /** "3. Input and Output" */
    val displayTitle: String get() = "$order. $title"

    /** "Foundation", "Core" or "Advanced" - empty when unknown. */
    val tierLabel: String
        get() = when (tier) {
            "foundation" -> "Foundation"
            "core" -> "Core"
            "advanced" -> "Advanced"
            else -> ""
        }
}

data class Concept(
    val id: String,
    val title: String,
    val lessonId: String,
    val summary: String,
    val prerequisites: List<String>,
    val errorCategories: List<String>,
)

/**
 * One exercise.
 *
 * [gradedBy] is carried from the export so the UI can be honest about how an
 * answer will be judged. Android never *executes* code, so every code exercise
 * here is graded by comparing the learner's own predicted output, and
 * interpretive ones by the tutor. Neither is a claim that code ran.
 */
data class Exercise(
    val id: String,
    val conceptId: String,
    val lessonId: String,
    val type: String,
    val title: String,
    val prompt: String,
    val code: String,
    val starterCode: String,
    val expectedOutput: String,
    val stdin: String,
    val rubric: List<String>,
    val novel: Boolean,
    val tags: List<String>,
    val gradedBy: String,
) {
    val isInterpretive: Boolean get() = gradedBy == "interpretive"
    val initialCode: String get() = starterCode.ifBlank { code }
}

data class Milestone(
    val title: String,
    val requirements: String,
    val acceptanceCriteria: List<String>,
    val hint: String,
)

data class Project(
    val id: String,
    val title: String,
    val purpose: String,
    val concepts: List<String>,
    val difficulty: String,
    val milestones: List<Milestone>,
    val extensions: List<String>,
)

data class Comparison(
    val id: String,
    val concept: String,
    val languages: List<String>,
    val same: String,
    val different: List<String>,
    val snippets: List<String>,
    val question: String,
)

/** Everything bundled for one language. */
data class Curriculum(
    val formatVersion: Int,
    val language: String,
    val label: String,
    val lessons: List<Lesson>,
    val concepts: List<Concept>,
    val exercises: List<Exercise>,
    val projects: List<Project>,
    val comparisons: List<Comparison>,
) {
    val lessonIds: Set<String> get() = lessons.map { it.id }.toSet()
    val conceptIds: Set<String> get() = concepts.map { it.id }.toSet()

    fun lesson(id: String): Lesson? = lessons.firstOrNull { it.id == id }
    fun concept(id: String): Concept? = concepts.firstOrNull { it.id == id }
    fun exercisesFor(conceptId: String): List<Exercise> =
        exercises.filter { it.conceptId == conceptId }

    /** Validate internal consistency, mirroring the desktop loader. */
    fun validate() {
        val unknownLessons = concepts.mapNotNull { it.lessonId }.filterNot { it in lessonIds }
        if (unknownLessons.isNotEmpty()) {
            throw CurriculumFormatException(
                "concepts reference unknown lessons: ${unknownLessons.distinct()}"
            )
        }
        val unknownConcepts = exercises.mapNotNull { it.conceptId }.filterNot { it in conceptIds }
        if (unknownConcepts.isNotEmpty()) {
            throw CurriculumFormatException(
                "exercises reference unknown concepts: ${unknownConcepts.distinct()}"
            )
        }
        val unknownPrereqs = concepts.flatMap { it.prerequisites }.filterNot { it in conceptIds }
        if (unknownPrereqs.isNotEmpty()) {
            throw CurriculumFormatException(
                "concepts require unknown concepts: ${unknownPrereqs.distinct()}"
            )
        }
    }
}

/** Parses the bundled JSON. Pure functions, no Android types, so it unit-tests. */
object CurriculumParser {

    fun parse(json: String): Curriculum {
        val root = JSONObject(json)
        val version = root.optInt("format_version", 0)
        if (version > CurriculumFormat.SUPPORTED_VERSION) {
            // Refusing is safer than half-reading content written for a newer
            // version of the format.
            throw CurriculumFormatException(
                "curriculum format v$version is newer than this app supports " +
                    "(v${CurriculumFormat.SUPPORTED_VERSION}). Update MentorSmith."
            )
        }
        if (version < 1) {
            throw CurriculumFormatException("missing or invalid format_version")
        }

        val curriculum = Curriculum(
            formatVersion = version,
            language = root.getString("language"),
            label = root.optString("label", root.getString("language")),
            lessons = root.optJSONArray("lessons").mapObjects(::parseLesson),
            concepts = root.optJSONArray("concepts").mapObjects(::parseConcept),
            exercises = root.optJSONArray("exercises").mapObjects(::parseExercise),
            projects = root.optJSONArray("projects").mapObjects(::parseProject),
            comparisons = root.optJSONArray("comparisons").mapObjects(::parseComparison),
        )
        curriculum.validate()
        return curriculum
    }

    private fun parseLesson(json: JSONObject) = Lesson(
        id = json.getString("id"),
        title = json.getString("title"),
        order = json.optInt("order", 0),
        tier = json.optString("tier"),
        sections = json.optJSONObject("sections").toStringMap(),
        exampleCode = json.optString("example_code"),
        starterCode = json.optString("starter_code"),
        checks = json.optJSONArray("checks").mapObjects {
            KnowledgeCheck(it.getString("question"), it.optString("answer"))
        },
    )

    private fun parseConcept(json: JSONObject) = Concept(
        id = json.getString("id"),
        title = json.getString("title"),
        lessonId = json.optString("lesson_id"),
        summary = json.optString("summary"),
        prerequisites = json.optJSONArray("prerequisites").toStringList(),
        errorCategories = json.optJSONArray("error_categories").toStringList(),
    )

    private fun parseExercise(json: JSONObject) = Exercise(
        id = json.getString("id"),
        conceptId = json.getString("concept_id"),
        lessonId = json.optString("lesson_id"),
        type = json.getString("type"),
        title = json.optString("title"),
        prompt = json.optString("prompt"),
        code = json.optString("code"),
        starterCode = json.optString("starter_code"),
        expectedOutput = json.optString("expected_stdout"),
        stdin = json.optString("stdin"),
        rubric = json.optJSONArray("rubric").toStringList(),
        novel = json.optBoolean("novel", false),
        tags = json.optJSONArray("tags").toStringList(),
        gradedBy = json.optString("graded_by", "deterministic"),
    )

    private fun parseProject(json: JSONObject) = Project(
        id = json.getString("id"),
        title = json.getString("title"),
        purpose = json.optString("purpose"),
        concepts = json.optJSONArray("concepts").toStringList(),
        difficulty = json.optString("difficulty", "unknown"),
        milestones = json.optJSONArray("milestones").mapObjects {
            Milestone(
                title = it.optString("title"),
                requirements = it.optString("requirements"),
                acceptanceCriteria = it.optJSONArray("acceptance_criteria").toStringList(),
                hint = it.optString("hint"),
            )
        },
        extensions = json.optJSONArray("extensions").toStringList(),
    )

    private fun parseComparison(json: JSONObject) = Comparison(
        id = json.getString("id"),
        concept = json.optString("concept"),
        languages = json.optJSONArray("languages").toStringList(),
        same = json.optString("same"),
        different = json.optJSONArray("different").toStringList(),
        snippets = json.optJSONArray("snippets").toStringList(),
        question = json.optString("question"),
    )
}

// ---- small JSON helpers, null-safe throughout -------------------------

/** `optJSONArray` returns null when the key is absent; treat that as empty. */
private fun <T> JSONArray?.mapObjects(transform: (JSONObject) -> T): List<T> {
    if (this == null) return emptyList()
    return (0 until length()).mapNotNull { index -> optJSONObject(index)?.let(transform) }
}

private fun JSONArray?.toStringList(): List<String> {
    if (this == null) return emptyList()
    return (0 until length()).map { optString(it) }.filter { it.isNotBlank() }
}

private fun JSONObject?.toStringMap(): Map<String, String> {
    if (this == null) return emptyMap()
    return keys().asSequence().associateWith { optString(it) }
}