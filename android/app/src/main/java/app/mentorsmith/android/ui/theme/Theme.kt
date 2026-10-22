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
    primary = Color(0xFFC2803F),
    onPrimary = Color(0xFF201A12),
    primaryContainer = Color(0xFF2A2825),
    onPrimaryContainer = Color(0xFF201A12),
    secondary = Color(0xFF6FA8B4),
    onSecondary = Color(0xFF1A1917),
    background = Color(0xFF1A1917),
    onBackground = Color(0xFFD9D3C8),
    surface = Color(0xFF232220),
    onSurface = Color(0xFFD9D3C8),
    surfaceVariant = Color(0xFF1E1D1B),
    onSurfaceVariant = Color(0xFF968F84),
    outline = Color(0xFF302E2A),
    outlineVariant = Color(0xFF292722),
    error = Color(0xFFDC7C73),
    onError = Color(0xFF201A12),
    errorContainer = Color(0xFF33201E),
    onErrorContainer = Color(0xFFDC7C73),
)

private val LightColors = lightColorScheme(
    primary = Color(0xFFA05620),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFE2DDD4),
    onPrimaryContainer = Color(0xFFFFFFFF),
    secondary = Color(0xFF467F8C),
    onSecondary = Color(0xFFEFEBE4),
    background = Color(0xFFEFEBE4),
    onBackground = Color(0xFF38342D),
    surface = Color(0xFFFAF8F4),
    onSurface = Color(0xFF38342D),
    surfaceVariant = Color(0xFFE9E5DD),
    onSurfaceVariant = Color(0xFF6B655B),
    outline = Color(0xFFDBD4C7),
    outlineVariant = Color(0xFFE8E3DA),
    error = Color(0xFFAC5A53),
    onError = Color(0xFFFFFFFF),
    errorContainer = Color(0xFFF5E6E3),
    onErrorContainer = Color(0xFFAC5A53),
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
    val accent = Color(0xFFC2803F)
    val success = Color(0xFF7FB073)
    val warning = Color(0xFFD2A854)
    val error = Color(0xFFDC7C73)
    val info = Color(0xFF7BA2CE)
    val muted = Color(0xFF968F84)
    val placeholder = Color(0xFF6B655C)
    val border = Color(0xFF302E2A)
    val borderSub = Color(0xFF292722)
    val surfaceAlt = Color(0xFF1E1D1B)
    val surfaceHover = Color(0xFF2A2825)
    val highlight = Color(0xFF6FA8B4)
    val highlightLight = Color(0xFF96C4CD)
    val accentLight = Color(0xFFD29A5C)
    val accentDeep = Color(0xFFA3672C)
    val successBg = Color(0xFF24301F)
    val warningBg = Color(0xFF33291A)
    val errorBg = Color(0xFF33201E)
    val infoBg = Color(0xFF1E2836)
    val onAccentPressed = Color(0xFF201A12)
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
