# PROJECT_STATE.md

## Current state
- Current phase: **All five phases complete**, plus a reliability audit that
  found two real defects (see below). Order was 1 → 2 → **4** → 3 → 5
  (see "Why Phase 4 came before Phase 3" below).
- Last updated: 2026-10-19
- Branch / repository status: `master`, 13 commits, clean tree. No remote.
- App launch status: **Launches on Fedora 44**, ten pages, verified by
  constructing the window offscreen (`python3 main.py --check`) and by rendering
  every screen.
- Android status: **APK builds and runs its unit tests.** No device or emulator
  test has been run — see "Android: what was and was not verified".

## Why Phase 4 came before Phase 3
Phase 4 adds a *language* dimension to concepts, progress and exercises. Phase 3
requires Android to sync "progress per language". Building Android first would
have meant writing a schema and sync contract with no language dimension, then
rewriting both. Doing 4 first meant the Android Room schema, the sync contract
and the mastery rules were all written once, correctly. Linux-first also
de-risked it: if the Android toolchain had failed on JDK 25 / AGP, Phases 2 and
4 would already be banked. **This was a deliberate reordering, not an oversight.**

## Baselines recorded
| Point | Python tests | Schema |
|---|---|---|
| Start of Phase 2 | 140 | 1 |
| Start of Phase 4 | 299 | 2 |
| Start of Phase 3 | 362 | 3 |
| After Phase 3 | 385 | 3 |
| Start of Phase 5 | 385 | 3 |
| After Phase 5 | **576** | 3 |
| After the §9 audit | 602 | **4** |
| After the §6 offline work | **627** | 4 |
| After branding, install and Java track | 712 | 4 |
| After the icon/analytics/theme fixes | 837 | 4 |
| After the AI key, model picker, dialog and theory work | **956** | 4 |

All earlier tests still pass unchanged. Android adds **41** JVM unit tests.

### Defects found after Phase 5

Beyond the §9 audit, a further review of the code added during Phase 5 and the
Java track turned up these, all now fixed:

| Where | Defect | How it survived |
|---|---|---|
| `ui/analytics_view.py` | XP comment said 10 per lesson; the line below awarded 20 | The file had no tests at all |
| `ui/analytics_view.py` | Level bar seeded `setValue(10)` — a fabricated 10% | `refresh()` overwrote it, so every test that did not check passed |
| `ui/analytics_view.py` | At the top level: "12000 XP (Next level at 10000 XP)" | `_calculate_level` invented `threshold * 2` past the last level |
| `ui/analytics_view.py` | Heatmap said "LAST 90 DAYS", drew 90–96 | Whole-week column alignment, undocumented |
| `ui/theme/Theme.kt` | Android shipped VS Code Dark+ under a comment claiming it was the desktop palette | A colour mismatch is not an error |
| `tools/install_desktop.py` | Wrote an `index.theme` into the user's shared `hicolor`, making unrelated icons invisible | Nothing on disk changed, so nothing showed why |
| `execution/java.py` | Claimed "the JVM provides its own memory isolation" — it does not; a runaway exercise got 4 GB of heap | `limit_memory=False` is necessary (RLIMIT_AS kills a JVM), so nothing was bounding it |
| `execution/java.py` | `java -version` on Java 8 gives `1.8.0_x`; the parser emitted `--release 1`, which javac rejects | Only manifests on a JDK this machine does not have |
| `core/theory.py` | `lru_cache` returned a mutable list shared by every caller | Nothing mutated it yet — which is the reason to close it |
| `core/theory.py` | A chapter that failed to parse vanished behind a `print` a GUI never shows | A missing chapter looks exactly like one never written |
| `ui/settings_dialog.py` | Grew taller than the screen; Save/Cancel below the fold, no scroll, no resize | Only visible by opening it on a real display |

