---
name: ticket-resolution
description: The specific analysis procedure to follow when picking up a new ticket or issue before starting any implementation.
---

# Ticket Resolution & Analysis Procedure

When assigned a ticket or issue (e.g. "αναλαμβάνω το ticket X", "ξεκίνα να λύνεις το πρόβλημα"), you MUST stop and follow this strict analysis procedure before writing any code. As a Senior Backend Developer, you must fully understand the architectural impact of a change before modifying the codebase.

## Step 1 — Context Gathering
Before touching any files, gather all necessary information:
1. **Consult the LLM Wiki:** Check `docs/wiki/index.md` and read the relevant subsystem or concept page (`docs/wiki/concepts/*`, `docs/wiki/modules/*`) to understand architectural invariants and locate key modules.
2. **Identify the core problem:** What is the current behavior vs the expected behavior?
3. **Locate affected areas:** View the relevant routers, services, schemas, and Angular components/services to pinpoint exactly where the logic resides.
4. **Check dependencies:** Does this affect the frontend or backend contract? (e.g., changing a response schema will break the Angular client). Does this affect database integrity?

## Step 2 — Capability & Limitation Check
Before drafting a plan, evaluate your operational constraints:
- **Sandbox / Environment Restrictions:** Do you lack network access (e.g., `nsjail` blocking `curl`), required credentials, or tool capabilities?
- **Domain Boundaries:** Does the ticket require modifying frontend or backend code? Ensure changes follow project conventions (Signals, RxJS in Angular 19, Pydantic schemas in FastAPI).
- **Action:** If you hit any limitation that blocks you from analyzing or executing the task, you MUST immediately pause, clearly explain the limitation to the user, and ask for their assistance (e.g., "Please run this command on your terminal"). DO NOT attempt to bypass restrictions silently.

## Step 3 — Architecture, Security & Edition Analysis
Analyze the proposed change against the project's core principles:
- **Security / AuthZ:** Does this change require checking `owner_id` or a campaign role?
- **Data Integrity:** Will this change introduce race conditions in MongoDB? (Use atomic operators `$set`, `$inc`, `$push`, `$pull` instead of overwriting full documents).
- **Performance:** Will this block the event loop? (Ensure async functions or `run_in_threadpool` are used for blocking operations).
- **2014 vs 2024 Edition Parity & Split-Brain:** If D&D rules or character fields are affected, confirm both `"2014 Edition"` and `"2024 Revision (5.5e)"` paths and check Python (`backend/`) ↔ TypeScript (`client/src/app/core/rules/`) parity.

## Step 4 — Execution Mode Recommendation & Implementation Planning
Before writing any code, you MUST recommend the **most cost- and time-effective Execution Mode** for this ticket (based on scope, file overlap, stack split, and quota) and enter Planning Mode (`implementation_plan.md`):
- **Execution Mode Recommendation (tell the user explicitly before starting):**
  - **Solo** *(default)*: Best for 1–3 files, single-stack fixes, or sequential changes (lowest token/quota cost).
  - **Solo + `/grill-me` or `/plan`**: When requirements or UX/schema tradeoffs are ambiguous before coding.
  - **Solo + `/boost`**: When a single complex problem needs deeper reasoning/verification without multi-agent overhead.
  - **`/teamwork`**: When Backend, Frontend, and QA/Review split cleanly into non-overlapping files.
  - **`swarm`** *(Quota Heavy)*: Only when 3+ truly independent slices can execute in parallel with zero file collisions and sufficient quota — never recommend `swarm` for small/medium bugs.
- **Your plan (`implementation_plan.md`) must include:**
  1. **Recommended Execution Mode** (and short justification).
  2. **Goal Description:** A brief summary of the problem and the proposed solution.
  3. **Proposed Changes:** A file-by-file breakdown of what will be modified, added, or deleted.
  4. **User Review Required:** Highlight any breaking changes, database migrations, or frontend-impacting changes using GitHub alerts (`> [!WARNING]`).
  5. **Verification Plan:** How you will verify the fix (including explicit 2014 + 2024 tests when rules/data are touched).

**CRITICAL:** You must STOP and wait for the user to explicitly APPROVE the execution mode & implementation plan before writing any code.

## Step 5 — Execution & Validation
Once the user approves the plan:
1. Create a `task.md` artifact to track your progress as a checklist.
2. Implement the changes strictly following the approved plan.
3. If you discover a major blocker during execution, STOP, update the plan, and ask for review again.
4. Verify your changes across test suites (`pytest tests/`, `npm test`, `simulate_session.py --mode both`, and pre-commit hooks).

## Step 6 — Documentation & LLM Wiki Synchronization (`doc-sync`)
After all tests pass and before concluding, requesting review, or opening a PR:
1. You MUST activate the [`doc-sync`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/.claude/skills/doc-sync/SKILL.md) procedure.
2. Audit whether the changes affect the LLM Wiki ([`docs/wiki/index.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/index.md)), architectural invariants, D&D rules, API contracts, or schemas.
3. Update the relevant documentation pages (or provide an explicit justification in `walkthrough.md` if no documentation updates were required).
4. Update the `walkthrough.md` artifact summarizing both the code implementation and the documentation audit outcomes.
