# Architecture

How MentorSmith is put together, and why.

## Layers

```
        ┌──────────────────────────────────────────────┐
        │ ui/            Qt widgets, no business logic  │
        └───────┬──────────────────────────────┬───────┘
                │ signals / slots               │ reads
                v                              v
        ┌────────────────────┐    ┌──────────────────────────┐
        │ services/          │    │ core/                    │
        │ tutor levels,      │    │ db.py (only SQLite       │
        │ prompts, parsing   │    │ caller), curriculum.py   │
        └─────────┬──────────┘    └──────────────────────────┘
                  │ calls                          ^
                  v                                |
        ┌────────────────────┐          ┌──────────────────────────┐
        │ providers/         │          │ compiler/                │
        │ LLMProvider + HTTP │          │ detect, compile, run,    │
        └────────────────────┘          │ resource limits, bwrap   │
                                        └──────────────────────────┘
```

Three rules hold the shape together:

1. **`core/db.py` is the only module that opens a SQLite connection.** The UI
   never touches the database, so persistence can be tested on its own and
   schema changes live in exactly one file.
2. **`services/tutor.py` and `providers/` contain no Qt imports.** Tutor
   behaviour is therefore testable headlessly and without a provider.
3. **Lesson content is Markdown on disk**, loaded by `core/curriculum.py`.
   Editing a lesson never requires touching Python.

## Data flow for one turn

1. The learner presses **Compile & Run**.
2. `LessonView` hands the editor text to a `CompileWorker` (a `QThread`), so the
   window never freezes.
3. `Toolchain.compile` writes `main.cpp` into the work directory, deletes any
   stale binary, invokes the compiler as an argument vector, and captures its
   real diagnostics.
4. On success `Toolchain` starts the binary with `Popen`, applying POSIX
   resource limits through `preexec_fn` and optionally wrapping it in `bwrap`.
   `start_new_session=True` puts it in its own process group so **Stop** can
   kill the whole tree, not just the direct child.
5. The result is rendered verbatim: command, compile status, stdout, stderr,
   exit code, duration.
6. `MainWindow` records the attempt in SQLite — `compiled_ok` and `ran_ok`
   record what actually happened, never what the tutor asserted.

## Data flow for a tutor turn

1. `LessonView` snapshots the current lesson, code and output into a
   `TutorContext` and emits `tutor_requested`.
2. `MainWindow` builds a `TutorService` at the chosen level and runs
   `TutorService.ask` on a `TutorWorker` thread.
3. `build_system_prompt` encodes the level rules. `hint` and `guided`
   explicitly forbid the `SOLUTION` tag unless the learner asks.
4. The provider adapter sends one `POST /chat/completions` and normalises the
   reply, or raises a typed error (`ProviderAuthError`, `ProviderRateLimited`,
   `ProviderTimeout`, …) that the chat panel shows verbatim.
5. `parse_tutor_response` reads the tagged format. It is **pure and I/O-free**
   so it is unit-testable, and it degrades gracefully: an untagged reply becomes
   the message rather than an empty bubble.

## Error handling policy

Every failure mode a learner can hit gets a specific, actionable message:

| Situation | Result |
|---|---|
| No compiler installed | `CompilerNotFoundError` naming `g++`/`clang++` and the `dnf` command |
| Compile failed | The compiler's own diagnostics, shown unmodified |
| Program crashed | Exit code and stderr, labelled as a failure |
| Runtime timeout | Stated as a timeout, with the limit that was hit |
| Sandbox requested but unavailable | The status line says the sandbox is **not** active |
| API key missing / wrong | Message naming the environment variable to set |
| Provider rate limiting | Message that it is temporary, plus `Retry-After` when supplied |
| Provider returned HTML | Message that the base URL probably points at a web page |

`CommandResult.combined_output` returns `"(no output)"` rather than an empty
string, so the UI never shows a blank panel and implies nothing went wrong.

## Security decisions

- **No credentials anywhere persistent.** Keys come from
  `MENTORSMITH_API_KEY` at request time. `tests/test_providers.py` asserts the
  key never reaches an error message or the settings file.
- **No shell.** The compiler and learner programs are invoked as argument
  vectors, so lesson text is never interpreted as shell syntax.
- **Bounded output.** Captured stdout/stderr is truncated at 200,000 characters
  so a runaway program cannot exhaust memory.
- **`RLIMIT_NPROC` is deliberately not set.** It counts processes per *real
  UID*, so a value low enough to matter also breaks `fork` for the learner's
  own unrelated programs. In testing, a limit of 64 made `bwrap` fail with
  `EAGAIN` because the account already had more than 64 live processes.
- **Honest sandbox reporting.** `Toolchain.sandbox_status()` returns the exact
  wording shown in the UI, and distinguishes "requested but unavailable" from
  "active". `tests/test_compiler.py` verifies the isolation empirically by
  attempting to read and write the host filesystem from inside the sandbox.

## Schema versioning

`core/db.py` holds an ordered `MIGRATIONS` dict. `Database.migrate()` reads
`PRAGMA user_version` and applies every entry newer than that, then records the
new version. Adding a schema change means appending an entry and never editing
a released one. Because `connect()` always calls `migrate()`, an old database
upgrades on next launch, which is the same code path as creating a fresh one.

## Things worth knowing before extending this

- **Lesson format** is documented at the top of `core/curriculum.py`. A lesson
  needs all seven sections; `tests/test_curriculum.py` enforces it.
- **`parse_tutor_response` must stay pure.** If you add provider-specific
  parsing, do it in `providers/`, not in the parser.
- **Never block the GUI thread.** Compile/run and tutor calls both use worker
  threads. Adding a third blocking call means adding a worker.
- **`sandbox_status()` text is user-facing.** Changing it changes what the app
  claims about its own safety. Keep it accurate.