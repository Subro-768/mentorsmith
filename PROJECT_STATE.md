# PROJECT_STATE.md

## Current state
- Current phase: **Phase 2 complete** (aihandoff_2.md). Phase 3 not started.
- Last updated: 2026-10-16
- Branch / repository status: `master`, two commits. No remote configured.
- App launch status: **Launches on Fedora 44**, six pages, verified by
  constructing the window offscreen (`python3 main.py --check`) and by rendering
  every screen.

## Baseline recorded before Phase 2
- Phase 1 tests at the start of Phase 2: **140 passed**.
- Schema version at that point: **1**.
- Those 140 tests still pass after Phase 2 (now 299 total).

## Project purpose
Linux-first AI programming tutor with an Android learning companion. The goal
is to teach fundamentals, debugging, and independent problem-solving rather
than simply generate code.

The app is called **MentorSmith** (Python package `mentorsmith`). The name was
chosen because a smith forges raw stock into something usable. It was checked
against PyPI and GitHub for collisions: PyPI returns 404 and GitHub reports 0
matching repositories. Rejected alternatives: `bitloom`, `codeloom` and
`corefoundry` were all already taken on PyPI.

## Actual architecture
A layered PyQt6 desktop app. Implemented, not planned:

- **`core/db.py`** — the only module that opens a SQLite connection. Holds an
  ordered `MIGRATIONS` dict applied through `PRAGMA user_version`, so an old
  database upgrades on next launch by the same path that creates a new one.
- **`core/curriculum.py`** — parses lesson Markdown with a small front-matter
  and section parser. No third-party Markdown dependency.
- **`lessons/`** — 16 Markdown files, one per topic. Content is never embedded
  in UI code.
- **`compiler/toolchain.py`** — detects `g++`/`clang++`/`c++`, compiles with
  `argparse`-style argument vectors (never a shell), deletes any stale binary
  before compiling, and runs with POSIX resource limits. Optionally wraps
  execution in `bwrap`. Compiles and runs on a `QThread` so the GUI never
  blocks; `start_new_session=True` plus a process group makes **Stop** kill the
  whole tree.
- **`providers/`** — a small `LLMProvider` interface plus one
  `/chat/completions` adapter using only the standard library. Typed errors for
  auth, rate limiting, timeout, network and malformed responses.
- **`services/tutor.py`** — the three assistance levels, prompt construction and
  `parse_tutor_response`, which is pure and free of both Qt and I/O so it is
  directly unit-testable.
- **`ui/`** — dark theme, line-numbered code editor with a `QSyntaxHighlighter`
  C++ highlighter, lesson view, dashboard, progress view, settings dialog and
  main window.

Design rationale is in `docs/architecture.md`.

## Important files
| File/path | Purpose | Status |
|---|---|---|
| `main.py` | Entry point; `--check` builds the UI headlessly | Done, verified |
| `mentorsmith/config.py` | Paths and non-secret settings only | Done, verified |
| `mentorsmith/core/db.py` | SQLite persistence + migrations | Done, 23 tests |
| `mentorsmith/core/curriculum.py` | Lesson Markdown loading | Done, 19 tests |
| `mentorsmith/lessons/*.md` | 16 C++ lessons | Done, all 16 verified complete |
| `mentorsmith/compiler/toolchain.py` | Detect / compile / run / contain | Done, 19 tests |
| `mentorsmith/providers/base.py` | Provider interface + typed errors | Done, 28 tests |
| `mentorsmith/providers/openai_compat.py` | `/chat/completions` adapter | Done, 28 tests |
| `mentorsmith/services/tutor.py` | Levels, prompts, parsing | Done, 29 tests |
| `mentorsmith/ui/` | Qt widgets | Done, 32 smoke tests |
| `mentorsmith/data/concepts.json` | 18 concepts + prerequisite graph + 5 projects | Done, validated on load |
| `mentorsmith/data/exercises.json` | 53 exercises across all 8 types | Done, validated on load |
| `mentorsmith/core/mastery.py` | Evidence -> label, with reasons | Done, 21 tests |
| `mentorsmith/core/adaptive.py` | Which exercise next, and why | Done, tested |
| `mentorsmith/core/debugging.py` | Diagnose / hint / retry / escalate | Done, tested |
| `mentorsmith/core/projects.py` | Proposals, milestones, difficulty | Done, tested |
| `mentorsmith/core/revision.py` | Review reasons, regressions | Done, tested |
| `mentorsmith/services/practice.py` | One exercise end to end, no Qt | Done, 23 tests |
| `mentorsmith/services/insights.py` | Dashboard assembly + justifications | Done, tested |
| `README.md` | Setup, AI config, security, tests, how recommendations work | Done |
| `docs/architecture.md` | Architecture and design rationale | Done |
| Android companion | Kotlin learning companion | **Not started** |