The recurring lesson is that these are all *silences*: a value that is
plausible-looking but false, a comment that contradicts the line beneath it, a
palette that is merely different. None of them raise. Each now has a test that
fails when the silence comes back.

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
A layered PyQt6 desktop app plus a Kotlin/Compose companion. Implemented, not
planned:

- **`core/db.py`** — the only module that opens a SQLite connection. Holds an
  ordered `MIGRATIONS` dict applied through `PRAGMA user_version`, so an old
  database upgrades on next launch by the same path that creates a new one.
- **`core/curriculum.py`** — parses lesson Markdown with a small front-matter
  and section parser. No third-party Markdown dependency.
- **`core/curriculum_registry.py`** — one entry point per language. Hides the
  fact that C++'s data predates the per-language layout, so callers only ever
  ask for a language id.
- **`lessons/<language>/`** — 54 Markdown files across five languages. Content
  is never embedded in UI code.
- **`execution/`** — introduced in Phase 4. `base.py` holds what is genuinely
  shared (tool detection, the process runner, POSIX resource limits, stoppable
  process groups); `compiled.py` and `interpreted.py` hold the two shapes of
  build-then-run; `cpp.py`, `c.py`, `python.py`, `javascript.py` supply only the
  command lines and diagnostics that must differ.
- **`compiler/toolchain.py`** — kept as a **compatibility shim** over
  `execution/cpp.py` so Phase 1–3 imports, saved settings and tests are
  unchanged. Deprecated; new code should use `execution`.
- **`core/comparisons.py`** — curated cross-language comparisons. Deliberately
  about *differences*: a comparison that only said "these are the same" would
  teach the wrong thing.
- **`providers/`** — a small `LLMProvider` interface plus one
  `/chat/completions` adapter using only the standard library. Typed errors for
  auth, rate limiting, timeout, network and malformed responses.
- **`services/tutor.py`** — the three assistance levels, prompt construction and
  `parse_tutor_response`, which is pure and free of both Qt and I/O so it is
  directly unit-testable.
- **`ui/`** — dark theme, line-numbered code editor with a `QSyntaxHighlighter`
  C++ highlighter, lesson view, dashboard, progress view, settings dialog and
  main window. A language selector sits in the toolbar; switching rebuilds the
  track's widgets and re-creates the execution adapter.
- **`android/`** — Compose + Room. `domain/` is pure Kotlin with no Android
  types so it unit-tests on the JVM; `data/` holds Room and the sync client;
  `ui/` holds screens and one shared ViewModel.
- **`sync_server/`** — optional FastAPI + SQLite backend implementing
  `docs/sync-contract.md`.

Design rationale is in `docs/architecture.md`.

## Important files
| File/path | Purpose | Status |
|---|---|---|
| `main.py` | Entry point; `--check` builds the UI headlessly | Done, verified |
| `mentorsmith/config.py` | Paths and non-secret settings only | Done, verified |
| `mentorsmith/core/db.py` | SQLite persistence + migrations | Done, 23 tests |
| `mentorsmith/core/curriculum.py` | Lesson Markdown loading | Done, 19 tests |
| `mentorsmith/lessons/cpp/*.md` | 16 C++ lessons | Done, all 16 verified complete |
| `mentorsmith/lessons/{python,c,javascript}/*.md` | 26 lessons across 3 new tracks | Done, all verified complete |
| `mentorsmith/core/curriculum_registry.py` | Per-language entry point | Done, tested |
| `mentorsmith/core/comparisons.py` | Cross-language differences | Done, 7 comparisons |
| `mentorsmith/execution/` | Per-language adapters + shared runner | Done, 61 tests |
| `mentorsmith/compiler/toolchain.py` | Compatibility shim over `execution/cpp.py` | Done, 19 tests still pass |
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
| `docs/architecture.md` | Architecture and design rationale | Needs a Phase 3/4 update |
| `docs/adding-a-language.md` | Procedure for a fifth language | Done |
| `docs/sync-contract.md` | Wire format, conflict rules, privacy | Done |
| `tools/export_curriculum.py` | Publishes curriculum for Android | Done, `--check` mode works |
| `sync_server/` | Optional sync backend | Done, 23 tests |
| `android/` | Kotlin/Compose/Room companion | Builds; **never run on a device** |

