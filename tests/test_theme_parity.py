"""The Android and desktop palettes must be the same colours.

The Android app shipped VS Code Dark+ (#1E1E1E, #4FC1FF, #D4D4D4) under a
comment claiming it was "the same palette the desktop uses". It was not - the
desktop is an amber-on-near-black theme. Nothing failed, because a colour
mismatch is not an error; it is only visible if you open both apps.

So the Kotlin file is now generated from ``mentorsmith/ui/theme.py`` and these
tests assert the checked-in file still matches. The failure mode changes from
"someone notices eventually" to "the build complains immediately".
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from mentorsmith.ui import theme

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

THEME_KT = (
    ROOT / "android" / "app" / "src" / "main" / "java" / "app" / "mentorsmith"
    / "android" / "ui" / "theme" / "Theme.kt"
)

COLOR_RE = re.compile(r"Color\(0x([0-9A-Fa-f]{8})\)")


def _kt_text() -> str:
    return THEME_KT.read_text(encoding="utf-8")


def _scheme_body(name: str) -> str:
    """The text of `private val <name> = ...ColorScheme(...)`."""
    text = _kt_text()
    start = text.index(f"private val {name}")
    end = text.index("\n)", start)
    return text[start:end]


# ======================================================================
# The generated file is current
# ======================================================================
class TestGeneratedFileIsCurrent:
    def test_the_checked_in_file_matches_the_generator(self) -> None:
        """The check that actually prevents drift."""
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "export_theme.py"), "--check"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            "Theme.kt is out of date with mentorsmith/ui/theme.py:\n"
            f"{result.stderr}\n"
            "Run: python3 tools/export_theme.py"
        )

    def test_the_file_says_it_is_generated(self) -> None:
        assert "GENERATED FILE - DO NOT EDIT BY HAND" in _kt_text()

    def test_it_names_the_command_to_regenerate(self) -> None:
        assert "python3 tools/export_theme.py" in _kt_text()


# ======================================================================
# Every colour is one the desktop actually uses
# ======================================================================
class TestColoursComeFromTheDesktop:
    def test_the_old_vs_code_palette_is_gone(self) -> None:
        """It was never the desktop theme; it just sat there looking plausible."""
        text = _kt_text()
        # #1E1E1E is deliberately absent from this list: it happens to be the
        # desktop's BORDER_SUB, so asserting on it would fail for the right
        # reason and look like a false alarm. Each of these appears nowhere in
        # any desktop palette.
        for hexcode, what in (
            ("252526", "surface"),
            ("4FC1FF", "accent"),
            ("D4D4D4", "foreground"),
            ("2D2D30", "surface variant"),
            ("9D9D9D", "muted"),
            ("3C3C3C", "outline"),
            ("101010", "onPrimary"),
        ):
            assert f"0xFF{hexcode}" not in text, (
                f"#{hexcode} ({what}) is VS Code Dark+, not a MentorSmith colour"
            )

    def test_none_of_the_vs_code_colours_exist_in_any_desktop_palette(self) -> None:
        """Guards the list above: if one of these ever joins the palette, the
        assertion is dropped rather than silently weakened."""
        every = {
            value.lstrip("#").upper()
            for palette in theme._PALETTES.values()
            for value in palette.values()
        }
        for hexcode in ("252526", "4FC1FF", "D4D4D4", "2D2D30", "9D9D9D", "3C3C3C"):
            assert hexcode not in every, (
                f"#{hexcode} is now a real desktop token; update this test"
            )

    def test_dark_primary_is_the_desktop_accent(self) -> None:
        assert theme._PALETTES["dark_orange"]["ACCENT"].lstrip("#").upper() == "E8650A"
        assert "primary = Color(0xFFE8650A)" in _scheme_body("DarkColors")

    def test_dark_background_is_the_desktop_base(self) -> None:
        assert "background = Color(0xFF0A0A0B)" in _scheme_body("DarkColors")

    def test_dark_surface_is_the_desktop_surface(self) -> None:
        assert "surface = Color(0xFF141414)" in _scheme_body("DarkColors")

    def test_dark_foreground_is_the_warm_desktop_white(self) -> None:
        """#f0ece4, not a neutral #ffffff - the desktop is deliberately warm."""
        assert "onBackground = Color(0xFFF0ECE4)" in _scheme_body("DarkColors")

    def test_muted_matches(self) -> None:
        assert theme._PALETTES["dark_orange"]["MUTED"].upper() == "#7A7069"
        assert "onSurfaceVariant = Color(0xFF7A7069)" in _scheme_body("DarkColors")

    def test_light_primary_matches_the_light_theme(self) -> None:
        """The Android light scheme follows the desktop's default theme."""
        expected = theme._PALETTES[theme.DEFAULT_THEME]["ACCENT"]
        assert f"primary = Color(0xFF{expected.lstrip('#').upper()})" in _scheme_body(
            "LightColors"
        )

    def test_light_background_matches(self) -> None:
        expected = theme._PALETTES[theme.DEFAULT_THEME]["BASE"]
        assert f"background = Color(0xFF{expected.lstrip('#').upper()})" in _scheme_body(
            "LightColors"
        )

    @pytest.mark.parametrize(
        "palette_name, scheme",
        [("dark_orange", "DarkColors"), (theme.DEFAULT_THEME, "LightColors")],
    )
    def test_every_colour_in_the_scheme_exists_in_the_palette(self, palette_name, scheme) -> None:
        palette = {
            v.lstrip("#").upper() for v in theme._PALETTES[palette_name].values()
        }
        body = _scheme_body(scheme)
        found = COLOR_RE.findall(body)
        assert found, "no colours found"
        for argb in found:
            rgb = argb[2:]  # drop the FF alpha byte
            assert rgb in palette, (
                f"{scheme} uses #{rgb}, which is not in the {palette_name} palette"
            )


