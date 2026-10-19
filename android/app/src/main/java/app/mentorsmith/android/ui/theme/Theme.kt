package app.mentorsmith.android.ui.theme

// GENERATED FILE - DO NOT EDIT BY HAND.
// Regenerate with:  python3 tools/export_theme.py
// Source of truth:  mentorsmith/ui/theme.py
//
// This file exists so the Android app and the desktop app are the same app.
// The palettes are the same numbers, not merely similar ones; a test asserts
// that, so this file cannot drift from the Python source.
//
// Dynamic colour is deliberately OFF by default. Wallpaper-derived colour
// would replace the brand palette wholesale, which is the opposite of matching
// the desktop.

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

private val DarkColors = darkColorScheme(
    primary = Color(0xFFE8650A),
    onPrimary = Color(0xFFFFF5EB),
    primaryContainer = Color(0xFF212121),
    onPrimaryContainer = Color(0xFFFFF5EB),
    secondary = Color(0xFFF0A500),
    onSecondary = Color(0xFF0A0A0B),
    background = Color(0xFF0A0A0B),
    onBackground = Color(0xFFF0ECE4),
    surface = Color(0xFF141414),
    onSurface = Color(0xFFF0ECE4),
    surfaceVariant = Color(0xFF1A1A1A),
    onSurfaceVariant = Color(0xFF7A7069),
    outline = Color(0xFF2E2E2E),
    outlineVariant = Color(0xFF1E1E1E),
    error = Color(0xFFF85149),
    onError = Color(0xFFFFF5EB),
    errorContainer = Color(0xFF2D1016),
    onErrorContainer = Color(0xFFF85149),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFFC44F00),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE8EAED),
    onPrimaryContainer = Color(0xFFFFFFFF),
    secondary = Color(0xFF0891B2),
    onSecondary = Color(0xFFFFFFFF),
    background = Color(0xFFFFFFFF),
    onBackground = Color(0xFF1A1A1A),
    surface = Color(0xFFF6F8FA),
    onSurface = Color(0xFF1A1A1A),
    surfaceVariant = Color(0xFFEEF0F2),
    onSurfaceVariant = Color(0xFF6E7781),
    outline = Color(0xFFD0D7DE),
    outlineVariant = Color(0xFFE0E4E8),
    error = Color(0xFFCF222E),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFFFEBE9),
    onErrorContainer = Color(0xFFCF222E),
)

/**
 * Semantic colours for panels the Material scheme has no slot for.
 *
 * Named after the Python token in `mentorsmith/ui/theme.py` so the two
 * can be matched up without reading either.
 *
 * These come from the *dark* palette, which is the default theme on both
 * platforms. Light mode reaches the Material scheme instead; screens that
 * need a semantic colour in light mode should read it off
 * `MaterialTheme.colorScheme`.
 */
object MentorColors {
    val accent = Color(0xFFE8650A)
    val success = Color(0xFF3FB950)
    val warning = Color(0xFFD29922)
    val error = Color(0xFFF85149)
    val info = Color(0xFF388BFD)
    val muted = Color(0xFF7A7069)
    val placeholder = Color(0xFF4A4540)
    val border = Color(0xFF2E2E2E)
    val borderSub = Color(0xFF1E1E1E)
    val surfaceAlt = Color(0xFF1A1A1A)
    val surfaceHover = Color(0xFF212121)
    val highlight = Color(0xFFF0A500)
    val highlightLight = Color(0xFFFFC840)
    val accentLight = Color(0xFFF4934A)
    val accentDeep = Color(0xFFC24D08)
    val successBg = Color(0xFF0F2A1A)
    val warningBg = Color(0xFF271F00)
    val errorBg = Color(0xFF2D1016)
    val infoBg = Color(0xFF051D4D)
    val onAccentPressed = Color(0xFF1A0800)
}

/**
 * Applies the MentorSmith theme.
 *
 * [darkTheme] follows the system setting, as Android users expect. Either way
 * the colours come from the desktop palette - the light scheme is the desktop's
 * `light` theme, not a generic Material light scheme.
 *
 * [dynamicColor] is off by default. Turning it on replaces the brand palette
 * with wallpaper-derived colours, which is the one thing that would stop the
 * two apps looking like one app.
 */
@Composable
fun MentorSmithTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colors = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context)
            else dynamicLightColorScheme(context)
        }
        darkTheme -> DarkColors
        else -> LightColors
    }
    MaterialTheme(colorScheme = colors, content = content)
}
