# AI HANDOFF — PHASE 1
## Build the Linux-first C++ learning tutor

You are Space Bunny Free acting as my coding partner inside the existing repository. Implement this phase in small, verifiable steps—not as one giant code dump.

## Mandatory working style
1. **Inspect before editing.** Read the repository structure, README, dependency files, entry points, tests, and `PROJECT_STATE.md` if present. Do not assume documented features work.
2. **Plan briefly, then implement.** Give me a short plan naming likely files, then proceed unless genuinely blocked.
3. **Small changes.** Prefer focused edits over replacing whole files. Preserve working code.
4. **Use the terminal.** Run available tests/build checks. Never claim a command passed unless you ran it and saw the result.
5. **Be token-conscious.** Don't repeatedly print whole files or the repository. Summarise findings and show focused diffs.
6. **No fake completion.** No fake buttons, hardcoded success messages, or documentation claiming unimplemented features exist.
7. **Teach me.** After major components, explain their purpose, important files, data flow, and a couple of concepts I should understand.
8. **Preserve data.** Avoid destructive commands, deleting user data, or overwriting unrelated files. Ask before risky operations.
9. **Choose sensible defaults** for noncritical choices. Ask before major architecture/security/data decisions or paid services.
10. If you cannot run a test, say so and give me the exact command.

## Goal
Build a personal AI programming tutor that helps me understand fundamentals rather than depend on generated answers. I use Fedora Linux. I have some experience with Python, C, Kotlin, PyQt6, Git, and AI-assisted coding, but want stronger programming fundamentals. Linux is the first target; do not build Android yet.

## Stack
Use Python, PyQt6, SQLite, a configurable LLM API/provider, GCC or Clang when installed, and Git. Inspect and reuse good existing code. If the repo is empty, create a sensible structure. Avoid a backend or complex agent framework unless genuinely needed.

## UI
Build a usable dark-themed desktop app with:
- Dashboard and C++ curriculum navigation
- Lesson view and AI tutor chat
- Code editor with syntax highlighting if practical
- Compile and Run controls
- Compiler output and runtime error panels
- Exercise instructions and hint controls
- Basic progress view
- AI provider/model settings

Prioritise working behaviour and readability over decorative polish.

## C++ curriculum
Create maintainable beginner lessons for:
1. Program structure
2. Variables and types
3. Input/output
4. Operators
5. Conditions
6. Loops
7. Functions
8. Arrays and strings
9. Pointers
10. References
11. Basic memory concepts
12. Structures
13. Classes and objects
14. Constructors and encapsulation
15. File handling
16. Exceptions and error handling

Each lesson needs objectives, explanation, a small example, knowledge checks, an exercise, common mistakes, and a recap. Don't bury all content inside UI code.

## Tutor behaviour
Support three assistance levels:
- **Hint:** small clue, no full solution by default
- **Guided:** leading questions and stepwise help
- **Full explanation:** worked solution with reasoning

Ask me to predict output, explain code, find bugs, and write small programs. If I am wrong, explain the misconception and let me try again before revealing the answer unless I request a full explanation.

An LLM's claim is not proof that code works. Use actual compiler output, execution, and tests.

## Compile and run C++
Detect GCC/Clang availability. Let the user write, compile, run, stop, and inspect output/errors. Use a dedicated working directory, timeouts, and resource limits where available. Handle missing compilers clearly.

**Security:** learner code is untrusted. Never automatically execute arbitrary AI-generated shell commands. A subprocess timeout alone is not a sandbox. Use an appropriate isolation mechanism if available; otherwise document the risk and do not claim full sandboxing. Ask before enabling broad host access.

## AI provider
Use a small provider abstraction. Read credentials from environment variables or suitable local configuration; never commit credentials or log keys. Handle timeouts, rate limits, network failures, and malformed responses. Tell the user when code/prompts are sent to an external provider. Do not hardcode a particular OpenRouter model or assume free access is unlimited.

## Persistence
Use SQLite for lesson completion, exercise attempts/results, recent activity, assistance preference, and non-secret settings. Separate database access from UI. Version the schema or use migrations. Never store API keys in progress tables.

## Tests and docs
Test database operations, response parsing, AI failures, compiler detection, successful/failed compilation, runtime timeouts, and exercise recording. Mock AI in automated tests.

Create/update `README.md`, `PROJECT_STATE.md`, architecture notes, Fedora setup/run instructions, AI configuration, test instructions, and known limitations.

## Acceptance checklist
- [ ] App launches on Linux
- [ ] Lessons can be browsed
- [ ] Tutor works when configured
- [ ] C++ can compile and run
- [ ] Compilation/runtime failures are displayed honestly
- [ ] Progress persists after restart
- [ ] Tests were run and results recorded
- [ ] Docs match actual implementation
- [ ] No fake functionality is presented as complete

## Handoff
Update `PROJECT_STATE.md` with actual architecture, important files, commands, features, test results, bugs, and next steps. Report what works, what is incomplete, tests actually run, key decisions, and what I should understand before Phase 2. **Do not start Phase 2 until I approve.**
