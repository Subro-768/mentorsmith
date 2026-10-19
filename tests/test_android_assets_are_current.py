"""The Android app's bundled curriculum must match the desktop one.

The Linux app is the single source of truth for content.
``tools/export_curriculum.py`` writes it into
``android/app/src/main/assets/curriculum/`` as JSON, and the Kotlin app
reads that at first launch.

Nothing kept the two in step. Content could be written on the desktop, the
export script never run, and the Android app would go on serving a
curriculum that no longer exists - with no error anywhere, because each
half was internally consistent.

These tests run the export into a temporary directory and compare it with
what is committed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "android" / "app" / "src" / "main" / "assets" / "curriculum"
EXPORTER = ROOT / "tools" / "export_curriculum.py"

LANGUAGES = ("cpp", "python", "java", "c", "javascript")


@pytest.fixture(scope="module")
def check_result():
    """Run the exporter in its --check mode."""
    return subprocess.run(
        [sys.executable, str(EXPORTER), "--check"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=600,
    )


class TestTheBundledAssetsExist:
    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_language_is_bundled(self, language: str) -> None:
        assert (ASSETS / f"{language}.json").is_file()

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_bundle_is_valid_json(self, language: str) -> None:
        json.loads((ASSETS / f"{language}.json").read_text(encoding="utf-8"))


class TestTheBundleIsCurrent:
    """A content change on the desktop must reach the Android app."""

    def test_the_exporter_reports_nothing_stale(self, check_result) -> None:
        """The exporter's own --check mode, which compares file by file."""
        assert check_result.returncode == 0, (
            "the bundled curriculum is out of date. Run:\n"
            "    python3 tools/export_curriculum.py\n"
            f"{check_result.stdout[-600:]}{check_result.stderr[-600:]}"
        )

    @pytest.mark.parametrize("language", LANGUAGES)
    def test_the_bundled_lesson_count_matches_the_desktop(
        self, language: str
    ) -> None:
        from mentorsmith.core.curriculum_registry import load_track

        bundled = json.loads(
            (ASSETS / f"{language}.json").read_text(encoding="utf-8")
        )
        track = load_track(language)
        assert len(bundled["lessons"]) == len(track.lessons)
        assert len(bundled["concepts"]) == len(track.model.concepts)
        assert len(bundled["exercises"]) == len(track.bank.exercises)

    def test_every_lesson_carries_its_tier(self) -> None:
        """The Android app shows a tier badge; it needs the field."""
        for language in LANGUAGES:
            bundled = json.loads(
                (ASSETS / f"{language}.json").read_text(encoding="utf-8")
            )
            for lesson in bundled["lessons"]:
                assert lesson.get("tier"), (
                    f"{language}/{lesson['id']} has no tier"
                )
                assert lesson["tier"] in ("foundation", "core", "advanced")

    def test_the_lesson_ids_match_the_desktop(self) -> None:
        from mentorsmith.core.curriculum_registry import load_track

        for language in LANGUAGES:
            bundled = json.loads(
                (ASSETS / f"{language}.json").read_text(encoding="utf-8")
            )
            assert [l["id"] for l in bundled["lessons"]] == [
                l.id for l in load_track(language).lessons
            ]
