package app.mentorsmith.android

import app.mentorsmith.android.domain.Curriculum
import app.mentorsmith.android.domain.CurriculumFormat
import app.mentorsmith.android.domain.CurriculumFormatException
import app.mentorsmith.android.domain.CurriculumParser
import app.mentorsmith.android.domain.Mastery
import app.mentorsmith.android.domain.normalise
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Curriculum parsing and validation. */
class CurriculumParserTest {

    private val minimalLesson = JSONObjectHelper.lesson("l1", "First", 1)
    private val minimalConcept = JSONObjectHelper.concept("c1", "Concept", "l1")
    private val minimalExercise = JSONObjectHelper.exercise("e1", "c1", "l1", "predict-output")

    @Test
    fun `parses a complete document`() {
        val curriculum = CurriculumParser.parse(
            """
            {
              "format_version": 1,
              "language": "cpp",
              "label": "C++",
              "lessons": [$minimalLesson],
              "concepts": [$minimalConcept],
              "exercises": [$minimalExercise],
              "projects": [],
              "comparisons": []
            }
            """.trimIndent()
        )
        assertEquals("cpp", curriculum.language)
        assertEquals("C++", curriculum.label)
        assertEquals(1, curriculum.lessons.size)
        assertEquals("First", curriculum.lessons.first().title)
        assertEquals(1, curriculum.exercises.size)
    }

    @Test
    fun `rejects a newer format version rather than misreading it`() {
        val failure = runCatching {
            CurriculumParser.parse("""{"format_version": 99, "language": "cpp"}""")
        }.exceptionOrNull()
        assertTrue(failure is CurriculumFormatException)
        assertTrue(failure!!.message!!.contains("newer"))
    }

    @Test
    fun `rejects a missing format version`() {
        val failure = runCatching {
            CurriculumParser.parse("""{"language": "cpp"}""")
        }.exceptionOrNull()
        assertTrue(failure is CurriculumFormatException)
    }

    @Test
    fun `rejects a concept pointing at an unknown lesson`() {
        val broken = JSONObjectHelper.concept("c9", "Bad", "missing-lesson")
        val failure = runCatching {
            CurriculumParser.parse(
                """{"format_version":1,"language":"cpp","concepts":[$broken],"lessons":[$minimalLesson]}"""
            )
        }.exceptionOrNull()
        assertTrue(failure is CurriculumFormatException)
        assertTrue(failure!!.message!!.contains("unknown lessons"))
    }

    @Test
    fun `rejects an exercise pointing at an unknown concept`() {
        val broken = JSONObjectHelper.exercise("e9", "ghost", "l1", "find-a-bug")
        val failure = runCatching {
            CurriculumParser.parse(
                """{"format_version":1,"language":"cpp","lessons":[$minimalLesson],
                    "concepts":[$minimalConcept],"exercises":[$broken]}"""
            )
        }.exceptionOrNull()
        assertTrue(failure is CurriculumFormatException)
        assertTrue(failure!!.message!!.contains("unknown concepts"))
    }

    @Test
    fun `rejects a dangling prerequisite`() {
        val broken = JSONObjectHelper.concept("c2", "Bad", "l1", prerequisites = listOf("ghost"))
        val failure = runCatching {
            CurriculumParser.parse(
                """{"format_version":1,"language":"cpp","lessons":[$minimalLesson],
                    "concepts":[$minimalConcept,$broken]}"""
            )
        }.exceptionOrNull()
        assertTrue(failure is CurriculumFormatException)
        assertTrue(failure!!.message!!.contains("require unknown"))
    }

    @Test
    fun `missing arrays are treated as empty rather than crashing`() {
        val curriculum = CurriculumParser.parse("""{"format_version":1,"language":"c"}""")
        assertTrue(curriculum.lessons.isEmpty())
        assertTrue(curriculum.exercises.isEmpty())
    }

    @Test
    fun `exercises carry their grading kind`() {
        val json = CurriculumParser.parse(
            """{"format_version":1,"language":"cpp","lessons":[$minimalLesson],
               "concepts":[$minimalConcept],
               "exercises":[${JSONObjectHelper.exercise("e2", "c1", "l1", "explain-code", gradedBy = "interpretive")}]}"""
        )
        assertTrue(json.exercises.first().isInterpretive)
    }
}

/**
 * The real bundled content must load.
 *
 * The asset lives in the APK, so this reads it from the test's working copy
 * under `src/main/assets`. That keeps the test honest about the shipped file
 * rather than about a hand-written fixture.
 */
class BundledCurriculumTest {