## Implemented features
Verified by the test suite and by rendering the UI:

- [x] App launches on Linux (window constructed and rendered; `--check` passes)
- [x] 16 C++ lessons load, each with all seven required sections, example code,
      starter code and at least three answered knowledge checks
- [x] Language selector in the toolbar; switching reloads lessons, concepts,
      exercises and the execution adapter, and scopes progress per language
- [x] Lesson navigation with correct previous/next boundaries
- [x] Code editor with C++ syntax highlighting and line numbers
- [x] Compile and run with `g++`; stdout and stderr shown separately
- [x] Compile failures shown with the compiler's own unmodified diagnostics
- [x] Non-zero exit codes reported as failures, not success
- [x] Runtime timeout enforced and reported as a timeout
- [x] Stop button terminates a hanging program (verified with `for(;;){}`)
- [x] Memory limit refuses an unbounded allocation
- [x] `bwrap` sandbox, on by default where bubblewrap is installed; verified to
      block host filesystem reads *and* writes from inside the sandbox
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

- [x] Concept model with 65 concepts and an explicit prerequisite graph,
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

**Not implemented:** no exercise authoring UI, no spaced-repetition scheduler (a
fixed staleness threshold is used instead), and project milestones are tracked
but not auto-graded.

### Phase 4 (aihandoff_4.md) — Python, C and JavaScript

- [x] Shared learning model; language-specific tooling. No differences abstracted
      away that actually matter.
- [x] Execution adapters for all five languages, verified by *running* each one
- [x] C++ curriculum preserved intact: still 16 lessons, 18 concepts, 53 exercises
- [x] Python 9 lessons / 9 concepts / 12 exercises
- [x] C 9 lessons / 9 concepts / 11 exercises
- [x] JavaScript 8 lessons / 8 concepts / 11 exercises
- [x] **63 lessons, 65 concepts, 111 exercises** total
- [x] Schema v3 adds `language`; the same lesson id in two languages is two
      achievements, and v1/v2 data survives (tested against a hand-built v2 db)
- [x] **Mastery never transfers between languages** — a C++ pointer label says
      nothing about C pointers
- [x] Cross-language comparisons, focused on where the semantics genuinely differ
- [x] `docs/adding-a-language.md` documents the whole procedure

### Phase 3 (aihandoff_3.md) — Android companion

- [x] Kotlin + Compose app, builds to a 17.5 MB debug APK
- [x] Room schema mirroring the desktop, `language` in every key
- [x] Bundled curriculum for all five languages (exported, not copied by hand)
- [x] Documents/offline-first: a row is `synced` only after server confirmation
- [x] Sync queue with `local / pending / synced / conflict / failed`
- [x] Sync contract documented in `docs/sync-contract.md`
- [x] Optional FastAPI sync backend implementing it, with conflict rules
- [x] **No credentials in the app** — enforced by a test that reflects over
      `SyncClient`'s fields
- [x] 41 JVM unit tests covering parsing, validation, mastery parity, sync
      error handling and output comparison

**Not implemented, and deliberately so:**
- **Tutor chat on Android is disabled.** An APK is not a secret store; a key
  compiled into it is a published key. Chat needs the backend first. The app
  says this plainly rather than showing a broken chat box.
- **Android never executes code.** That stays on Linux.
- The sync backend has **no authentication**, because Phase 3 required asking
  before adding it and a local single-user server does not need it. The
  consequence — anyone who can reach the port can read and write progress — is
  stated in the contract document rather than buried.
- No offline model for tutor chat (there is no model on the device at all).

### Phase 5 (aihandoff_5.md) — developer tools, reliability, portfolio

