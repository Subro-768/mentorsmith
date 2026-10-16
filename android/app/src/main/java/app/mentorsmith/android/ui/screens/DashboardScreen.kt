package app.mentorsmith.android.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import app.mentorsmith.android.domain.CurriculumFormat
import app.mentorsmith.android.domain.Mastery
import app.mentorsmith.android.ui.MentorViewModel
import app.mentorsmith.android.ui.Screen
import app.mentorsmith.android.ui.theme.MentorColors

/**
 * The landing screen.
 *
 * Shows the suggested next activity with its reason, and is explicit about
 * what counts as evidence. Chat messages and time spent are deliberately not
 * shown here: on Android they would be tempting to display, and neither is
 * evidence of understanding.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(viewModel: MentorViewModel) {
    val curriculum by viewModel.curriculum.collectAsStateWithLifecycle()
    val language by viewModel.language.collectAsStateWithLifecycle()
    val assessments by viewModel.assessments.collectAsStateWithLifecycle()
    val completed by viewModel.completedLessons.collectAsStateWithLifecycle()
    val correct by viewModel.correctCount.collectAsStateWithLifecycle()
    val hints by viewModel.hintsUsed.collectAsStateWithLifecycle()
    val independent by viewModel.independentCount.collectAsStateWithLifecycle()

    Scaffold(
        topBar = { TopAppBar(title = { Text("MentorSmith") }) },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text(
                    "Read, quiz and revise here. Code runs on your Linux machine.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MentorColors.muted,
                )
            }

            item { LanguageSelector(viewModel, language) }

            val loaded = curriculum
            if (loaded == null) {
                item { Text("Loading curriculum…") }
                return@LazyColumn
            }

            // ---- next activity, with its reason ----
            item {
                val suggestion = suggestNext(loaded, assessments, language)
                Card(colors = CardDefaults.cardColors()) {
                    Column(Modifier.padding(16.dp)) {
                        Text("Suggested next", style = MaterialTheme.typography.titleMedium)
                        Spacer(Modifier.height(8.dp))
                        if (suggestion == null) {
                            Text(
                                "No graded attempts recorded yet, so there is no evidence " +
                                    "to base a suggestion on. Open a lesson and answer a " +
                                    "knowledge check.",
                                color = MentorColors.muted,
                            )
                        } else {
                            Text(suggestion.first, fontWeight = FontWeight.SemiBold)
                            Spacer(Modifier.height(4.dp))
                            Text("Why: ${suggestion.second}", color = MentorColors.muted)
                            Spacer(Modifier.height(12.dp))
                            Button(onClick = { viewModel.openExercise(suggestion.third) }) {
                                Text("Start this exercise")
                            }
                        }
                    }
                }
            }

            // ---- progress ----
            item {
                val strong = assessments.values.count { it.label == Mastery.STRONG }
                val percent = if (assessments.isEmpty()) 0
                else (strong * 100 / assessments.size)
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text(
                            "${CurriculumFormat.label(language)} progress",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        Spacer(Modifier.height(8.dp))
                        LinearProgressIndicator(
                            progress = { percent / 100f },
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "$strong of ${assessments.size} concepts strong · " +
                                "${loaded.lessons.count { it.id in completed }} of " +
                                "${loaded.lessons.size} lessons read",
                            color = MentorColors.muted,
                        )
                    }
                }
            }

            // ---- evidence counts ----
            item {
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text("Evidence", style = MaterialTheme.typography.titleMedium)
                        Spacer(Modifier.height(8.dp))
                        Text("Graded attempts correct: $correct")
                        Text("Solved without help: $independent")
                        Text("Hints used: $hints")
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Chat messages and time spent in the app are not counted here. " +
                                "Only graded attempts are.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MentorColors.muted,
                        )
                    }
                }
            }

            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { viewModel.navigate(Screen.CURRICULUM) }) {
                        Text("Curriculum")
                    }
                    OutlinedButton(onClick = { viewModel.navigate(Screen.REVISION) }) {
                        Text("Revision")
                    }
                    OutlinedButton(onClick = { viewModel.navigate(Screen.PROJECTS) }) {
                        Text("Projects")
                    }
                }
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LanguageSelector(viewModel: MentorViewModel, language: String) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        CurriculumFormat.LANGUAGES.forEach { id ->
            FilterChip(
                selected = id == language,
                onClick = { viewModel.setLanguage(id) },
                label = { Text(CurriculumFormat.label(id)) },
            )
        }
    }
}

/**
 * Pick the next exercise and explain why.
 *
 * Deliberately simple and deterministic: a concept that is weak wins, then one
 * that has only ever been answered correctly once, then something new.
 */
private fun suggestNext(
    curriculum: app.mentorsmith.android.domain.Curriculum,
    assessments: Map<String, Mastery.Assessment>,
    language: String,
): Triple<String, String, String>? {
    val mastered = assessments.filterValues { it.isMastered }.keys

    val weak = assessments.values
        .filter { it.label == Mastery.NEEDS_REVIEW && it.attempts > 0 }
        .minByOrNull { it.score }
    if (weak != null) {
        val exercise = curriculum.exercisesFor(weak.conceptId).firstOrNull()
        val reason = "${weak.attempts} graded attempts, ${"%.2f".format(weak.score)} score. " +
            weak.evidence.firstOrNull { it.isNotBlank() }.orEmpty()
        return Triple(
            exercise?.title ?: weak.conceptId,
            reason,
            exercise?.id ?: return null,
        )
    }

    val thin = assessments.values
        .filter { it.attempts == 1 }
        .minByOrNull { it.conceptId }
    if (thin != null) {
        val exercise = curriculum.exercisesFor(thin.conceptId).firstOrNull { it.novel }
            ?: curriculum.exercisesFor(thin.conceptId).firstOrNull()
        return Triple(
            exercise?.title ?: thin.conceptId,
            "Correct first time, but one answer is not enough to call it understood. " +
                "This is a different question.",
            exercise?.id ?: return null,
        )
    }

    // Prerequisites must be satisfied before new material is suggested.
    val next = curriculum.concepts.firstOrNull { concept ->
        concept.id !in mastered && concept.prerequisites.all { it in mastered }
    }
    val exercise = next?.let { curriculum.exercisesFor(it.id).firstOrNull() }
    return exercise?.let {
        Triple(
            it.title,
            "'${next.title}' has no attempts yet and its prerequisites are strong.",
            it.id,
        )
    }
}