## Implemented features
Verified by the test suite and by rendering the UI:

- [x] App launches on Linux (window constructed and rendered; `--check` passes)
- [x] 16 C++ lessons load, each with all seven required sections, example code,
      starter code and at least three answered knowledge checks
- [x] Lesson navigation with correct previous/next boundaries
- [x] Code editor with C++ syntax highlighting and line numbers
- [x] Compile and run with `g++`; stdout and stderr shown separately
- [x] Compile failures shown with the compiler's own unmodified diagnostics
- [x] Non-zero exit codes reported as failures, not success
- [x] Runtime timeout enforced and reported as a timeout
- [x] Stop button terminates a hanging program (verified with `for(;;){}`)
- [x] Memory limit refuses an unbounded allocation
- [x] Optional `bwrap` sandbox; verified to block host filesystem reads *and*
      writes from inside the sandbox
- [x] Sandbox status reported honestly, including when requested but inactive
- [x] Progress persists across restarts (verified by reopening the database)
- [x] Exercise attempts record `compiled_ok` / `ran_ok` from real results
- [x] Three assistance levels with level-specific prompt rules
- [x] Tutor response parsing with graceful fallback for untagged replies
- [x] Provider error handling for auth, rate limit, timeout, 404, 5xx and
      malformed responses
- [x] API key read from the environment only; never persisted or logged
- [x] `MENTORSMITH_OFFLINE=1` blocks all AI calls
- [x] Settings dialog with a working "Test connection" request
- [x] Progress view and activity feed; reset requires confirmation

### Phase 2 (aihandoff_2.md)

- [x] Concept model with 18 concepts and an explicit prerequisite graph,
      stored as validated structured data
- [x] Exercise history affects recommendations (repair / consolidate /
      extension / review, each with its reason)
- [x] Concepts can be flagged for review with explainable evidence
- [x] 53 exercises covering all 8 required types; every concept has at least one
- [x] Deterministic grading by compiling and running, with a diff on mismatch
- [x] Interpretive grading labelled as such, never presented as proof
- [x] Guided debugging: capture, categorise, hint, retry, escalate, follow-up
- [x] Hint usage recorded and reflected in the independence flag
- [x] `solve-without-AI` exercises refuse hints, in code and in the UI
- [x] Projects have milestones, requirements and acceptance criteria
- [x] Blocked projects name the concepts to strengthen first
- [x] Attempts and progress persist, including across a schema upgrade
- [x] Dashboard explains its next-step recommendation
- [x] Chat messages and time in the app are not counted as evidence
- [x] Model output validated before use; prompt injection proven inert
- [x] Phase 1 still works (its 140 tests are unchanged and still pass)

**Not implemented:** no Android companion, no exercise authoring UI, no
spaced-repetition scheduler (a fixed staleness threshold is used instead), and
project milestones are tracked but not auto-graded.

## Commands
### Run Linux app
```bash
cd "/home/subro/Documents/APPS/programming tutor space bunny"
python3 main.py
```

### Verify the install without opening a window
```bash
python3 main.py --check
```

### Run tests
```bash
python3 -m pip install pytest
python3 -m pytest tests/ -q
```

### Build Android app
Not applicable — Android has not been started.

## Tests
Command run and actual result after Phase 2:

```
$ python3 -m pytest tests/ -q
........................................................................ [ 72%]
........................................................................ [ 96%]
...........                                                              [100%]
299 passed in 8.52s
```

Per file, all passing:

