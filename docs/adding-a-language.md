# Adding a language to MentorSmith

This is the procedure Phase 4 followed, written down so it does not have to be
rediscovered. It assumes nothing about the current number of languages.

## 1. Write an execution adapter

Create `mentorsmith/execution/<language>.py`. Extend `CompiledAdapter` for a
statically compiled language or `InterpretedAdapter` for a scripted one.

```python
from pathlib import Path
from .compiled import CompiledAdapter


class RustAdapter(CompiledAdapter):
    language_id = "rust"
    display_name = "Rust"
    kind = "compiled"
    extensions = (".rs",)
    tool_candidates = ("rustc",)
    install_hint = "sudo dnf install rust"
    compiles = True

    def compile_argv(self, source: Path, artifact: Path) -> list[str]:
        return [self.tool_path, str(source), "-o", str(artifact)]

    def run_argv(self, source: Path, artifact: Path) -> list[str]:
        return [str(artifact)]
```

`interpreted.py` already provides the no-build-step behaviour, so an
interpreted adapter only needs `run_argv`.

**What must stay language-specific.** Compiler flags, diagnostics handling,
execution configuration and resource limits. Phase 4 was explicit: *do not
abstract away meaningful language differences*. Only the shared process
handling lives in `base.py`.

**Where a default has to change.** V8 needs a much larger address space than a
C binary (see `javascript.py`), and any runtime with its own heap cap should
expose it as a flag rather than relying on `RLIMIT_AS` alone. Measure before
guessing.

## 2. Register it

In `mentorsmith/execution/__init__.py`:

1. add the id to `LANGUAGE_IDS`
2. add the label to `LANGUAGE_LABELS`
3. add the import and register it in `_ADAPTERS`

## 3. Add the lessons

Create `mentorsmith/lessons/<language>/` and write one Markdown file per topic.

Front matter plus seven sections:

```markdown
---
id: 01-first-topic
title: First Topic
order: 1
---

## Objectives
## Explanation
## Example
```cpp
## Knowledge checks
Q: ...
A: ...
## Exercise
```cpp starter
## Common mistakes
## Recap
```

Use ```` ```<language> ```` for code fences, and add the tag to `CODE_FENCE` in
`core/curriculum_registry.py`.

## 4. Add concepts and exercises

Create `mentorsmith/data/curriculum/<language>.json`:

```json
{
  "language": "rust",
  "concepts": [
    { "id": "rs-variables", "title": "Variables", "lesson_id": "01-first-topic",
      "summary": "...", "prerequisites": [], "error_categories": [] }
  ],
  "exercises": [
    { "id": "rs-ex-1", "concept_id": "rs-variables", "lesson_id": "01-first-topic",
      "type": "predict-output", "title": "...", "prompt": "...",
      "code": "...", "expected_stdout": "..." }
  ]
}
```

Validation is automatic and happens at load: unknown concepts, dangling lesson
links, prerequisite cycles, deterministic exercises without
`expected_stdout`, and interpretive exercises without a `rubric` all fail
loudly.

C++ is the exception: its data predates this layout and lives in
`mentorsmith/data/concepts.json` and `mentorsmith/data/exercises.json`.

## 5. Add the schema column

Add `MIGRATIONS[next_version]` with:

```sql
ALTER TABLE <table> ADD COLUMN language TEXT NOT NULL DEFAULT '<new-language>'
```

Never edit a released migration. Existing rows keep the C++ default, which is
correct because C++ was the first track.

## 6. Add tests

At minimum, copy the shape of `tests/test_phase4_languages.py`:

- the adapter runs a hello program
- failures are reported honestly
- the timeout stops a runaway program
- a missing tool produces an install hint
- lessons load and every concept has an exercise
- progress is isolated from the other languages

## 7. Update the docs

- `README.md` — the language list and the runtime requirements
- `PROJECT_STATE.md` — the curriculum coverage table and the test results

## Checklist before calling it done

- [ ] `python3 main.py --check` lists the language and finds its toolchain
- [ ] The full test suite passes
- [ ] Progress in the new language does not leak into another language
- [ ] A missing tool explains how to install it
- [ ] `mentorsmith/execution/base.py` was not edited to add special cases for
      this language; if it was, that is a sign the adapter is doing too much.