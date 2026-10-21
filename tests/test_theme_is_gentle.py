"""The default theme should be easy on the eyes.

The learner spends hours in this window. The first theme was a near-black
one that looked striking and, over a long session, was tiring - which is
the opposite of what a study tool should be.

These tests put numbers on "easy on the eyes" rather than leaving it to
 taste, so the theme cannot quietly drift back:

* the page is not pure white, which is the main source of glare;
* the text is not pure black against it, which is what makes a page feel
  heavy;
* the text still clears the WCAG AA contrast ratio, so it stays readable;
* the borders are faint, because structure should come from spacing;
* the accent is muted rather than fully saturated, so it does not shout.
"""

from __future__ import annotations

import pytest

from mentorsmith.ui import theme


def _channels(hex_colour: str) -> tuple[int, int, int]:
    value = hex_colour.lstrip("#")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _relative_luminance(hex_colour: str) -> float:
    """WCAG's relative luminance."""

    def channel(raw: int) -> float:
        srgb = raw / 255
        return srgb / 12.92 if srgb <= 0.03928 else ((srgb + 0.055) / 1.055) ** 2.4

    r, g, b = _channels(hex_colour)
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(first: str, second: str) -> float:
    a = _relative_luminance(first)
    b = _relative_luminance(second)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def _saturation(hex_colour: str) -> float:
    """How colourful a colour is, 0 (grey) to 1 (fully saturated)."""
    r, g, b = _channels(hex_colour)
    highest, lowest = max(r, g, b), min(r, g, b)
    if highest == 0:
        return 0.0
    return (highest - lowest) / highest


class TestTheDefaultTheme:
    def test_it_is_the_soft_one(self) -> None:
        assert theme.DEFAULT_THEME == "paper"
        assert "paper" in theme.THEMES

    def test_the_dark_themes_are_still_there(self) -> None:
        """Not replaced - some people want dark, and the choice is theirs."""
        assert "dark_orange" in theme.THEMES
        assert "light" in theme.THEMES


class TestPaperIsEasyOnTheEyes:
    def test_the_page_is_not_pure_white(self) -> None:
        """Pure white is the main source of glare on a bright screen."""
        base = theme._PALETTES["paper"]["BASE"]
        assert base.upper() != "#FFFFFF"
        r, g, b = _channels(base)
        assert r > 200, "the page is too dark to read comfortably"
        # A warm paper, not a cold grey.
        assert r >= b, "the page should be warm rather than blue"

    def test_the_text_is_not_pure_black(self) -> None:
        """Full contrast against the background is what reads as heavy."""
        foreground = theme._PALETTES["paper"]["FOREGROUND"]
        assert foreground.upper() != "#000000"

    def test_the_text_is_still_readable(self) -> None:
        """Soft is not the same as unreadable: WCAG AA is the floor."""
        palette = theme._PALETTES["paper"]
        for background in (palette["BASE"], palette["SURFACE"]):
            ratio = _contrast(palette["FOREGROUND"], background)
            assert ratio >= 4.5, f"contrast {ratio:.2f} is below AA"

    def test_the_secondary_text_is_readable_too(self) -> None:
        palette = theme._PALETTES["paper"]
        ratio = _contrast(palette["MUTED"], palette["BASE"])
        assert ratio >= 3.0, f"muted text contrast {ratio:.2f} is too low"

    def test_the_borders_are_faint(self) -> None:
        """Structure should come from spacing, not from lines."""
        palette = theme._PALETTES["paper"]
        ratio = _contrast(palette["BORDER"], palette["BASE"])
        assert ratio < 1.6, f"borders contrast {ratio:.2f} - they will shout"

    def test_the_accent_is_muted(self) -> None:
        """A colour that shouts is a colour you stop noticing."""
        palette = theme._PALETTES["paper"]
        assert _saturation(palette["ACCENT"]) < 0.75
        assert _saturation(palette["ACCENT"]) > 0.2, "the accent has no colour"

    def test_the_accent_still_stands_out_from_the_page(self) -> None:
        palette = theme._PALETTES["paper"]
        ratio = _contrast(palette["ACCENT"], palette["BASE"])
        assert ratio > 2.5, f"accent contrast {ratio:.2f} is too low to spot"

    def test_every_theme_still_builds_a_stylesheet(self) -> None:
        for name in theme.THEMES:
            sheet = theme.get_stylesheet(name)
            assert sheet
            assert "QWidget" in sheet
