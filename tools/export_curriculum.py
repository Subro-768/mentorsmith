#!/usr/bin/env python3
"""Export the MentorSmith curriculum into the format the Android app bundles.

The Linux app is the single source of truth for content. This script writes
that content into ``android/app/src/main/assets/curriculum/`` as JSON, which
the Kotlin app reads at first launch.

**No Python code is shared with Kotlin.** Only this documented file format is.
It is deliberately plain and stable so either side can evolve independently:

Top level (one file per language, named ``<language>.json``)::

    {
      "format_version": 1,          // bump on incompatible changes
      "language": "cpp",
      "label": "C++",
      "generated_by": "tools/export_curriculum.py",
      "lessons":   [ Lesson, ... ],
      "concepts":  [ Concept, ... ],
      "exercises": [ Exercise, ... ],
      "projects":  [ Project, ... ],
      "comparisons": [ Comparison, ... ]
    }

Lesson::

    { "id", "title", "order", "tier", "sections": {name: markdown},
      "example_code", "starter_code", "checks": [{"question", "answer"}] }

Concept::

    { "id", "title", "lesson_id", "summary",
      "prerequisites": [id], "error_categories": [id] }

Exercise::

    { "id", "concept_id", "lesson_id", "type", "title", "prompt", "code",
      "starter_code", "expected_stdout", "stdin", "rubric": [str],
      "novel", "tags": [str], "graded_by": "deterministic" | "interpretive" }

Project::

    { "id", "title", "purpose", "concepts": [id], "difficulty",
      "milestones": [{ "title", "requirements",
                       "acceptance_criteria": [str], "hint" }],
      "extensions": [str] }

Comparison::

    { "id", "concept", "languages": [a, b], "same", "different": [str],
      "snippets": [a, b], "question" }

Run it with ``--check`` to verify the export is up to date without writing,
which is what CI should do.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mentorsmith.core import comparisons as comparisons_module  # noqa: E402
from mentorsmith.core import curriculum_registry as registry  # noqa: E402

#: Bump when a field changes meaning or disappears. The Kotlin side refuses to
#: read a file with a higher version rather than misinterpreting it.
FORMAT_VERSION = 1


def export_language(language: str) -> dict:
    """Build the export payload for one language."""
    track = registry.load_track(language)

    lessons = [
        {
            "id": lesson.id,
            "title": lesson.title,
            "order": lesson.order,
            # Which progression tier the lesson sits in: foundation, core or
            # advanced. The Android app shows the same badge the desktop
            # one does, so the two agree on where a learner is.
            "tier": lesson.tier,
            "sections": dict(lesson.sections),
            "example_code": lesson.example_code,
            "starter_code": lesson.starter_code,
            "checks": [
                {"question": question, "answer": answer}
                for question, answer in lesson.checks
            ],
        }
        for lesson in track.lessons
    ]

    concepts = [concept.to_dict() for concept in track.model.concepts.values()]

    exercises = [
        {
            "id": exercise.id,
            "concept_id": exercise.concept_id,
            "lesson_id": exercise.lesson_id,
            "type": exercise.type,
            "title": exercise.title,
            "prompt": exercise.prompt,
            "code": exercise.code,
            "starter_code": exercise.starter_code,
            "expected_stdout": exercise.expected_stdout,
            "stdin": exercise.stdin,
            "rubric": list(exercise.rubric),
            "novel": exercise.novel,
            "tags": list(exercise.tags),
            # The Android app must label grading the same way the desktop does.
            "graded_by": "interpretive" if exercise.is_interpretive else "deterministic",
        }
        for exercise in track.bank.exercises
    ]

    projects = [project.to_dict() for project in track.model.projects.values()]

    # Comparisons are global rather than per language, but the app should only
    # be handed the ones that touch the track it is showing.
    relevant = [
        comparison.to_dict()
        for comparison in comparisons_module.for_language(language)
    ]

    return {
        "format_version": FORMAT_VERSION,
        "language": track.language,
        "label": track.label,
        "generated_by": "tools/export_curriculum.py",
        "lessons": lessons,
        "concepts": concepts,
        "exercises": exercises,
        "projects": projects,
        "comparisons": relevant,
    }


def destination(language: str) -> Path:
    return ROOT / "android" / "app" / "src" / "main" / "assets" / "curriculum" / f"{language}.json"


def write_all(check_only: bool = False) -> int:
    """Write every language, or verify without writing. Returns an exit code."""
    languages = list(registry.LANGUAGE_IDS)
    stale: list[str] = []

    for language in languages:
        try:
            payload = export_language(language)
        except Exception as exc:  # a broken track must not stop the export
            print(f"  error: {language}: {exc}", file=sys.stderr)
            stale.append(language)
            continue

        text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n"
        path = destination(language)
        path.parent.mkdir(parents=True, exist_ok=True)

        if check_only:
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != text:
                stale.append(language)
                print(f"  stale: {path.relative_to(ROOT)}")
        else:
            path.write_text(text, encoding="utf-8")
            print(
                f"  wrote {path.relative_to(ROOT)} "
                f"({len(payload['lessons'])} lessons, "
                f"{len(payload['concepts'])} concepts, "
                f"{len(payload['exercises'])} exercises)"
            )

    if check_only and stale:
        print(
            f"\n{len(stale)} file(s) out of date: {', '.join(stale)}",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the exported files are up to date without writing them.",
    )
    args = parser.parse_args()

    print(f"Exporting MentorSmith curriculum (format v{FORMAT_VERSION})")
    code = write_all(check_only=args.check)
    if code == 0:
        print("Done.")
    return code


if __name__ == "__main__":
    sys.exit(main())