    private fun loadAsset(name: String): Curriculum {
        val path = "src/main/assets/curriculum/$name"
        val file = java.io.File(path)
        assertTrue("missing bundled asset: $path", file.exists())
        return CurriculumParser.parse(file.readText())
    }

    @Test
    fun `every bundled language parses`() {
        CurriculumFormat.LANGUAGES.forEach { language ->
            val curriculum = loadAsset("$language.json")
            assertTrue("$language has no lessons", curriculum.lessons.isNotEmpty())
            assertTrue("$language has no concepts", curriculum.concepts.isNotEmpty())
            assertTrue("$language has no exercises", curriculum.exercises.isNotEmpty())
        }
    }

    @Test
    fun `every lesson is complete`() {
        CurriculumFormat.LANGUAGES.forEach { language ->
            loadAsset("$language.json").lessons.forEach { lesson ->
                listOf(
                    "objectives", "explanation", "example",
                    "knowledge_checks", "exercise", "common_mistakes", "recap",
                ).forEach { section ->
                    assertTrue(
                        "$language/${lesson.id} is missing $section",
                        lesson.section(section).isNotBlank(),
                    )
                }
                assertTrue("$language/${lesson.id} has no starter code", lesson.starterCode.isNotBlank())
                assertTrue("$language/${lesson.id} has no checks", lesson.checks.isNotEmpty())
            }
        }
    }

    @Test
    fun `every concept has an exercise`() {
        CurriculumFormat.LANGUAGES.forEach { language ->
            val curriculum = loadAsset("$language.json")
            val uncovered = curriculum.conceptIds - curriculum.exercises.map { it.conceptId }.toSet()
            assertTrue("$language concepts without exercises: $uncovered", uncovered.isEmpty())
        }
    }

    @Test
    fun `the C plus plus track was not reduced`() {
        val cpp = loadAsset("cpp.json")
        // A floor, not a figure. The track has grown since this test was
        // written - it now carries the inheritance, operator-overloading and
        // virtual-function lessons from the OOP book - and a hard-coded
        // count only ever reports that someone forgot to update it.
        assertTrue(cpp.lessons.size >= 16)
    }

    @Test
    fun `prerequisite graphs are acyclic`() {
        CurriculumFormat.LANGUAGES.forEach { language ->
            val curriculum = loadAsset("$language.json")
            val visiting = mutableSetOf<String>()
            val done = mutableSetOf<String>()

            fun visit(id: String) {
                if (id in done) return
                assertTrue("cycle at $id", id !in visiting)
                visiting += id
                curriculum.concept(id)?.prerequisites?.forEach { visit(it) }
                visiting -= id
                done += id
            }
            curriculum.conceptIds.forEach { visit(it) }
        }
    }
}

/** Mastery must behave exactly as the desktop does, or the two devices disagree. */
class MasteryTest {

    private fun evidence(
        attempts: Int = 0,
        correct: Int = 0,
        hints: Int = 0,
        firstTry: Boolean = false,
        freeform: Int = 0,
        freeformCorrect: Int = 0,
        novel: Int = 0,
        errors: Map<String, Int> = emptyMap(),
    ) = Mastery.Evidence(
        attempts = attempts,
        correct = correct,
        hintsUsed = hints,
        firstAttemptCorrect = firstTry,
        freeformAttempts = freeform,
        freeformCorrect = freeformCorrect,
        novelAttempts = novel,
        errorCategories = errors,
    )

    @Test
    fun `no attempts is not started, not needs review`() {
        val result = Mastery.assess("c", Mastery.Evidence())
        assertEquals(Mastery.NOT_STARTED, result.label)
        assertEquals(0.0, result.score, 0.001)
        assertTrue(result.evidence.isNotEmpty())
    }

    @Test
    fun `one correct attempt is not strong`() {
        val result = Mastery.assess("c", evidence(attempts = 1, correct = 1, firstTry = true))
        assertFalse(result.isMastered)
    }

    @Test
    fun `consistent correct answers become strong`() {
        val result = Mastery.assess(
            "c",
            evidence(attempts = 4, correct = 4, firstTry = true),
        )
        assertEquals(Mastery.STRONG, result.label)
        assertTrue(result.isMastered)
    }

    @Test
    fun `a repeated error downgrades a strong label`() {
        val result = Mastery.assess(
            "c",
            evidence(attempts = 5, correct = 5, firstTry = true, errors = mapOf("off_by_one" to 3)),
        )
        assertEquals(Mastery.NEEDS_REVIEW, result.label)
        assertTrue(result.evidence.any { it.contains("repeating problem") })
    }