# ======================================================================
# Semantic colours
# ======================================================================
class TestSemanticColours:
    def test_the_object_exists(self) -> None:
        assert "object MentorColors" in _kt_text()

    @pytest.mark.parametrize(
        "prop, token",
        [
            ("success", "SUCCESS"),
            ("warning", "WARNING"),
            ("error", "ERROR"),
            ("info", "INFO"),
            ("muted", "MUTED"),
            ("placeholder", "PLACEHOLDER"),
            ("border", "BORDER"),
            ("highlight", "CYAN"),
            ("successBg", "SUCCESS_BG"),
            ("warningBg", "WARNING_BG"),
            ("errorBg", "ERROR_BG"),
            ("infoBg", "INFO_BG"),
        ],
    )
    def test_each_maps_to_the_desktop_token(self, prop, token) -> None:
        expected = "0xFF" + theme._PALETTES["dark_orange"][token].lstrip("#").upper()
        assert f"val {prop} = Color({expected})" in _kt_text(), (
            f"MentorColors.{prop} should be the desktop {token} ({expected})"
        )

    def test_every_referenced_property_exists(self) -> None:
        """The check that matters: a screen referring to a colour that is not
        declared is a compile error, and the first version of this generator
        shipped exactly that - Screens.kt uses MentorColors.accent, which the
        generated object had dropped.

        Note the direction. Unused properties are *not* asserted against: this
        is a palette export, and a colour no screen has reached for yet is
        still the desktop's colour, available and correct. A test that demanded
        every token be used would push the generator back towards hand-curating
        a subset - which is how the two palettes drifted in the first place.
        """
        used = set()
        for path in (ROOT / "android" / "app" / "src" / "main" / "java").rglob("*.kt"):
            if path == THEME_KT:
                continue
            used.update(
                re.findall(r"MentorColors\.(\w+)", path.read_text(encoding="utf-8"))
            )
        assert used, "no screen uses MentorColors at all; is the object orphaned?"
        declared = set(re.findall(r"val (\w+) = Color", _kt_text()))
        missing = used - declared
        assert not missing, (
            f"MentorColors.{sorted(missing)} referenced by a screen but not "
            f"declared - the Android build would not compile"
        )

    def test_every_desktop_colour_is_reachable_from_kotlin(self) -> None:
        """No colour should exist only on the desktop.

        Each token in the dark palette must be reachable one of three ways:

        * present in a Material ColorScheme (BASE is `background`, SURFACE is
          `surface`, FOREGROUND is `onBackground`, ACCENT is `primary`, and so
          on);
        * exported through ``MentorColors``;
        * or named in ``QT_ONLY`` below, because it describes a Qt stylesheet
          state that Compose has no equivalent of.

        The point is that a screen never has to hard-code a colour to match the
        desktop, and never has to guess.
        """
        import export_theme

        scheme_text = _scheme_body("DarkColors") + _scheme_body("LightColors")
        in_scheme = {
            argb[2:]
            for argb in COLOR_RE.findall(scheme_text)
        }
        exported = {
            theme._PALETTES["dark_orange"][token].lstrip("#").upper()
            for token in export_theme.SEMANTIC
            if token in theme._PALETTES["dark_orange"]
        }

        #: Qt-stylesheet states with no Material counterpart. Navigation and
        #: selection highlights are per-widget CSS states in the desktop app;
        #: Compose expresses the same idea through its own state layers, so
        #: porting the literal colour would be wrong, not merely redundant.
        QT_ONLY = {
            "NAV_ACTIVE_BG", "NAV_ACTIVE_BG_HOV", "LIST_SEL_BG",
            "BTN_DISABLED_BG", "BTN_DISABLED_FG",
            "SYNTAX_KEYWORD", "SYNTAX_TYPE", "SYNTAX_STRING", "SYNTAX_NUMBER",
            "SYNTAX_COMMENT", "SYNTAX_PREPROCESSOR", "SYNTAX_FUNCTION",
            "SYNTAX_OPERATOR",
        }

        unreachable = []
        for token, value in theme._PALETTES["dark_orange"].items():
            if token in QT_ONLY:
                continue
            rgb = value.lstrip("#").upper()
            if rgb not in in_scheme and rgb not in exported:
                unreachable.append(token)
        assert not unreachable, (
            f"these desktop colours are not reachable from Kotlin: {unreachable}"
        )

    def test_syntax_highlighting_is_deliberately_not_exported(self) -> None:
        """The syntax colours are not carried over.

        Android has no syntax-highlighted editor - the playground is read-only
        there - so exporting 9 editor colours would be claiming a feature that
        does not exist. Listed explicitly so the decision is visible rather
        than an omission.
        """
        import export_theme

        assert not [t for t in export_theme.SEMANTIC if t.startswith("SYNTAX_")]


# ======================================================================
# Dynamic colour
# ======================================================================
class TestDynamicColourIsOptIn:
    def test_it_defaults_to_off(self) -> None:
        assert "dynamicColor: Boolean = false" in _kt_text()

    def test_the_flag_is_actually_used(self) -> None:
        """An ignored parameter would be a lie in the signature."""
        text = _kt_text()
        signature = text[text.index("fun MentorSmithTheme"):]
        assert "dynamicColor &&" in signature, "dynamicColor is never read"

    def test_the_system_scheme_needs_the_import(self) -> None:
        text = _kt_text()
        if "dynamicDarkColorScheme(" in text:
            assert "import androidx.compose.material3.dynamicDarkColorScheme" in text
            assert "import android.os.Build" in text

    def test_dark_theme_follows_the_system(self) -> None:
        assert "isSystemInDarkTheme()" in _kt_text()