package app.mentorsmith.android.ui.screens

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
import androidx.compose.material3.Checkbox
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import kotlinx.coroutines.delay
import app.mentorsmith.android.focus.FocusMode
import app.mentorsmith.android.domain.Concept
import app.mentorsmith.android.domain.normalise
import app.mentorsmith.android.domain.Exercise
import app.mentorsmith.android.domain.Lesson
import app.mentorsmith.android.ui.MentorViewModel
import app.mentorsmith.android.ui.Screen
import app.mentorsmith.android.ui.theme.MentorColors

/** The curriculum list, with the label and its evidence behind it. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CurriculumScreen(viewModel: MentorViewModel) {
    val curriculum by viewModel.curriculum.collectAsStateWithLifecycle()
    val language by viewModel.language.collectAsStateWithLifecycle()
    val assessments by viewModel.assessments.collectAsStateWithLifecycle()
    val completed by viewModel.completedLessons.collectAsStateWithLifecycle()

    Scaffold(topBar = { TopAppBar(title = { Text("Curriculum") }) }) { padding ->
        val loaded = curriculum
        if (loaded == null) {
            Text("Loading…", Modifier.padding(padding))
            return@Scaffold
        }
        LazyColumn(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            items(loaded.lessons, key = { it.id }) { lesson ->
                LessonRow(
                    lesson = lesson,
                    label = assessments[loaded.concepts.firstOrNull { it.lessonId == lesson.id }?.id]?.label
                        ?: "not started",
                    done = lesson.id in completed,
                    onOpen = { viewModel.openLesson(lesson.id) },
                )
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

@Composable
private fun LessonRow(lesson: Lesson, label: String, done: Boolean, onOpen: () -> Unit) {
    Card(
        colors = CardDefaults.cardColors(),
        onClick = onOpen,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text(lesson.displayTitle, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(4.dp))
            Text(
                if (done) "✓ read · concepts: $label" else "○ not read · concepts: $label",
                style = MaterialTheme.typography.bodySmall,
                color = when (label) {
                    "strong" -> MentorColors.success
                    "needs_review" -> MentorColors.warning
                    else -> MentorColors.muted
                },
            )
        }
    }
}

/** Reading a lesson, plus its knowledge checks. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun LessonScreen(viewModel: MentorViewModel) {
    val curriculum by viewModel.curriculum.collectAsStateWithLifecycle()
    val lessonId by viewModel.selectedLessonId.collectAsStateWithLifecycle()

    Scaffold(topBar = { TopAppBar(title = { Text("Lesson") }) }) { padding ->
        val lesson = curriculum?.lesson(lessonId.orEmpty())
        if (lesson == null) {
            Text("No lesson selected", Modifier.padding(padding))
            return@Scaffold
        }
        LazyColumn(
            modifier = Modifier
                .padding(padding)
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item { Text(lesson.displayTitle, style = MaterialTheme.typography.headlineSmall) }

            // The tier badge, so the Android app says the same thing about
            // where the learner is as the desktop one does.
            if (lesson.tierLabel.isNotEmpty()) {
                item {
                    Text(
                        lesson.tierLabel.uppercase(),
                        style = MaterialTheme.typography.labelMedium,
                        color = when (lesson.tier) {
                            "advanced" -> MentorColors.accent
                            "core" -> MentorColors.info
                            else -> MentorColors.muted
                        },
                    )
                }
            }

            listOf(
                "objectives" to "Objectives",
                "explanation" to "Explanation",
                "example" to "Example",
                "exercise" to "Exercise",
                "common_mistakes" to "Common mistakes",
                "recap" to "Recap",
            ).forEach { (key, title) ->
                val body = lesson.section(key)
                if (body.isNotBlank()) {
                    item {
                        Card {
                            Column(Modifier.padding(16.dp)) {
                                Text(title, style = MaterialTheme.typography.titleMedium)
                                Spacer(Modifier.height(8.dp))
                                Text(body)
                            }
                        }
                    }
                }
            }

            if (lesson.checks.isNotEmpty()) {
                item {
                    Text("Knowledge checks", style = MaterialTheme.typography.titleMedium)
                }
                items(lesson.checks) { check ->
                    KnowledgeCheckCard(check.question, check.answer)
                }
            }

            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { viewModel.markLessonComplete(lesson.id) }) {
                        Text("Mark as read")
                    }
                    OutlinedButton(onClick = { viewModel.navigate(Screen.CURRICULUM) }) {
                        Text("Back")
                    }
                }
            }
            item {
                Text(
                    "Marking a lesson as read does NOT count as evidence of " +
                        "understanding. Only graded attempts do.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MentorColors.muted,
                )
            }
            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

@Composable
private fun KnowledgeCheckCard(question: String, answer: String) {
    var revealed by remember { mutableStateOf(false) }
    Card {
        Column(Modifier.padding(16.dp)) {
            Text(question)
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = { revealed = !revealed }) {
                Text(if (revealed) "Hide answer" else "Reveal answer")
            }
            if (revealed) Text("Answer: $answer", color = MentorColors.success)
        }
    }
}

/**
 * Predict-the-output.
 *
 * Android does **not** run the code. The learner reads it and commits to an
 * answer, which is the part that teaches prediction. The expected output is
 * revealed afterwards for self-checking; on Linux the real program runs.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PredictScreen(viewModel: MentorViewModel) {
    val curriculum by viewModel.curriculum.collectAsStateWithLifecycle()
    val exerciseId by viewModel.selectedExerciseId.collectAsStateWithLifecycle()
    val exercise = curriculum?.exercises?.firstOrNull { it.id == exerciseId }

    Scaffold(topBar = { TopAppBar(title = { Text("Predict the output") }) }) { padding ->
        if (exercise == null) {
            Text("No exercise selected", Modifier.padding(padding))
            return@Scaffold
        }
        var prediction by remember(exercise.id) { mutableStateOf("") }
        var submitted by remember(exercise.id) { mutableStateOf(false) }

        Column(
            Modifier
                .padding(padding)
                .padding(16.dp)
                .fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(exercise.title, style = MaterialTheme.typography.titleLarge)
            Text(exercise.prompt)

            CodeBlock(exercise.code)

            Text(
                "This app does not compile or run code — that happens on your Linux " +
                    "machine. Predict what it prints, then check yourself.",
                style = MaterialTheme.typography.bodySmall,
                color = MentorColors.muted,
            )

            OutlinedTextField(
                value = prediction,
                onValueChange = { prediction = it },
                label = { Text("Your predicted output") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 2,
            )

            Button(
                onClick = {
                    submitted = true
                    viewModel.recordAttempt(
                        exercise.id,
                        correct = normalise(prediction) == normalise(exercise.expectedOutput),
                        hintsUsed = 0,
                        escalated = false,
                        errorCategory = if (prediction.isBlank()) "no_prediction" else "",
                        grade = "",
                    )
                },
                enabled = !submitted,
            ) { Text(if (submitted) "Submitted" else "Check my answer") }

            if (submitted) {
                Card {
                    Column(Modifier.padding(16.dp)) {
                        val correct = normalise(prediction) == normalise(exercise.expectedOutput)
                        Text(
                            if (correct) "That matches." else "Not quite.",
                            color = if (correct) MentorColors.success else MentorColors.warning,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Spacer(Modifier.height(8.dp))
                        Text("Expected output:")
                        CodeBlock(exercise.expectedOutput)
                    }
                }
            }

            OutlinedButton(onClick = { viewModel.navigate(Screen.CURRICULUM) }) {
                Text("Back")
            }
        }
    }
}

/** Find-the-bug: read the code, choose the fix, self-check the reasoning. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FindBugScreen(viewModel: MentorViewModel) {
    val curriculum by viewModel.curriculum.collectAsStateWithLifecycle()
    val exerciseId by viewModel.selectedExerciseId.collectAsStateWithLifecycle()
    val exercise = curriculum?.exercises?.firstOrNull { it.id == exerciseId }

    Scaffold(topBar = { TopAppBar(title = { Text("Find the bug") }) }) { padding ->
        if (exercise == null) {
            Text("No exercise selected", Modifier.padding(padding))
            return@Scaffold
        }
        var fixed by remember(exercise.id) { mutableStateOf(false) }
        var explanation by remember(exercise.id) { mutableStateOf("") }

        Column(
            Modifier.padding(padding).padding(16.dp).fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(exercise.title, style = MaterialTheme.typography.titleLarge)
            Text(exercise.prompt)
            CodeBlock(exercise.code)

            OutlinedTextField(
                value = explanation,
                onValueChange = { explanation = it },
                label = { Text("What is wrong, and how did you spot it?") },
                modifier = Modifier.fillMaxWidth(),
                minLines = 3,
            )
            Text(
                "Write the fix on your Linux machine and press Run there. " +
                    "This app records your reasoning, not a compile.",
                style = MaterialTheme.typography.bodySmall,
                color = MentorColors.muted,
            )

            Button(onClick = {
                fixed = true
                viewModel.recordAttempt(
                    exercise.id,
                    correct = explanation.isNotBlank(),
                    hintsUsed = 0,
                    escalated = false,
                    errorCategory = "",
                    grade = explanation,
                )
            }, enabled = !fixed) { Text("Record my reasoning") }

            if (fixed && exercise.starterCode.isNotBlank()) {
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text("A fixed version to compare against", fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(8.dp))
                        CodeBlock(exercise.starterCode)
                    }
                }
            }
            OutlinedButton(onClick = { viewModel.navigate(Screen.CURRICULUM) }) { Text("Back") }
        }
    }
}

/** Revision: concepts with weak or repeated-error evidence, and why. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RevisionScreen(viewModel: MentorViewModel) {
    val curriculum by viewModel.curriculum.collectAsStateWithLifecycle()
    val assessments by viewModel.assessments.collectAsStateWithLifecycle()

    Scaffold(topBar = { TopAppBar(title = { Text("Revision") }) }) { padding ->
        val loaded = curriculum
        if (loaded == null) {
            Text("Loading…", Modifier.padding(padding)); return@Scaffold
        }
        val needsWork = loaded.concepts
            .map { it to assessments[it.id] }
            .filter { (_, assessment) ->
                assessment != null && assessment.attempts > 0 &&
                    assessment.label != app.mentorsmith.android.domain.Mastery.STRONG
            }
            .sortedBy { it.second?.score ?: 1.0 }

        LazyColumn(
            Modifier.padding(padding).fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Text(
                    "No review schedule can guarantee a concept is mastered. Only a " +
                        "new, unfamiliar problem shows whether it transferred.",
                    color = MentorColors.muted,
                )
            }
            if (needsWork.isEmpty()) {
                item {
                    Text(
                        "Nothing flagged. That is not the same as knowing everything — " +
                            "it means no recorded attempt looks weak yet."
                    )
                }
            }
            items(needsWork, key = { it.first.id }) { (concept, assessment) ->
                Card(
                    onClick = {
                        concept.exercisesFor(loaded).firstOrNull()?.let {
                            viewModel.openExercise(it.id)
                        }
                    },
                ) {
                    Column(Modifier.padding(16.dp)) {
                        Text(concept.title, fontWeight = FontWeight.SemiBold)
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "Recommended because: " +
                                (assessment?.evidence?.firstOrNull { it.isNotBlank() } ?: concept.summary),
                            color = MentorColors.warning,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        }
    }
}

private fun Concept.exercisesFor(curriculum: app.mentorsmith.android.domain.Curriculum) =
    curriculum.exercisesFor(id)

/** Project requirements and milestones. Progress is tracked on the phone too. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProjectsScreen(viewModel: MentorViewModel) {
    val curriculum by viewModel.curriculum.collectAsStateWithLifecycle()
    Scaffold(topBar = { TopAppBar(title = { Text("Projects") }) }) { padding ->
        val loaded = curriculum
        if (loaded == null) {
            Text("Loading…", Modifier.padding(padding)); return@Scaffold
        }
        LazyColumn(
            Modifier.padding(padding).fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            items(loaded.projects, key = { it.id }) { project ->
                Card {
                    Column(Modifier.padding(16.dp)) {
                        Text(project.title, style = MaterialTheme.typography.titleMedium)
                        Text(project.purpose, color = MentorColors.muted)
                        Spacer(Modifier.height(8.dp))
                        Text("Difficulty: ${project.difficulty}")
                        Spacer(Modifier.height(8.dp))
                        project.milestones.forEachIndexed { index, milestone ->
                            Text(
                                "${index + 1}. ${milestone.title}",
                                fontWeight = FontWeight.SemiBold,
                            )
                            Text(milestone.requirements)
                            milestone.acceptanceCriteria.forEach { criterion ->
                                Row(verticalAlignment = Alignment.Top) {
                                    Checkbox(checked = false, onCheckedChange = null)
                                    Text(criterion, Modifier.padding(top = 12.dp))
                                }
                            }
                            Spacer(Modifier.height(8.dp))
                        }
                        Text(
                            "Implement these on Linux. Record notes here when you " +
                                "have made progress.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MentorColors.muted,
                        )
                    }
                }
            }
            if (loaded.projects.isEmpty()) {
                item {
                    Text("Projects are generated for C++ only at the moment.")
                }
            }
        }
    }
}

/** Attempt history — the record of what was actually graded. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(viewModel: MentorViewModel) {
    val language by viewModel.language.collectAsStateWithLifecycle()
    val attempts by viewModel.recentAttempts.collectAsStateWithLifecycle()

    Scaffold(topBar = { TopAppBar(title = { Text("History") }) }) { padding ->
        LazyColumn(
            Modifier.padding(padding).fillMaxSize().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            item {
                Text(
                    "Graded attempts for this language. Reading a lesson or chatting " +
                        "is not recorded here, because neither is evidence.",
                    color = MentorColors.muted,
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            items(attempts, key = { it.id }) { attempt ->
                Card {
                    Row(
                        Modifier.padding(16.dp).fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Column {
                            Text(attempt.exerciseId, fontWeight = FontWeight.SemiBold)
                            Text(
                                "${attempt.exerciseType} · ${attempt.createdAt.take(10)}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MentorColors.muted,
                            )
                        }
                        Text(
                            if (attempt.correct) "correct" else "not correct",
                            color = if (attempt.correct) MentorColors.success else MentorColors.warning,
                        )
                    }
                }
            }
            if (attempts.isEmpty()) {
                item { Text("Nothing recorded yet.") }
            }
        }
    }
}

/**
 * Tutor chat.
 *
 * Disabled unless a sync backend is configured, because the app deliberately
 * holds no provider API key — an APK is not a secret. See `SyncClient`.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TutorScreen(viewModel: MentorViewModel) {
    Scaffold(topBar = { TopAppBar(title = { Text("Tutor") }) }) { padding ->
        Column(
            Modifier.padding(padding).padding(24.dp).fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Tutor chat is not available on this device yet.", fontWeight = FontWeight.SemiBold)
            Text(
                "MentorSmith deliberately does not ship an AI provider key inside the " +
                    "app: an APK can be downloaded and unpacked by anyone, so a key " +
                    "embedded in it is a published key. Tutor chat will be served by " +
                    "the optional backend, which holds the key on your server instead.",
                color = MentorColors.muted,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "Everything else works offline: lessons, quizzes, revision, projects " +
                    "and progress all run from bundled data.",
            )
            OutlinedButton(onClick = { viewModel.navigate(Screen.SETTINGS) }) {
                Text("Open settings")
            }
        }
    }
}

/**
 * The focus card.
 *
 * Android's answer to "stop all distracting apps" is **Do Not Disturb**:
 * it silences notifications from every other app, which removes the reason
 * to pick the phone up. No Android app may close another app, and this
 * screen says so rather than implying that it can.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FocusCard(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    var minutes by remember { mutableStateOf(45) }
    var running by remember { mutableStateOf(false) }
    var secondsLeft by remember { mutableStateOf(0) }
    var previousFilter by remember { mutableStateOf(-1) }
    var hasAccess by remember { mutableStateOf(FocusMode.hasPolicyAccess(context)) }

    LaunchedEffect(running) {
        if (!running) return@LaunchedEffect
        while (secondsLeft > 0) {
            delay(1000)
            secondsLeft -= 1
        }
        FocusMode.restoreFilter(context, previousFilter)
        running = false
    }

    Card(modifier = modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("Focus", style = MaterialTheme.typography.titleMedium)
            Text(
                "Turns on Do Not Disturb, so notifications from every other " +
                    "app stop arriving. Android does not let an app close " +
                    "another app, so this quiets the phone rather than " +
                    "killing what is on it.",
                color = MentorColors.muted,
                style = MaterialTheme.typography.bodySmall,
            )

            if (running) {
                val left = secondsLeft / 60
                val seconds = secondsLeft % 60
                Text(
                    "%02d:%02d left".format(left, seconds),
                    style = MaterialTheme.typography.headlineMedium,
                )
                OutlinedButton(
                    onClick = {
                        FocusMode.restoreFilter(context, previousFilter)
                        running = false
                    },
                ) { Text("End the session") }
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(25, 45, 60).forEach { option ->
                        if (option == minutes) {
                            Button(onClick = { minutes = option }) { Text("$option") }
                        } else {
                            OutlinedButton(onClick = { minutes = option }) {
                                Text("$option")
                            }
                        }
                    }
                }
                Text(
                    "minutes",
                    color = MentorColors.muted,
                    style = MaterialTheme.typography.bodySmall,
                )

                if (!hasAccess) {
                    Text(
                        "MentorSmith needs notification access to turn Do Not " +
                            "Disturb on. Android grants that to you, in the " +
                            "system settings - it cannot be taken by an app.",
                        color = MentorColors.warning,
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Button(
                        onClick = {
                            context.startActivity(FocusMode.policyAccessIntent())
                        },
                    ) { Text("Open notification access") }
                    TextButton(
                        onClick = { hasAccess = FocusMode.hasPolicyAccess(context) },
                    ) { Text("I have granted it - check again") }
                } else {
                    Button(
                        onClick = {
                            previousFilter = FocusMode.currentFilter(context)
                            if (FocusMode.setDoNotDisturb(context)) {
                                secondsLeft = minutes * 60
                                running = true
                            }
                        },
                    ) { Text("Start a $minutes minute session") }
                }
            }
        }
    }
}

/** Settings: sync endpoint, offline explanation, what is stored. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SettingsScreen(viewModel: MentorViewModel) {
    val status by viewModel.statusMessage.collectAsStateWithLifecycle()
    var url by remember { mutableStateOf("") }

    Scaffold(topBar = { TopAppBar(title = { Text("Settings") }) }) { padding ->
        Column(
            Modifier.padding(padding).padding(16.dp).fillMaxSize(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            FocusCard()

            Text("Sync (optional)", style = MaterialTheme.typography.titleMedium)
            Text(
                "Leave this blank to stay offline. Progress is always saved on this " +
                    "device first and only marked synced once the server confirms it.",
                color = MentorColors.muted,
                style = MaterialTheme.typography.bodySmall,
            )
            OutlinedTextField(
                value = url,
                onValueChange = { url = it },
                label = { Text("Sync base URL, e.g. http://10.0.2.2:8000") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { viewModel.setSyncBaseUrl(url.ifBlank { null }) }) {
                    Text("Save")
                }
                OutlinedButton(onClick = { viewModel.pushSync() }) { Text("Sync now") }
            }

            if (status.isNotBlank()) {
                Text(status, color = MentorColors.accent)
            }

            Spacer(Modifier.height(8.dp))
            Text("Privacy", style = MaterialTheme.typography.titleMedium)
            Text(
                "This app stores lesson progress, your attempts and settings in a local " +
                    "database. It holds no credentials of any kind. It does not upload " +
                    "your source files or project directories.",
                color = MentorColors.muted,
            )
            Spacer(Modifier.height(8.dp))
            Text("Offline behaviour", style = MaterialTheme.typography.titleMedium)
            Text(
                "Lessons, quizzes, revision, projects and progress are bundled with the " +
                    "app and work with no network. Sync is the only feature that needs one.",
                color = MentorColors.muted,
            )
            Spacer(Modifier.height(24.dp))
        }
    }
}

@Composable
private fun CodeBlock(code: String) {
    Card {
        Text(
            code.trimEnd(),
            fontFamily = FontFamily.Monospace,
            modifier = Modifier.padding(12.dp),
        )
    }
}