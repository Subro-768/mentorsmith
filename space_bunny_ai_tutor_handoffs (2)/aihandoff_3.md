# AI HANDOFF — PHASE 3
## Android learning companion

Continue the existing project as Space Bunny Free. Linux remains the main environment for coding, compiling, running, and debugging. Android is for lessons, quizzes, revision, tutor chat, and progress.

## Workflow
Read `PROJECT_STATE.md`, README, architecture notes, schemas, API contracts, and tests. Run current tests and record the baseline. Inspect data models before designing sync. Plan briefly and implement in small pieces. Preserve Linux functionality and data. Do not claim device tests were run unless they were. Ask before paid infrastructure or major authentication changes. Keep summaries focused.

## 1. Android stack
Use Kotlin, Jetpack Compose, Material 3, Room, coroutines, and a suitable HTTP client. Separate UI, presentation logic, repositories, local storage, and remote service code without unnecessary layers. Check dependency compatibility. Do not share Python code directly with Kotlin; share documented data formats and API contracts.

## 2. Mobile experience
Build phone-appropriate screens for dashboard, curriculum, lessons, AI tutor chat, quizzes, predict-output challenges, bug-identification exercises, revision, project requirements/milestones, history, and settings. Do not shrink the desktop UI; optimise readability and touch controls.

## 3. Keep complex execution on Linux
Android must not pretend code was compiled or executed if no compiler/runtime actually ran. Support reading code, conceptual exercises, short snippets, hints, and project requirements. Clearly mark tasks that should be continued on Linux.

## 4. Sync
Inspect whether an API already exists. If needed, consider a small documented FastAPI backend only when justified. Do not add cloud services for fashion.

Define stable IDs and conflict handling for lesson completion, exercise attempts/results, concept review, project milestones, and relevant preferences. Prefer preserving history over overwriting newer data. Document and test conflict rules.

Never expose privileged provider API keys in the Android APK. If Android needs remote AI, use a properly secured backend or another documented safe design. Do not embed a shared secret in the app.

## 5. Offline behaviour
Keep downloaded lessons and progress available locally. Queue eligible updates offline. Clearly show locally saved, waiting to sync, synced, conflict, and failure states. Never show “synced” until confirmed by the server.

## 6. Privacy/security
Validate remote data. Implement authentication properly if accounts are needed. Avoid unnecessary personal data collection. Do not silently upload whole source files or project directories. Make external AI data sharing clear.

## 7. Tests
Test navigation, local persistence, offline use, sync, conflicts, malformed responses, provider failures, and lifecycle changes. Add repository/ViewModel/data transformation tests. Use emulator or physical device if available and state exactly what was tested.

## Acceptance checklist
- [ ] Android app builds and launches
- [ ] Lessons, quizzes, and tutor work
- [ ] Progress persists locally
- [ ] Offline behaviour is explicit
- [ ] Sync works when configured
- [ ] Conflict handling is documented/tested
- [ ] Linux/Android data formats are compatible
- [ ] Linux still works
- [ ] Actual test results recorded
- [ ] Setup docs updated

## Handoff
Update `PROJECT_STATE.md` with Android architecture, API contract, sync/conflict behaviour, offline limits, build commands, tests, and issues. **Do not start Phase 4 until I approve.**