- [x] **Git integration** with a two-step approval gate on commits
- [x] **No push, checkout, reset, clean or stash** in the module at all
- [x] **Project workspaces** with path validation after resolution
- [x] **Code review** with `confirmed` / `heuristic` / `speculative` origins,
      where only a confirmed finding counts as a defect
- [x] **Compiler diagnostics merged** into the same finding list, origin intact
- [x] **Test generation** that proposes, never auto-runs, and always reports
      proposed versus executed
- [x] **Security audit** that runs real code and states what it does *not* prove
- [x] **Delayed-review analytics** distinguishing recall from transfer
- [x] **Offline gate enforced at the socket**, not in a caller (§6, §7)
- [x] **Bounded output reading** (see below — this was a real bug)
- [x] Developer page wired into the desktop UI, 31 smoke tests
- [x] README and this document updated to match the code

**Not implemented, deliberately:**
- **No authentication on the sync backend.** Phase 3 required asking first.
- **No AI review or test generation without a provider.** The deterministic
  checks still run and are reported as the confirmed findings.
- **No offline model.** Offline means everything except the tutor's AI
  features, and the docs say exactly that.
- **No release build, no packaging, no store listing.** `assembleRelease` is
  untested and signing is not configured.

### Two defects found by the Phase 5 reliability audit (§9)

Phase 5 §9 says to prioritise real risks over additions. Two were found, both
of which made a documented feature untrue:

1. **Reviews were never persisted.** Phase 2 documented "concepts can be flagged
   for review". They were computed and displayed, and `persist_reviews()` existed
   and was tested — but nothing called it, so the `reviews` table stayed empty
   forever and `close_review()` had no rows to act on. Now called from
   `insights.build_report`, deduplicated on `(concept, language, open)`.
2. **Phase 4's language isolation was incomplete.** Schema v3 covered two of
   the eight progress tables. Fixed by migration 4 (above).

Dead code removed after verifying each was unreferenced:
`execution.export_path`, `exercises.for_concepts`,
`practice.needs_attention`, `code_editor.set_markdown`,
`dashboard.select_lesson`, `insights.label_glossary`.

`LABEL_DESCRIPTIONS` was written in Phase 2 and never surfaced in the UI. It is
now a "What the labels mean" legend under the Progress table, so a bare label
like `strong` is explained rather than shown bare.

### A third defect: the offline switch was UI-only (§6, §7)

`MENTORSMITH_OFFLINE=1` was checked in `main_window._refresh_provider_status`
and nowhere else. That means any code path using the provider directly could
still open a socket while the user believed they were offline — including the
Phase 5 developer tools written the same day. The gate now lives inside
`complete()`, the only function that sends anything, and
`tests/test_offline.py` asserts that even a direct `urlopen` is never reached.

`tests/test_offline.py` also disables the socket layer outright and checks that
every language still compiles and runs, that lessons load, that the dashboard
builds, that the security audit runs, and that read-only git works. "Offline"
is verified behaviour, not a claim in a README.

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

### Build and test the Android app
```bash
python3 tools/export_curriculum.py      # refresh bundled assets
cd android
./gradlew :app:assembleDebug            # -> app/build/outputs/apk/debug/app-debug.apk
./gradlew :app:testDebugUnitTest        # 41 tests
```

Requires **JDK 17–21**. AGP 8.7.3 refuses to run on JDK 25 (it fails with the
bare version number as the error message, which is not helpful). Temurin 21 was
downloaded to `~/jdk/jdk-21.0.12.1+1` for this machine; set
`JAVA_HOME` to any JDK 17–21. `ANDROID_HOME` must point at an SDK with
platform 35.

### Run the optional sync backend
```bash
python3 -m pip install fastapi uvicorn
uvicorn sync_server.app:app --host 127.0.0.1 --port 8000
```
Bind to localhost. It has no authentication; see `docs/sync-contract.md`.

