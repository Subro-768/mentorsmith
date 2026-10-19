#!/usr/bin/env python3
"""Generate the Android colour palette from the desktop one.

The two palettes used to be maintained by hand, independently, and had drifted
into looking like different products: the desktop is an amber-on-near-black
theme, while the Android build carried VS Code Dark+ (#1E1E1E, #4FC1FF,
#D4D4D4) under a comment claiming it was "the same palette the desktop uses".

Hand-maintained copies drift. So the Kotlin file is *generated* from
``mentorsmith.ui.theme._PALETTES`` and a test asserts the checked-in file still
matches, which turns "someone changed one and forgot the other" into a failing
test rather than a visual discrepancy nobody notices until they open the app.

Usage::

    python3 tools/export_theme.py            # rewrite the Kotlin file
    python3 tools/export_theme.py --check    # fail if it is out of date

Only the colours that Compose Material 3 has a slot for are mapped into
``ColorScheme``. The rest are exposed through :obj:`MentorColors` for screens
that need them, named identically to the Python token so the correspondence is
obvious.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mentorsmith.ui import theme  # noqa: E402

TARGET = (
    ROOT / "android" / "app" / "src" / "main" / "java" / "app" / "mentorsmith"
    / "android" / "ui" / "theme" / "Theme.kt"
)

#: Python token -> Kotlin property name. Material 3's own names are used where
#: one exists, so the mapping reads as "this Material slot is that token".
SEMANTIC = {
    "ACCENT": "accent",
    "SUCCESS": "success",
    "WARNING": "warning",
    "ERROR": "error",
    "INFO": "info",
    "MUTED": "muted",
    "PLACEHOLDER": "placeholder",
    "BORDER": "border",
    "BORDER_SUB": "borderSub",
    "SURFACE_ALT": "surfaceAlt",
    "SURFACE_HOV": "surfaceHover",
    "CYAN": "highlight",
    "CYAN_LIGHT": "highlightLight",
    "ACCENT_LIGHT": "accentLight",
    "ACCENT_ALT": "accentDeep",
    "SUCCESS_BG": "successBg",
    "WARNING_BG": "warningBg",
    "ERROR_BG": "errorBg",
    "INFO_BG": "infoBg",
    "PRIMARY_HOVER_FG": "onAccentPressed",
}

HEADER = '''package app.mentorsmith.android.ui.theme

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
'''


def _argb(hex_colour: str) -> str:
    """'#e8650a' -> '0xFFE8650A' (Compose wants an opaque ARGB literal)."""
    value = hex_colour.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"expected a 6-digit hex colour, got {hex_colour!r}")
    return "0xFF" + value.upper()


def _scheme(name: str, palette: dict[str, str]) -> str:
    c = lambda token: f"Color({_argb(palette[token])})"  # noqa: E731
    return f"""
private val {name} = {'dark' if name == 'DarkColors' else 'light'}ColorScheme(
    primary = {c('ACCENT')},
    onPrimary = {c('ACCENT_TEXT')},
    primaryContainer = {c('SURFACE_HOV')},
    onPrimaryContainer = {c('ACCENT_TEXT')},
    secondary = {c('CYAN')},
    onSecondary = {c('BASE')},
    background = {c('BASE')},
    onBackground = {c('FOREGROUND')},
    surface = {c('SURFACE')},
    onSurface = {c('FOREGROUND')},
    surfaceVariant = {c('SURFACE_ALT')},
    onSurfaceVariant = {c('MUTED')},
    outline = {c('BORDER')},
    outlineVariant = {c('BORDER_SUB')},
    error = {c('ERROR')},
    onError = {c('ACCENT_TEXT')},
    errorContainer = {c('ERROR_BG')},
    onErrorContainer = {c('ERROR')},
)
"""


def _semantics() -> str:
    lines = [
        "/**",
        " * Semantic colours for panels the Material scheme has no slot for.",
        " *",
        " * Named after the Python token in `mentorsmith/ui/theme.py` so the two",
        " * can be matched up without reading either.",
        " *",
        " * These come from the *dark* palette, which is the default theme on both",
        " * platforms. Light mode reaches the Material scheme instead; screens that",
        " * need a semantic colour in light mode should read it off",
        " * `MaterialTheme.colorScheme`.",
        " */",
        "object MentorColors {",
    ]
    for token, prop in SEMANTIC.items():
        lines.append(f"    val {prop} = Color({_argb(theme._PALETTES['dark_orange'][token])})")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _composable() -> str:
    return '''
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
'''


def render() -> str:
    dark = theme._PALETTES["dark_orange"]
    light = theme._PALETTES["light"]
    return (
        HEADER
        + _scheme("DarkColors", dark)
        + _scheme("LightColors", light)
        + "\n"
        + _semantics()
        + _composable()
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the checked-in file differs from the source.",
    )
    args = parser.parse_args()

    generated = render()

    if args.check:
        if not TARGET.exists():
            print(f"{TARGET} does not exist", file=sys.stderr)
            return 1
        current = TARGET.read_text(encoding="utf-8")
        if current != generated:
            print(
                f"{TARGET.relative_to(ROOT)} is out of date with "
                f"mentorsmith/ui/theme.py.\n"
                f"Run: python3 tools/export_theme.py",
                file=sys.stderr,
            )
            return 1
        print(f"{TARGET.relative_to(ROOT)} is up to date")
        return 0

    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(generated, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)} "
          f"({len(generated.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())