| File | Tests | Covers |
|---|---|---|
| `tests/test_db.py` | 23 | migrations, lesson progress, attempts, activity, settings |
| `tests/test_compiler.py` | 19 | detection, compile success/failure, timeouts, stop, sandbox isolation |
| `tests/test_curriculum.py` | 19 | 16 lessons complete, ordering, parsing edge cases |
| `tests/test_providers.py` | 28 | configuration, parsing, malformed replies, HTTP failures, key hygiene |
| `tests/test_tutor.py` | 29 | assistance levels, prompts, response parsing |
| `tests/test_ui_smoke.py` | 32 | headless construction, lessons, persistence, offline, Phase 2 pages |
| `tests/test_concepts.py` | 27 | concept model, prerequisites, cycle detection, malformed data |
| `tests/test_mastery.py` | 21 | labels, evidence, repeated errors, hints, novelty |
| `tests/test_phase2_core.py` | 54 | grading, adaptive selection, debugging, projects, revision |
| `tests/test_phase2_data.py` | 24 | v1-to-v2 migration safety, evidence aggregation, model-output validation |
| `tests/test_practice.py` | 23 | end-to-end practice with a real compiler, hint tracking, regressions |

Tests never touch the real database or a real provider: the database is
in-memory or in `tmp_path`, and the AI provider is always mocked. No test costs
money or requires network access. Compiler-dependent tests skip themselves if
no compiler is present.

## How recommendations work

Deterministic and inspectable. `core/adaptive.py` scores candidate exercises
into four priority tiers, and each one carries a plain-language reason built
from the learner's own counts:

1. **repair** — attempted but weak, especially with a recurring error category.
2. **consolidate** — correct first time but only once; an unfamiliar variation
   comes next, because recall of a worked example is not generalisation.
3. **extension** — prerequisites all strong, nothing attempted.
4. **review** — strong concept not practised for `REVIEW_AFTER_DAYS` (14).

Two rules that are easy to get wrong and are enforced:

- **Lesson completion is never read by the selection code.** It is not
  evidence. Only graded attempts are.
- **A recurring error category downgrades the label** even when the score is
  high. Three occurrences of the same mistake force `needs_review`.

Mastery score composition is documented at the top of `core/mastery.py`, and
every label must ship with evidence strings.

## Data and migrations
- Database: `~/.local/share/mentorsmith/progress.db` (SQLite 3.51.2).
- Work directory for compiled code: `~/.local/share/mentorsmith/workdir/`.
- Both honour `XDG_DATA_HOME`.
- Schema version **2**. Version 1 is the Phase 1 schema; version 2 is
  **strictly additive** — nine `ALTER TABLE ... ADD COLUMN` statements with
  defaults, plus five new tables. Nothing is dropped or rewritten.
- Tables: `lesson_progress`, `exercise_attempts` (now carrying Phase 2
  evidence columns), `activity`, `app_settings`, `concept_progress`,
  `projects`, `project_milestones`, `project_activity`, `reviews`.
- **Upgrade safety is tested, not assumed.** `tests/test_phase2_data.py`
  builds a genuine schema-v1 database by hand, fills it with Phase 1 rows, opens
  it with the current code, and asserts every Phase 1 row survives with its
  values intact.
- **Backup:** stop the app and copy `progress.db`. No sync, no automatic backup.
- API keys are never stored here. Only non-secret settings are persisted.

## AI provider configuration
- Base URL and model name are entered in Settings and stored in
  `~/.local/share/mentorsmith/settings.json`.
- The API key is read from the `MENTORSMITH_API_KEY` environment variable at
  request time. It is never written to disk, to the database, or to any log or
  exception message — asserted by tests.
- No provider or model is hardcoded. The adapter targets the widely used
  `POST /chat/completions` shape.
- `MENTORSMITH_OFFLINE=1` blocks all AI calls.
- When a message is sent, the provider receives the lesson title and
  objectives, the editor contents, the on-screen compiler and runtime output,
  and the learner's message. The chat panel states this permanently.

**No real provider has been configured or tested yet.** The provider tests use
a mocked `urlopen`; the live path against an actual vendor is unverified.

## Known bugs and limitations
- The Markdown renderer handles the subset the lessons use (headings, bullets,
  fenced code, inline code, bold, italic, simple tables), not the full spec.
