package app.mentorsmith.android

import android.app.Application
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.BackHandler
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import app.mentorsmith.android.ui.MentorViewModel
import app.mentorsmith.android.ui.Screen
import app.mentorsmith.android.ui.screens.CurriculumScreen
import app.mentorsmith.android.ui.screens.DashboardScreen
import app.mentorsmith.android.ui.screens.FindBugScreen
import app.mentorsmith.android.ui.screens.HistoryScreen
import app.mentorsmith.android.ui.screens.LessonScreen
import app.mentorsmith.android.ui.screens.PredictScreen
import app.mentorsmith.android.ui.screens.ProjectsScreen
import app.mentorsmith.android.ui.screens.RevisionScreen
import app.mentorsmith.android.ui.screens.SettingsScreen
import app.mentorsmith.android.ui.screens.TutorScreen
import app.mentorsmith.android.ui.theme.MentorSmithTheme

/**
 * The single activity. Navigation is a small hand-rolled switch rather than
 * NavHost: there are eleven screens over one shared ViewModel, and a real
 * navigation graph would be more machinery than this needs.
 */
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MentorSmithTheme {
                MentorSmithApp()
            }
        }
    }
}

/** Screens reachable from the bottom bar. */
private val BOTTOM_BAR = listOf(
    Screen.DASHBOARD,
    Screen.CURRICULUM,
    Screen.REVISION,
    Screen.PROJECTS,
    Screen.SETTINGS,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MentorSmithApp() {
    val application = LocalContext.current.applicationContext as Application
    val viewModel: MentorViewModel = viewModel(factory = MentorViewModel.factory(application))
    val screen by viewModel.screen.collectAsStateWithLifecycle()

    // Android's back button maps onto "return to the dashboard", which is where
    // a user expects to land.
    BackHandler(enabled = screen !in BOTTOM_BAR) { viewModel.navigate(Screen.DASHBOARD) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("MentorSmith") }) },
        bottomBar = {
            NavigationBar {
                BOTTOM_BAR.forEach { target ->
                    NavigationBarItem(
                        selected = screen == target,
                        onClick = { viewModel.navigate(target) },
                        icon = { Text(iconFor(target)) },
                        label = { Text(target.title) },
                    )
                }
            }
        },
    ) { padding ->
        Box(Modifier.padding(padding)) {
            when (screen) {
                Screen.DASHBOARD -> DashboardScreen(viewModel)
                Screen.CURRICULUM -> CurriculumScreen(viewModel)
                Screen.LESSON -> LessonScreen(viewModel)
                Screen.QUIZ -> PredictScreen(viewModel)
                Screen.PREDICT -> PredictScreen(viewModel)
                Screen.FIND_BUG -> FindBugScreen(viewModel)
                Screen.REVISION -> RevisionScreen(viewModel)
                Screen.PROJECTS -> ProjectsScreen(viewModel)
                Screen.HISTORY -> HistoryScreen(viewModel)
                Screen.TUTOR -> TutorScreen(viewModel)
                Screen.SETTINGS -> SettingsScreen(viewModel)
            }
        }
    }
}

/** Emoji used for the bottom bar; keeps the APK free of image assets. */
private fun iconFor(screen: Screen): String = when (screen) {
    Screen.DASHBOARD -> "◧"
    Screen.CURRICULUM -> "☰"
    Screen.REVISION -> "↻"
    Screen.PROJECTS -> "▣"
    Screen.SETTINGS -> "⚙"
    else -> "•"
}