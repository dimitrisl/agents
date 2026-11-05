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

## Step 3 — Architecture & Security Analysis
Analyze the proposed change against the project's core principles:
- **Security / AuthZ:** Does this change require checking `owner_id` or a campaign role?
- **Data Integrity:** Will this change introduce race conditions in MongoDB? (Use `$push` or `$set` with positional operators instead of blind `$set` for arrays).
- **Performance:** Will this block the event loop? (Ensure async functions or `run_in_threadpool` are used for blocking operations).

## Step 4 — Implementation Planning
You MUST enter Planning Mode and create an `implementation_plan.md` artifact.
Your plan must include:
1. **Goal Description:** A brief summary of the problem and the proposed solution.
2. **Proposed Changes:** A file-by-file breakdown of what will be modified, added, or deleted.
3. **User Review Required:** Highlight any breaking changes, database migrations, or frontend-impacting changes using GitHub alerts (`> [!WARNING]`).
4. **Verification Plan:** How you will verify the fix (tests, manual checks).

**CRITICAL:** You must STOP and wait for the user to explicitly APPROVE the implementation plan before writing any code.

## Step 5 — Execution & Validation
Once the user approves the plan:
1. Create a `task.md` artifact to track your progress as a checklist.
2. Implement the changes strictly following the approved plan.
3. If you discover a major blocker during execution, STOP, update the plan, and ask for review again.
4. Verify your changes and update the `walkthrough.md` artifact to summarize the completed work.
