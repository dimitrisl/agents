---
name: code-review
description: The procedure for performing a strict, full-stack code review of a specific branch against origin/dev.
---

# Code Review Agent Procedure

When asked to review a branch (e.g. "review this branch", "κάνε code review"), follow this strict procedure. You act as a Senior Full Stack Developer (Angular + FastAPI) looking for security flaws, memory leaks, race conditions, and UX/UI inconsistencies.

## Step 1 — Fetch and Diff

Do not guess what has changed. Always compare against `origin/dev`.
1. Run `git fetch origin` to ensure you have the latest state.
2. If the diff is expected to be small, run `git diff origin/dev...<branch-name> > branch_diff.patch` and review it.
3. If the diff is large, run `git diff origin/dev...<branch-name> --name-status` to identify changed files, then use `view_file` to review the specific files.

## Step 2 — Strict Analysis

Examine **EVERYTHING** in the diff with extreme prejudice. Do not restrict yourself to just the backend or frontend code. You must review infrastructure, automation, configuration, and documentation as well.

### Infrastructure & Automation (CI/CD, Scripts, Configs)
- **GitHub Actions & CI:** Are workflows secure? Do they follow best practices? Are they brittle?
- **Configuration & Dependencies:** Are `.gitignore`, `pyproject.toml`, or `package.json` changes safe? No leaked secrets or bloated dependencies?

### Backend (FastAPI / Python)
- **Security:** Are REST endpoints properly checking `owner_id` or `current_user`? Are WebSockets doing targeted delivery?
- **Concurrency:** Are MongoDB queries vulnerable to race conditions (e.g., using `$set` on arrays instead of `$push`)?
- **Resource Management:** Are there memory leaks? (e.g., catching exceptions but failing to call cleanup functions like `manager.disconnect()` in a `finally` block).
- **Validation:** Are Pydantic schemas used correctly? Is data validated dynamically rather than hardcoded?

### Frontend (Angular 19 / TypeScript)
- **State Management:** Are Angular Signals used correctly for state? Is the UI reacting properly without unnecessary refetches?
- **WebSockets & Networking:** Is the fallback to REST implemented for catch-up? Is the reconnection logic solid? Are errors handled gracefully without silent failures?
- **UX Consistency:** Do all actions update the UI locally to feel "snappy" (optimistic updates)? Does the UI accurately reflect the loading/pending states?
- **Styling:** Does it strictly follow `client/design-contract.md`? No literal colors, use the `forge-*` kit, ensure responsiveness, etc.

## Step 3 — The Report

Generate an Artifact (markdown file) or a structured markdown response with your findings.

The report MUST contain a **Markdown Table** summarizing all findings before any detailed explanations. The table MUST have the following columns:
- **Class**: The severity class (Major, Adequate, Minor).
- **Problem**: A concise description of the issue.
- **Affected Files**: The files impacted by this issue.
- **Impact / Reason**: Why this problem matters (e.g. Memory Leak, UX lag).
- **Actionable Solution**: Exact instructions or code snippets on how to fix it.

After the table, you may provide detailed explanations if necessary, and you MUST conclude with:
1. **Praise:** Briefly acknowledge what was done right.
2. **Final Verdict:** You MUST conclude the report with a clear decision:
   - **APPROVE**: If there are no Major issues.
   - **DECLINE**: If there is even one Major issue that prevents merging.

**DO NOT** modify the code yourself during a code review unless explicitly requested by the user *after* the review. Just provide the report.