- The code editor has no autocomplete, and relies on Qt's built-in undo.
- `RLIMIT_NPROC` is intentionally not used. It counts processes per real UID,
  so any value restrictive enough to matter also breaks `fork` for the user's
  own programs. This was found the hard way: a limit of 64 made `bwrap` fail
  with `EAGAIN` on a machine already running more than 64 processes.
- `bwrap` requires unprivileged user namespaces. If unavailable, the app says
  the sandbox is **not** active rather than implying otherwise.
- Bubblewrap isolation is defence in depth, not a true sandbox. It gives less
  protection than a VM or a configured container.
- The learner's own exercises are not automatically unit-tested; examples are
  verified when the learner compiles them.
- There is no lesson-content editor in the UI; lessons are edited as Markdown.
- Progress is per-machine.

## Next steps
1. Manually verify the Phase 1 acceptance checklist in the running app,
   especially the three assistance levels against a real configured provider.
2. Obtain an API key, configure a provider in Settings, and exercise the tutor
   at all three levels. This is the largest untested surface.
3. Test the sandbox on a course material that needs real headers, to learn
   whether the read-only view is too restrictive for practical work.
4. Review lesson content for technical accuracy.
5. Only then begin Phase 2 (`aihandoff_2.md`) after approval.

## Decisions not to silently reverse
- **Lesson completion is not evidence.** Phase 2 says completing a lesson must
  not mean mastery. `core/adaptive.py` never reads `lesson_progress`, and a test
  asserts it.
- **Chat messages and time in the app are not evidence.** Neither quantity is
  read anywhere in the insights path. A test asserts that recording chat
  activity leaves every concept `not_started`.
- **Deterministic grading is separated from interpretive grading.** Code
  exercises are graded by compiling and running; free-form explanations are
  graded by the tutor and stored with `graded_by='interpretive'`. The UI labels
  which kind of judgement the learner is looking at, every time.
- **Model output is data, never instructions.** `services/practice.parse_verdict`
  is the only function that reads untrusted tutor text and it can do nothing
  except choose a verdict. A test injects a prompt-injection payload and asserts
  it stays inert; another asserts the practice module imports no `subprocess`,
  `eval`, `exec` or `__import__`.
- **Every label and recommendation carries evidence.** No bare claim appears in
  the UI.
- **`not_started` is distinct from `needs_review`.** Doing nothing is not the
  same as having tried and struggling.
- **One correct answer is not mastery.** `strong` requires at least two graded
  attempts.
- **API keys come from the environment, never from the database or settings
  file.** Tests enforce it.
- **The compiler is never invoked through a shell.** Lesson text must never be
  interpreted as shell syntax.
- **Stale binaries are deleted before every compile.** A failed compile must
  never leave a previous executable behind that appears to run.
- **Sandbox is off by default**, and its state is always displayed honestly.
- **UI never opens a database connection.**
- **Lesson and exercise content stays in data files**, not in UI code.
- **No claim of success without real output.**
- **Concept data is validated on load.** A broken prerequisite graph, an unknown
  concept reference, a cycle or a milestone with no acceptance criteria fails at
  startup rather than producing impossible recommendations.

## Notes for the next Space Bunny session
Read this file, `README.md`, `docs/architecture.md`, the relevant source and
the tests before editing.

Re-run `python3 -m pytest tests/ -q` (expect **299 passed**) and
`python3 main.py --check` before changing anything.

The largest untested area is still the **live AI provider path** — everything up
to the HTTP boundary is mocked, and nothing has been sent to a real vendor. The
interpretive grading of free-form answers is the part most likely to need tuning
against a real model, since its rubric parsing is deliberately conservative and
defaults to *incorrect* when it cannot parse a verdict.

What to understand before changing anything:

- **Evidence flows one way.** `exercise_attempts` → `core/db.concept_evidence`
  → `core/mastery` → `core/adaptive` / `core/revision` → `services/insights` →
  UI. Interpretation lives in `mastery` and `adaptive`, never in a widget.
- **`concept_progress` is only a cache** and can always be rebuilt from
  `exercise_attempts`. Do not make it authoritative.
- **Adding an exercise type** means touching `EXERCISE_TYPES` in
  `core/exercises.py`, giving it either `expected_stdout` (deterministic) or a
  `rubric` (interpretive). The loader rejects anything else.