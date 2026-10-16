package app.mentorsmith.android.domain

/**
 * Normalises program output for comparison.
 *
 * Mirrors the desktop's rule exactly, so the two never disagree about whether
 * an answer was right: trailing whitespace on each line is ignored, and a
 * missing final newline is not a wrong answer.
 *
 * This lives in the domain package because it is a rule about *output*, not
 * about presentation.
 */
fun normalise(text: String): String =
    text.replace("\r\n", "\n").lines().joinToString("\n") { it.trimEnd() }.trim()

/** Whether an actual output matches what was expected. */
fun outputsMatch(actual: String, expected: String): Boolean =
    normalise(actual) == normalise(expected)