package app.mentorsmith.android.domain

/**
 * Mastery labels and the evidence behind them.
 *
 * This deliberately mirrors the desktop's rules so a learner sees the same
 * reasoning on both devices. Two rules from that design are preserved here
 * because they are easy to lose when porting:
 *
 * 1. A label is a **summary, not a measurement**, and it always ships with the
 *    counts that justify it.
 * 2. Chat message counts and time spent in the app are **not** evidence. Only
 *    graded attempts are.
 *
 * Scores are computed from recorded attempts, never from activity traces.
 */
object Mastery {

    const val NOT_STARTED = "not_started"
    const val NEEDS_REVIEW = "needs_review"
    const val DEVELOPING = "developing"
    const val STRONG = "strong"

    val LABEL_ORDER = listOf(NOT_STARTED, NEEDS_REVIEW, DEVELOPING, STRONG)

    val DESCRIPTIONS = mapOf(
        NOT_STARTED to "No graded attempts recorded yet.",
        NEEDS_REVIEW to "Attempted, but the evidence is weak or shows a repeated problem.",
        DEVELOPING to "Making real progress; some signals are mixed.",
        STRONG to "Consistent correct results across several attempts.",
    )

    /** One error category this many times forces a review flag. */
    const val REPEAT_ERROR_THRESHOLD = 3

    /** `strong` cannot be granted below this many graded attempts. */
    const val MIN_ATTEMPTS_FOR_STRONG = 2

    const val HINT_PENALTY = 0.10
    const val MAX_HINT_PENALTY = 0.30

    /** Aggregated evidence for one concept in one language. */
    data class Evidence(
        val attempts: Int = 0,
        val correct: Int = 0,
        val hintsUsed: Int = 0,
        val firstAttemptCorrect: Boolean = false,
        val freeformAttempts: Int = 0,
        val freeformCorrect: Int = 0,
        val novelAttempts: Int = 0,
        val errorCategories: Map<String, Int> = emptyMap(),
        val reviewAttempts: Int = 0,
    )

    data class Assessment(
        val conceptId: String,
        val label: String = NOT_STARTED,
        val score: Double = 0.0,
        val evidence: List<String> = emptyList(),
        val attempts: Int = 0,
    ) {
        val isMastered: Boolean
            get() = label == STRONG && attempts >= MIN_ATTEMPTS_FOR_STRONG

        /** One paragraph the learner can read and challenge. */
        fun explain(): String = buildString {
            append("$conceptId: $label (score ${"%.2f".format(score)})\n")
            evidence.forEach { append("  - $it\n") }
        }
    }

    fun assess(conceptId: String, evidence: Evidence): Assessment {
        val notes = mutableListOf<String>()

        if (evidence.attempts == 0) {
            return Assessment(
                conceptId = conceptId,
                label = NOT_STARTED,
                evidence = listOf(
                    "No graded attempts recorded. Completing a lesson does not " +
                        "count as evidence."
                ),
            )
        }

        val accuracy = evidence.correct.toDouble() / evidence.attempts
        var score = accuracy
        notes += "${evidence.correct} of ${evidence.attempts} graded attempts were " +
            "correct (${(accuracy * 100).toInt()}%)."

        if (evidence.firstAttemptCorrect) {
            score += 0.15
            notes += "The very first attempt was already correct."
        } else {
            notes += "The first attempt was wrong, so this concept needed practice."
        }

        if (evidence.freeformAttempts > 0) {
            if (evidence.freeformCorrect > 0) {
                score += 0.10
                notes += "You also explained a solution correctly in your own words."
            } else {
                score -= 0.15
                notes += "${evidence.freeformAttempts} free-form explanation " +
                    "attempt(s) were not judged correct. Code can work without " +
                    "being understood, so this counts against mastery."
            }
        }

        if (evidence.novelAttempts > 0) {
            score += 0.10
            notes += "Solved an unfamiliar variation, not just the worked example."
        }

        if (evidence.hintsUsed > 0) {
            val penalty = minOf(MAX_HINT_PENALTY, HINT_PENALTY * (evidence.hintsUsed - 1))
            score -= penalty
            notes += "${evidence.hintsUsed} hint(s) used, which reduces confidence " +
                "in independent understanding."
        } else {
            notes += "No hints were used on these attempts."
        }

        val repeated = evidence.errorCategories.filterValues { it >= REPEAT_ERROR_THRESHOLD }
        repeated.forEach { (category, count) ->
            notes += "'$category' came up $count times — a repeating problem, not a " +
                "one-off slip."
        }

        if (evidence.reviewAttempts > 0) {
            notes += "${evidence.reviewAttempts} of these were deliberate review attempts."
        }

        score = score.coerceIn(0.0, 1.0)

        var label = when {
            score >= 0.75 && evidence.attempts >= MIN_ATTEMPTS_FOR_STRONG -> STRONG
            score >= 0.45 -> DEVELOPING
            else -> NEEDS_REVIEW
        }

        // A recurring misunderstanding outweighs a good overall score.
        if (repeated.isNotEmpty() && (label == STRONG || label == DEVELOPING)) {
            label = NEEDS_REVIEW
            notes += "Downgraded from the score-based label because of a repeated " +
                "error category."
        }

        return Assessment(
            conceptId = conceptId,
            label = label,
            score = score,
            evidence = notes,
            attempts = evidence.attempts,
        )
    }

    /** Fold a list of recorded attempts into evidence for one concept. */
    fun evidenceFrom(attempts: List<AttemptRecord>): Evidence {
        if (attempts.isEmpty()) return Evidence()
        // Oldest first, so the "first attempt" is genuinely first.
        val ordered = attempts.sortedBy { it.id }
        val categories = mutableMapOf<String, Int>()
        var hints = 0
        var novel = 0
        var freeform = 0
        var freeformCorrect = 0
        var reviews = 0
        ordered.forEach { attempt ->
            if (attempt.errorCategory.isNotBlank()) {
                categories[attempt.errorCategory] =
                    (categories[attempt.errorCategory] ?: 0) + 1
            }
            hints += attempt.hintsUsed
            if (attempt.novel) novel += 1
            if (attempt.exerciseType == "explain-code") {
                freeform += 1
                if (attempt.correct) freeformCorrect += 1
            }
            if (attempt.exerciseType.startsWith(REVIEW_PREFIX)) reviews += 1
        }
        return Evidence(
            attempts = ordered.size,
            correct = ordered.count { it.correct },
            hintsUsed = hints,
            firstAttemptCorrect = ordered.first().correct,
            freeformAttempts = freeform,
            freeformCorrect = freeformCorrect,
            novelAttempts = novel,
            errorCategories = categories,
            reviewAttempts = reviews,
        )
    }

    const val REVIEW_PREFIX = "review:"

    /** The minimal attempt shape the mastery code needs. */
    data class AttemptRecord(
        val id: Long,
        val exerciseType: String,
        val correct: Boolean,
        val hintsUsed: Int,
        val errorCategory: String,
        val novel: Boolean,
    )
}