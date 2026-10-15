# MentorSmith

A Linux-first desktop tutor for learning C++ fundamentals, built with Python and
PyQt6.

MentorSmith compiles and runs **your own code** and shows you the real compiler
and runtime output, then pairs each lesson with an AI tutor that supports three
levels of help. The goal is understanding, not generated answers.

---

## What it does

- **16 beginner C++ lessons**, from program structure to exceptions. Each has
  objectives, an explanation, a worked example, knowledge checks, an exercise
  with starter code, common mistakes, and a recap. The content lives in
  Markdown under `mentorsmith/lessons/`, not inside the UI code.
- **Real compile and run** with `g++` or `clang++`, showing the exact command,
  the compiler's own diagnostics, stdout and stderr separately, the exit code
  and the wall-clock time. Failures are displayed honestly and are never
  dressed up as success.
- **A code editor** with C++ syntax highlighting and a line-number gutter.
- **An AI tutor** with three assistance levels:
  - *Hint* — one small clue, no answer.
  - *Guided* — leading questions, one step at a time.
  - *Full explanation* — the worked solution with reasoning.
  Lower levels never volunteer the answer first, but you can ask for the full
  explanation at any time.
- **Progress that persists** in a local SQLite database: lesson completions,
  every compile attempt and what actually happened, and a recent-activity feed.
- **A dark theme** and a plain, readable layout.

## Requirements

- Fedora Linux (other Linux distributions should work)
- Python 3.11 or newer
- PyQt6
- A C++ compiler — `gcc` or `clang`

Check what you have:

```bash
python3 --version
g++ --version
```

## Install

```bash
sudo dnf install python3-pip gcc bubblewrap
python3 -m pip install --user PyQt6
```

`bubblewrap` is optional but recommended; see [Running your code](#running-your-code-sandbox-and-limits).

Run it straight from the checkout — no install step or packaging is required:

```bash
cd "/home/subro/Documents/APPS/programming tutor space bunny"
python3 main.py
```

To confirm the install without opening a window:

```bash
python3 main.py --check
```

That builds the entire UI headlessly and prints what was found:

```
MentorSmith 0.1.0
  lessons loaded : 16
  pages built    : 3
  compiler       : g++ (g++ (GCC) 16.2.1 20260819 (Red Hat 16.2.1-2))
  sandbox        : INACTIVE
  database       : /home/subro/.local/share/mentorsmith/progress.db
```

## Configuring the AI tutor

Everything else works without the AI. To enable the tutor you need three
things.

**1. Export your API key.** Keys are read from the environment and are never
written to the settings file, the database, or a log:

```bash
export MENTORSMITH_API_KEY="your-key-here"
```

Restart the app after exporting.

**2. Enter the endpoint and model** in **Settings**:

- **Base URL** — the API root. Most providers want something ending in `/v1`,
  for example `https://your-provider.example/v1`.
- **Model** — the exact model name your account can use.

No provider or model is hardcoded, and nothing assumes free or unlimited
access.

**3. Press "Test connection".** This sends one small real request and reports
what came back, so you find out now rather than mid-lesson.

The app speaks the widely used `POST /chat/completions` shape, so one adapter
covers most hosted models.

### When your code leaves the machine

Only when you send a message, MentorSmith sends the following to your provider:
the lesson title and objectives, the code in the editor, the compiler and
runtime output on screen, and your message. Nothing is sent otherwise, and the
chat panel says so at all times.

To block every AI call:

```bash
export MENTORSMITH_OFFLINE=1
```

Or tick the box in Settings. Lessons, compiling, running and progress tracking
keep working; the tutor explains that it is offline instead of pretending.

## Running your code: sandbox and limits

Your code is untrusted input, so it is contained rather than trusted. Two
layers apply:

**Always on — resource limits.** CPU time, address space, file size and core
dumps are capped for the child process only.

**Optional — bubblewrap sandbox.** Enable it in Settings. It then runs your
program in a private mount namespace with no network and a read-only view of
the system, so your program cannot read or write your home directory.

**This is defence in depth, not a real sandbox.** `bwrap` relies on unprivileged
user namespaces, and those give far less protection than a VM or a properly
configured container. Do not treat it as isolation you can safely run genuinely
hostile code in. With the sandbox off (the default), your program runs as your
own user with your own file access. The status bar always states which mode is
actually in force — the app never claims protection it does not have.

Your code is compiled and run in a dedicated directory:

```
~/.local/share/mentorsmith/workdir/
```

Compiled binaries and objects never touch the source tree.

## Tests

```bash
python3 -m pip install pytest
python3 -m pytest tests/ -q
```

The suite covers database operations and migrations, curriculum parsing,
tutor prompting and response parsing, provider error handling (with the network
replaced by a fake), compiler detection, successful and failed compilation,
runtime timeouts, stopping a running program, memory limits, sandbox isolation,
and a headless UI smoke test.

Compiler-dependent tests skip themselves if no compiler is present. AI is
always mocked, so the suite runs offline and costs nothing.

## Project layout

```
main.py                     Entry point (--check builds the UI headlessly)
mentorsmith/
  app.py                    QApplication bootstrap
  config.py                 Paths and non-secret settings
  lessons/                  The 16 lessons, as Markdown
  core/
    db.py                   SQLite persistence, schema migrations
    curriculum.py           Lesson loading and the file format
  compiler/
    toolchain.py            Detect, compile, run, contain
  providers/
    base.py                 Provider interface and typed errors
    openai_compat.py        /chat/completions client, stdlib only
  services/
    tutor.py                Assistance levels, prompts, response parsing
  ui/                       Qt widgets (theme, editor, panels, window)
tests/                      pytest suite
docs/                       Architecture notes
```

Only PyQt6 is required at runtime; HTTP uses the Python standard library, so
there is no third-party HTTP dependency.

## Keyboard shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+R` | Dashboard |
| `Ctrl+L` | Lessons |
| `Ctrl+P` | Progress |
| `Ctrl+Shift+P` | Compile and run the current lesson |
| `Ctrl+,` | Settings |
| `Ctrl+Enter` | Send a chat message |

## Known limitations

- Linux desktop only. The Android companion is not built yet.
- The in-app Markdown renderer covers the subset the lessons use, not the
  whole specification.
- There is no built-in test suite for the learner's own C++ lessons; the
  examples are verified by the compiler when you press **Compile & Run**.
- The editor has no autocomplete or undo history beyond Qt's built-in support.
- Progress is per-machine and not synchronised anywhere.

## Licence

Personal project. See `PROJECT_STATE.md` for current status and next steps.