    @Test
    fun `two occurrences do not downgrade`() {
        val result = Mastery.assess(
            "c",
            evidence(attempts = 5, correct = 5, firstTry = true, errors = mapOf("off_by_one" to 2)),
        )
        assertEquals(Mastery.STRONG, result.label)
    }

    @Test
    fun `hints reduce confidence`() {
        val plain = Mastery.assess("c", evidence(attempts = 4, correct = 4, firstTry = true))
        val aided = Mastery.assess(
            "c",
            evidence(attempts = 4, correct = 4, firstTry = true, hints = 3),
        )
        assertTrue(aided.score < plain.score)
    }

    @Test
    fun `a failed explanation counts against mastery`() {
        val without = Mastery.assess("c", evidence(attempts = 4, correct = 4, firstTry = true))
        val withBad = Mastery.assess(
            "c",
            evidence(attempts = 4, correct = 4, firstTry = true, freeform = 2),
        )
        assertTrue(withBad.score < without.score)
    }

    @Test
    fun `score is clamped`() {
        val bad = Mastery.assess(
            "c",
            evidence(attempts = 10, correct = 0, hints = 50, freeform = 3),
        )
        assertTrue(bad.score >= 0.0)
        assertTrue(bad.score <= 1.0)
        assertEquals(0.0, bad.score, 0.001)
    }

    @Test
    fun `every label carries evidence`() {
        listOf(
            Mastery.Evidence(),
            evidence(attempts = 1, correct = 1, firstTry = true),
            evidence(attempts = 3, correct = 0),
            evidence(attempts = 4, correct = 3, firstTry = true),
        ).forEach { case ->
            val result = Mastery.assess("c", case)
            assertTrue("${result.label} has no evidence", result.evidence.isNotEmpty())
        }
    }

    @Test
    fun `evidence is folded from attempts oldest first`() {
        val records = listOf(
            Mastery.AttemptRecord(1, "predict-output", correct = false, hintsUsed = 0,
                errorCategory = "off_by_one", novel = false),
            Mastery.AttemptRecord(2, "find-a-bug", correct = true, hintsUsed = 0,
                errorCategory = "", novel = false),
        )
        val folded = Mastery.evidenceFrom(records)
        assertEquals(2, folded.attempts)
        assertEquals(1, folded.correct)
        assertFalse("the first attempt was wrong", folded.firstAttemptCorrect)
        assertEquals(1, folded.errorCategories["off_by_one"])
    }

    @Test
    fun `empty attempt history yields zero evidence`() {
        val folded = Mastery.evidenceFrom(emptyList())
        assertEquals(0, folded.attempts)
    }
}

/** Output comparison must match the desktop's tolerance. */
class OutputNormalisationTest {

    @Test
    fun `trailing whitespace is ignored`() {
        assertEquals("a\nb", normalise("a  \nb\n\n"))
    }

    @Test
    fun `a missing final newline is not a wrong answer`() {
        assertEquals(normalise("hi\n"), normalise("hi"))
        assertEquals(normalise("a\nb"), normalise("a\nb\n"))
    }

    @Test
    fun `carriage returns are normalised`() {
        assertEquals(normalise("a\nb"), normalise("a\r\nb\r\n"))
    }

    @Test
    fun `different content still differs`() {
        assertFalse(normalise("2.5") == normalise("2"))
    }
}

/** JSON fixtures, so the parser tests describe a document, not Kotlin code. */
object JSONObjectHelper {
    fun lesson(id: String, title: String, order: Int): String = """
        {"id":"$id","title":"$title","order":$order,
         "sections":{"objectives":"o","explanation":"e","example":"c",
                     "knowledge_checks":"Q: q\nA: a","exercise":"x","common_mistakes":"m","recap":"r"},
         "example_code":"int main(){}","starter_code":"int main(){}",
         "checks":[{"question":"q","answer":"a"}]}
    """.trimIndent()

    fun concept(
        id: String,
        title: String,
        lessonId: String,
        prerequisites: List<String> = emptyList(),
    ): String = """
        {"id":"$id","title":"$title","lesson_id":"$lessonId","summary":"s",
         "prerequisites":[${prerequisites.joinToString(",") { "\"$it\"" }}],
         "error_categories":[]}
    """.trimIndent()

    fun exercise(
        id: String,
        conceptId: String,
        lessonId: String,
        type: String,
        gradedBy: String = "deterministic",
    ): String = """
        {"id":"$id","concept_id":"$conceptId","lesson_id":"$lessonId","type":"$type",
         "title":"t","prompt":"p","code":"code","starter_code":"s",
         "expected_stdout":"ok\n","stdin":"","rubric":[],"novel":false,"tags":[],
         "graded_by":"$gradedBy"}
    """.trimIndent()
}