package app.mentorsmith.android.ui.theme

import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext

/**
 * The same palette the desktop uses, so the two feel like one app.
 *
 * Dynamic colour is enabled on Android 12+, but only when the system is in
 * dark mode: this app is dark-first, matching the desktop theme.
 */
private val Accent = Color(0xFF4FC1FF)
private val DarkBackground = Color(0xFF1E1E1E)
private val DarkSurface = Color(0xFF252526)
private val DarkSurfaceAlt = Color(0xFF2D2D30)
private val Foreground = Color(0xFFD4D4D4)
private val Muted = Color(0xFF9D9D9D)
private val Success = Color(0xFF6A9955)
private val Warning = Color(0xFFD7BA7D)
private val Error = Color(0xFFF14C4C)

/** Semantic colours used by the result and grading panels. */
object MentorColors {
    val success = Success
    val warning = Warning
    val error = Error
    val muted = Muted
    val accent = Accent
}

private val DarkColors = darkColorScheme(
    primary = Accent,
    onPrimary = Color(0xFF101010),
    background = DarkBackground,
    onBackground = Foreground,
    surface = DarkSurface,
    onSurface = Foreground,
    surfaceVariant = DarkSurfaceAlt,
    onSurfaceVariant = Muted,
    error = Error,
    outline = Color(0xFF3C3C3C),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFF0078D4),
    onPrimary = Color.White,
    background = Color(0xFFFAFAFA),
    onBackground = Color(0xFF1E1E1E),
    surface = Color.White,
    onSurface = Color(0xFF1E1E1E),
    surfaceVariant = Color(0xFFEEEEEE),
    onSurfaceVariant = Color(0xFF555555),
    error = Color(0xFFB00020),
)

@Composable
fun MentorSmithTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val context = LocalContext.current
    val colors = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S && darkTheme ->
            dynamicDarkColorScheme(context)
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.S ->
            dynamicLightColorScheme(context)
        darkTheme -> DarkColors
        else -> LightColors
    }
    MaterialTheme(colorScheme = colors, content = content)
}