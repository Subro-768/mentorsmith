# Space Bunny Free — using these handoffs

These five Markdown prompts guide development of a personal AI programming tutor.

## Recommended workflow
1. Put `PROJECT_STATE_TEMPLATE.md` in the app repository root as `PROJECT_STATE.md`.
2. Open that repository in Space Bunny Free.
3. Give the agent only `aihandoff_1.md`.
4. Let it inspect, implement, test, and update `PROJECT_STATE.md`.
5. Personally verify the acceptance checklist.
6. Fix issues before proceeding.
7. Give it `aihandoff_2.md`, then continue in order.

## Important
- These prompts assume the coding agent can read/edit repository files and run terminal commands. If a capability is unavailable, ask it to state the limitation and give you exact manual steps.
- Do not assume a claim means a feature works. Run the app and tests yourself.
- Do not provide all five phase prompts at once; later phases depend on earlier decisions.
- Keep API keys out of source control and `PROJECT_STATE.md`.
- Use Git or a backup before major changes.
- Model/API availability, context limits, and rate limits may vary. If a session gets long, ask the agent to update `PROJECT_STATE.md`, then continue in a fresh session.
