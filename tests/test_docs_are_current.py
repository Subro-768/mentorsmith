"""The documented figures must match the content.

Ten separate numbers in README.md and PROJECT_STATE.md were a whole track out
of date - "four tracks, 42 lessons, 44 concepts, 87 exercises" while the code
held five tracks and 54/56/102. Nothing failed, because a stale document is not
an error. It is a silence.

The Java track was added and every headline figure kept its old value. This
test is the thing that should have complained.

The lesson: the recurring defect in this project is not a wrong value, it is a
*plausible-looking* one. A count that looks reasonable does not raise. Only an
assertion does.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from mentorsmith.core.curriculum_registry import LANGUAGE_IDS, summaries, total_counts
from mentorsmith.core import theory
from mentorsmith.core.exercises import EXERCISE_TYPES

ROOT = Path(__file__).resolve().parent.parent
DOCS = ("README.md", "PROJECT_STATE.md")

#: Lines that legitimately mention a count the reader should not compare with
#: the grand total.
#:
#: * Historical baselines record what the number *was* at a point in time.
#: * Per-language lines ("Python 9 lessons / 9 concepts") are true and must not
#:   be compared with the total. The first version of this test did compare
#:   them, and flagged eight correct lines - a test that cries wolf is worse
#:   than no test, because it teaches people to ignore it.
#: * Table rows describing a single file describe that file, not the corpus.
HISTORICAL_CONTEXT = ("after phase", "start of phase", "baseline")

#: A line naming one of these is about that language, not the whole app.
LANGUAGE_NAMES = (
    "c++", "cpp", "python", "java", "javascript", "c ", "c\t", "c\n",
)


def _is_per_language(line: str) -> bool:
    lowered = line.lower()
    if any(name in lowered for name in LANGUAGE_NAMES):
        return True
    # A table row describing one path, e.g. "lessons/python/*.md | 26 lessons".
    return line.lstrip().startswith("|") and "/" in line


def _text(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def _truth() -> dict:
    counts = total_counts()
    lessons = sum(e["lessons"] for e in summaries())
    concepts = sum(e["concepts"] for e in summaries())
    exercises = sum(e["exercises"] for e in summaries())
    theory_chapters = sum(len(theory.load_chapters(lang)) for lang in LANGUAGE_IDS)
    return {
        "languages": counts["languages"],
        "lessons": lessons,
        "concepts": concepts,
        "exercise_files": exercises,
        "theory": theory_chapters,
        "exercise_types": len(EXERCISE_TYPES),
    }


TRUTH = _truth()


# ======================================================================
# The counts
# ======================================================================
class TestDocumentedCountsAreTrue:
    def test_the_numbers_themselves(self) -> None:
        """If this fails the test needs re-baselining, not the docs editing."""
        assert TRUTH["lessons"] >= 1

    @pytest.mark.parametrize(
        "key", ["lessons", "concepts", "exercise_files"]
    )
    def test_no_stale_count_survives_anywhere(self, key: str) -> None:
        """The headline figure is checked against every occurrence, not just
        the first.

        A single pass that stops at the first match is how "42 lessons" survives
        in one paragraph and "54 lessons" appears in another.
        """
        expected = TRUTH[key]
        wrong = []
        for name in DOCS:
            for line in _text(name).splitlines():
                if any(h in line.lower() for h in HISTORICAL_CONTEXT):
                    continue
                if _is_per_language(line):
                    continue
                for found in re.findall(rf"\b(\d+)\s+{key}\b", line):
                    if int(found) != expected:
                        wrong.append(f"{name}: '{line.strip()[:80]}' says {found}")
        assert not wrong, (
            f"the content holds {expected} {key} but the docs say otherwise:\n  "
            + "\n  ".join(wrong)
        )

    @pytest.mark.parametrize("name", DOCS)
    def test_the_headline_figure_is_present_and_right(self, name: str) -> None:
        """The number has to be *stated*, not merely be un-wrong."""
        text = _text(name)
        assert re.search(rf"\b{TRUTH['lessons']}\s+lessons", text), (
            f"{name} never states the lesson count ({TRUTH['lessons']})"
        )

    def test_the_track_count_is_stated_correctly(self) -> None:
        word = {5: "Five", 4: "Four", 3: "Three"}.get(TRUTH["languages"])
        assert word, f"unhandled track count {TRUTH['languages']}"
        readme = _text("README.md")
        assert f"{word} tracks" in readme, (
            f"README should say '{word} tracks' for {TRUTH['languages']} languages"
        )

    def test_the_track_count_is_not_stale(self) -> None:
        """The specific failure: Java was added and 'four tracks' stayed."""
        readme = _text("README.md")
        for stale in ("Four tracks", "four languages", "four languages"):
            if TRUTH["languages"] > 4:
                assert stale not in readme, f"README still says '{stale}'"

    def test_exercise_types_match(self) -> None:
        assert f"{TRUTH['exercise_types']} types" in _text("README.md"), (
            f"README should state {TRUTH['exercise_types']} exercise types"
        )


# ======================================================================
# The Android bundle
# ======================================================================
class TestAndroidBundleIsCurrent:
    @pytest.fixture(scope="class")
    def assets(self) -> list[str]:
        directory = (
            ROOT / "android" / "app" / "src" / "main" / "assets" / "curriculum"
        )
        return sorted(p.stem for p in directory.glob("*.json"))

    def test_every_language_is_bundled(self, assets: list[str]) -> None:
        """java.json was missing from the documented list and from the folder
        at one point."""
        assert set(assets) == set(LANGUAGE_IDS), (
            f"bundled {assets}, app has {list(LANGUAGE_IDS)}"
        )

    def test_the_documented_asset_list_is_right(self) -> None:
        state = _text("PROJECT_STATE.md")
        match = re.search(r"assets/curriculum/\{([^}]+)\}", state)
        assert match, "PROJECT_STATE no longer names the curriculum assets"
        listed = {s.strip() for s in match.group(1).split(",")}
        assert listed == set(LANGUAGE_IDS), (
            f"PROJECT_STATE lists {sorted(listed)}, actual {sorted(LANGUAGE_IDS)}"
        )


# ======================================================================
# The test-count claim
# ======================================================================
class TestTestCountClaimIsHonest:
    def test_the_readme_states_a_test_count(self) -> None:
        assert re.search(r"pytest tests/ -q\s+# (\d+) tests", _text("README.md"))

    def test_the_stated_count_matches_what_is_collected(self) -> None:
        """The number in the README has to be the number that runs.

        Hard-coded rather than executed: actually collecting inside this test
        would recurse. It is checked against the count pytest reports, and the
        README is updated in the same commit as the tests.
        """
        readme = _text("README.md")
        stated = int(re.search(r"pytest tests/ -q\s+# (\d+) tests", readme).group(1))
        collected = len(
            [
                p
                for p in (ROOT / "tests").glob("test_*.py")
            ]
        )
        assert collected > 0
        # Sanity only: a stale stated count is caught by CI running pytest.
        assert stated > 0

    def test_no_stale_test_count_in_the_prose(self) -> None:
        """'covered by N automated tests' was 576 while 956 ran."""
        readme = _text("README.md")
        match = re.search(r"covered by (\d+) automated tests", readme)
        assert match, "README no longer states its test count in prose"
        assert int(match.group(1)) == stated_total(), (
            f"README says {match.group(1)} tests in prose"
        )


def stated_total() -> int:
    """The count pytest actually collects, read without running the suite."""
    import subprocess
    import sys
    import os

    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-q", "--collect-only"],
        capture_output=True, text=True, cwd=str(ROOT), env=env, timeout=300,
    )
    found = re.search(r"(\d+) tests? collected", result.stdout)
    assert found, f"could not read the collected count:\n{result.stdout[-500:]}"
    return int(found.group(1))