### Verify the exported curriculum is current
```bash
python3 tools/export_curriculum.py --check    # non-zero if assets are stale
```

## Tests
Command run and actual result after Phase 3:

```
$ python3 -m pytest tests/ -q
385 passed in 21.81s

$ cd android && ./gradlew :app:testDebugUnitTest --console=plain
BUILD SUCCESSFUL
  CurriculumParserTest       8 tests, 0 failed
  SyncClientTest            13 tests, 0 failed
  MasteryTest               11 tests, 0 failed
  BundledCurriculumTest      5 tests, 0 failed
  OutputNormalisationTest    4 tests, 0 failed
  TOTAL: 41 tests, 0 failed
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
| `tests/test_phase4_languages.py` | 61 | adapters per language, real execution, isolation, comparisons, curriculum |
| `tests/test_sync_server.py` | 23 | HTTP endpoint, idempotency, monotonic completion, milestone conflicts |

Android (`android/app/src/test/`):

| File | Tests | Covers |
|---|---|---|
| `CurriculumParserTest` | 8 | format version refusal, dangling references, missing fields |
| `BundledCurriculumTest` | 5 | the four **shipped** assets parse, every lesson complete, no uncovered concepts |
| `MasteryTest` | 11 | parity with the desktop rules, repeated-error downgrade, clamping |
| `SyncClientTest` | 13 | offline handling, retryable vs not, newer-client refusal, conflict surfacing, no-credential invariant |
| `OutputNormalisationTest` | 4 | trailing whitespace, missing final newline, CRLF |

Tests never touch the real database or a real provider: the database is
in-memory or in `tmp_path`, and the AI provider is always mocked. No test costs
money or requires network access. Compiler-dependent tests skip themselves if
no compiler is present.

## Android: what was and was not verified

Stated plainly because the distinction matters:

**Verified by actually running the commands:**
- `./gradlew :app:assembleDebug` → BUILD SUCCESSFUL, `app-debug.apk`, 17.5 MB
- The APK contains `assets/curriculum/{cpp,python,java,c,javascript}.json` (checked
  with `unzip -l`)
- The manifest requests only `INTERNET` and `ACCESS_NETWORK_STATE`
- `./gradlew :app:testDebugUnitTest` → 41 tests, 0 failures

**Not verified — no claim is made about any of this:**
- **No emulator or physical device test.** `/dev/kvm` exists and the SDK has
  platform 35, but there are **no AVDs, no system images and no `sdkmanager` or
  `avdmanager` installed**, so no system image could be downloaded or booted.
- The app has therefore never been seen running. Screens are untested on a real
  display, and no Compose UI test exists.

To do it: install `cmdline-tools`, `sdkmanager "system-images;android-35;google_apis;x86_64"`,
create an AVD, then
`./gradlew :app:installDebug` with an emulator running.

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
- Work directory for compiled code: `~/.local/share/mentorsmith/workdir/<language>/`.
- Both honour `XDG_DATA_HOME`.
- Schema version **4**.
  - v1 → Phase 1.
  - v2 → Phase 2, **strictly additive**: nine `ALTER TABLE ... ADD COLUMN`
    statements with defaults, plus five new tables.
  - v3 → Phase 4, adds `language` to `lesson_progress` and `exercise_attempts`.
    This one **rebuilds a table**, because `lesson_progress` was keyed by
    `lesson_id` alone and ids can now repeat across languages. SQLite cannot add
    a column to a primary key, so the table is created, copied, dropped and
    renamed. Every existing row is preserved with `language='cpp'`, which is
    correct because C++ was the only track at the time.
  - v4 → the Phase 5 audit, which found that **Phase 4 had missed four tables**.
    `reviews`, `projects`, `project_milestones`, `concept_progress`, `activity`
    and `project_activity` had no `language` column at all, so a C++ pointer
    review was indistinguishable from a C pointer review, project progress
    leaked across tracks, the activity feed showed one track's events in
    another, and `concept_progress` — a cache of per-language mastery — could
    serve one track's label for another. Four plain `ADD COLUMN`s plus two table
    rebuilds (`concept_progress`, `projects`).
- Tables: `lesson_progress`, `exercise_attempts` (now carrying Phase 2
  evidence columns and a language), `activity`, `app_settings`, `concept_progress`,
  `projects`, `project_milestones`, `project_activity`, `reviews`.
- **Upgrade safety is tested, not assumed.** `tests/test_phase2_data.py` builds
  a genuine schema-v1 database by hand, fills it with Phase 1 rows, opens it
  with the current code, and asserts every Phase 1 row survives. The v2→v3
  rebuild is verified the same way.
- **Backup:** stop the app and copy `progress.db`. No automatic backup.
- API keys are never stored here. Only non-secret settings are persisted.
- The Android app has its own Room database. It does **not** read the desktop's
  file; the only thing shared between the two is the exported JSON curriculum.

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
- **Output capture is capped at 200,000 characters while reading, not after.**
  This was a genuine bug. The original code buffered a child's entire output
  before truncating it; a program printing in a tight loop reached 13 GB on a
  16 GB machine and the kernel OOM-killed the process. Now 17 MB on the same
  input. `tests/test_retention.py` carries the regression.
- The learner's own exercises are not automatically unit-tested; examples are
  verified when the learner compiles them.
- There is no lesson-content editor in the UI; lessons are edited as Markdown.
- Progress is per-machine on the desktop. Android can sync via the optional local
  backend, but the desktop app does not sync.
- The Android app has never been run on a device or emulator (see above).
- Android exercises with code are graded by comparing the learner's *predicted*
  output, not by compiling. On Linux they are compiled and run for real.
- The sync backend stores progress in plaintext SQLite with no authentication.
- Exercise coverage is uneven: C++ has 53 exercises, the other tracks 11–12.
- `docs/adding-a-language.md` is a procedure, not an automated codegen path.

## Next steps
1. **Run the Android app on an emulator.** It builds and its logic is tested, but
   it has never been seen running. Install `cmdline-tools` first — that is the
   blocker, not the code.
2. Obtain an API key, configure a provider in Settings, and exercise the tutor at
   all three levels. This is still the largest untested surface, and now also
   gates Android tutor chat.
3. Add a `/v1/tutor` proxy to `sync_server` so Android chat can work without ever
   shipping a key. This is the natural next endpoint and is deliberately absent.
4. Review lesson content for technical accuracy. 63 lessons have been written and
   machine-checked for structure, but nobody has read them end to end.
5. Then Phase 5 (`aihandoff_5.md`): git integration, project workspaces, AI code
   review, test generation, security audit and portfolio docs.

## Exam preparation (SRM KTR)

Built to a handoff brief. The design is driven by one rule: a student must
always be able to tell what a question is.

- **Catalogue** (`mentorsmith/data/exam/courses.json`): one course,
  `21CSS101J Programming for Problem Solving`, B.Tech (All Branches),
  semester I/I, SRMIST KTR. Every field read from the paper headers or the
  course's own unit material, with the source recorded. The record is
  `PENDING_REVIEW`, not `VERIFIED`: nobody has checked it against official
  SRM material.
- **Question bank** (`mentorsmith/core/exam.py`): every question carries
  `source_type` (VERIFIED_PYQ / OFFICIAL_SAMPLE / ORIGINAL_PRACTICE /
  PREDICTED_PRACTICE) *and* `verification_status` (PENDING_REVIEW /
  VERIFIED / REJECTED). A question is only labelled a *verified* past
  question once a human has checked it against a file, page and question
  number.
- **The bank is not in the repository.** It lives in
  `~/.local/share/mentorsmith/exam/questions.json`, mode 0600, because past
  papers are the learner's material. `tools/import_exam_papers.py` builds
  it from their own PDFs.
- **The importer verifies nothing.** It copies the text verbatim, never
  invents an answer key, reports scanned papers as needing OCR, and flags
  OCR damage and layout noise for review.
- **Ungraded is not wrong.** The papers print no answer key, so most
  questions cannot be marked. Such an attempt is recorded and reported as
  *ungraded*, never as a mistake, and a session where nothing could be
  graded reports no score rather than 0%.
- **What was actually extracted:** 356 questions from the two clean-text
  question banks and the CT papers; 132 duplicates skipped; 15 of the 27
  supplied PDFs have no text layer and need OCR.
- **The human-check workflow exists.** `Check questions` in the Exam Prep
  screen walks the pending queue, shows the source page, and records the
  answer and who checked it. That is the only path to
  `verification_status=VERIFIED`, and therefore the only path to the
  "Verified past question" label.
- **A key that is not among the extracted options is flagged, not
  rejected.** It usually means the options were garbled by the
  extraction. Such a question is saved as checked but cannot be graded
  automatically, because a student could not have picked it.

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
- **The sandbox is on by default wherever bubblewrap is installed**, and its
  state is always displayed honestly. This reverses the earlier decision to
  leave it off: learner code is code the learner did not write, and running
  it with the user's own file access makes a stray path dangerous. Where
  bubblewrap is absent the setting stays off, because promising containment
  that is not there is worse than not promising it. The user's own choice
  is remembered - the default only applies to a setting never set.
- **UI never opens a database connection.**
- **Lesson and exercise content stays in data files**, not in UI code.
- **No claim of success without real output.**
- **Concept data is validated on load.** A broken prerequisite graph, an unknown
  concept reference, a cycle or a milestone with no acceptance criteria fails at
  startup rather than producing impossible recommendations.
- **Mastery does not transfer between languages.** Phase 4 requires it, and it is
  the correct call: being strong at C++ pointers says nothing about C pointers.
  A label is scoped by `(concept, language)` everywhere.
- **Android never executes code.** Phase 3 says keep complex execution on Linux.
  Predict-output on Android is a *prediction* plus a self-check, and the UI says
  the code did not run.
- **The Android app holds no credentials.** An APK is a downloadable artefact, so
  a key inside it is a published key. Enforced by a test that reflects over
  `SyncClient`'s fields looking for anything key/token/auth-shaped.
- **`synced` means the server said so.** Nothing is marked synced optimistically.
- **Sync preserves history over overwriting newer data.** Completion is
  monotonic; attempts and reviews are append-only and deduplicated by
  `client_id`; milestones merge by `updated_at` and a conflict is *reported*
  rather than silently resolved in favour of either side.
- **The sync backend has no authentication, on purpose**, because the phase
  required asking first. It must not be exposed to a network that matters. This
  is written in `docs/sync-contract.md`, not left implicit.
- **Python and desktop share only a JSON file format.** `tools/export_curriculum.py`
  is the only bridge. No Python code is imported from Kotlin and vice versa.
- **`RLIMIT_AS` is per language where the runtime demands it.** V8 reserves a
  large virtual address space before running any user code, so Node gets 4 GiB
  of address space and a real `--max-old-space-size` cap instead. Measured on
  this machine: 1 GiB kills Node, 2 GiB works.
- **`RLIMIT_NPROC` is still not set**, for the reason in "Known bugs".

## Notes for the next Space Bunny session
Read this file, `README.md`, `docs/architecture.md`, the relevant source and
the tests before editing.

Re-run `python3 -m pytest tests/ -q` (expect **385 passed**),
`python3 main.py --check`, and `python3 tools/export_curriculum.py --check`
(expect exit 0) before changing anything. If you touch Android:
`cd android && ./gradlew :app:testDebugUnitTest` (expect **41 tests**) with
`JAVA_HOME` set to a JDK 17–21.

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