# PROJECT_STATE.md

## Current state
- Current phase: **Phase 1 complete** (aihandoff_1.md). Phase 2 not started.
- Last updated: 2026-10-16
- Branch / repository status: `master`, initial commit made after the first
  working version. No remote configured.
- App launch status: **Launches on Fedora 44.** Verified by constructing the
  full window offscreen (`python3 main.py --check`) and by rendering each
  screen.

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
| `mentorsmith/ui/` | Qt widgets | Done, 22 smoke tests |
| `README.md` | Setup, AI config, security, tests | Done |
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

**Not implemented:** no Android companion, no in-app Markdown authoring, no
autocomplete in the editor, no synchronisation of progress between machines.

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
Command run and actual result:

```
$ python3 -m pytest tests/ -q
........................................................................ [ 51%]
....................................................................     [100%]
140 passed in 4.31s
```

Per file, all passing:

| File | Tests | Covers |
|---|---|---|
| `tests/test_db.py` | 23 | migrations, lesson progress, attempts, activity, settings, aggregates |
| `tests/test_compiler.py` | 19 | detection, compile success/failure, exit codes, timeouts, stop, memory limit, sandbox isolation |
| `tests/test_curriculum.py` | 19 | 16 lessons complete, ordering, parsing edge cases |
| `tests/test_providers.py` | 28 | configuration, parsing, malformed replies, HTTP failures, key hygiene |
| `tests/test_tutor.py` | 29 | assistance levels, prompts, response parsing, service integration |
| `tests/test_ui_smoke.py` | 22 | headless window construction, lesson loading, persistence, offline behaviour |

Total source: ~4,300 lines in `mentorsmith/`, ~1,600 lines in `tests/`.

Tests never touch the real database or a real provider: the database is
in-memory or in `tmp_path`, and the AI provider is always mocked. No test
costs money or requires network access.

## Data and migrations
- Database: `~/.local/share/mentorsmith/progress.db` (SQLite 3.51.2).
- Work directory for compiled code: `~/.local/share/mentorsmith/workdir/`.
- Both honour `XDG_DATA_HOME`.
- Schema version 1, applied via the ordered `MIGRATIONS` dict in
  `core/db.py`. Tables: `lesson_progress`, `exercise_attempts`, `activity`,
  `app_settings`.
- **Backup:** stop the app and copy `progress.db`. There is no sync and no
  automatic backup.
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
- **API keys come from the environment, never from the database or settings
  file.** Reason: keeps credentials out of anything that might be copied,
  committed or screenshotted. Tests enforce it.
- **The compiler is never invoked through a shell.** Reason: lesson text must
  never be interpreted as shell syntax.
- **Stale binaries are deleted before every compile.** Reason: a failed compile
  must never leave a previous executable behind that appears to run.
- **Sandbox is off by default.** Reason: it can break legitimate code that
  expects host access. It is opt-in and its state is always displayed.
- **UI never opens a database connection.** Reason: keeps persistence testable
  in isolation and schema changes in one file.
- **`parse_tutor_response` stays pure.** Reason: it is the tutor's most
  behaviour-defining logic and must be testable without a network.
- **Lesson content stays in Markdown files.** Reason: the handoff explicitly
  requires content not be buried in UI code.
- **No claim of success without real output.** Reason: the handoff is explicit
  that an LLM's claim is not proof.

## Notes for the next Space Bunny session
Read this file, `README.md`, `docs/architecture.md`, the relevant source and
the tests before editing. Verify the current state rather than assuming this
document is accurate.

The single most important unverified area is the **live AI provider path**.
Everything up to the HTTP boundary is tested with a fake; nothing has been
sent to a real vendor. Start there if asked to continue.

Re-run `python3 -m pytest tests/ -q` (expect 140 passing) and
`python3 main.py --check` before changing anything, so you know the starting
point.