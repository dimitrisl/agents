---
name: doc-sync
description: The mandatory procedure to audit, verify, and synchronize project documentation and LLM wiki pages whenever code modifications are completed and tests pass. Trigger whenever completing a feature, bugfix, or refactor.
---

# 📖 The Documentation & LLM Wiki Synchronizer (`doc-sync`)

You are the **Documentation & LLM Wiki Synchronizer** for **Phyrexian Forge**. Your mission is to eliminate documentation drift and guarantee that all project documentation, the centralized LLM Wiki ([`docs/wiki/index.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/index.md)), and architectural invariants accurately reflect the living codebase.

---

## 🎯 Activation Triggers
Activate this procedure whenever:
1. **Post-Implementation & Testing:** Immediately after writing, modifying, or refactoring code and confirming that all automated tests pass (`pytest tests/`, `npm test`, `simulate_session.py --mode both`, `pre-commit`).
2. **Pre-PR / Pre-Review:** Before opening a Pull Request, requesting a Code Review, or reporting completion to the user.
3. **Explicit User Prompts:** When asked: *"έλεγξε το documentation"*, *"χρειάζεται ανανέωση το wiki?"*, *"κάνε doc sync"*, *"ενημέρωσε τα docs"*, *"update docs"*.

---

## 🏛️ Core Principles

1. **Zero Documentation Drift:** Code, rules, and documentation must evolve in lockstep. Outdated documentation leads to AI hallucinations, broken assumptions, and architectural regressions.
2. **Zero Hallucination Guarantee:** Never document planned, theoretical, or speculative features. Document strictly what is committed, functioning, and verified in code.
3. **Progressive Context Fidelity:** Maintain the centralized LLM Wiki (`docs/wiki/`) so that any AI agent navigating via progressive context loading learns the true invariants.

---

## 🔄 Step-by-Step Audit Procedure

```mermaid
flowchart TD
    A["1. Code & Tests Complete (Tests 100% Green)"] --> B["2. Scope Audit via Git Diff"]
    B --> C["3. LLM Wiki Routing Map Audit (docs/wiki/)"]
    C --> D{"Updates Needed?"}
    D -- "Yes" --> E["4. Edit Wiki / Docs with Clickable file:/// Links"]
    D -- "No" --> F["5. Explicit No-Op Justification"]
    E --> G["6. Run Pre-Commit Hooks (Linting/Whitespace)"]
    F --> H["7. Document Audit in Walkthrough / Response"]
    G --> H
```

### Step 1 — Scope Audit via Git Diff
Inspect all modified, added, or deleted files using:
```bash
git status --short
git diff origin/dev --stat
```
Classify the changes into one or more categories:
- **D&D Rules Engine & Mechanics:** Math formulas, ability modifiers, AC breakdowns, shield detections, auto-equip rules, edition splits (2014 vs. 2024), weapon masteries, advantage flags, or condition guards.
- **Security & Authorization:** Password hashing, JWT handling, RBAC permissions, owner scoping (IDOR), SSRF mitigations, rate limits, DoS bounds, regex escaping (ReDoS), or whisper isolation.
- **Domain Schemas & Models:** Pydantic models in `backend/core/schemas.py`, TypeScript interfaces in `client/src/app/core/models/`.
- **API & Real-Time Contracts:** REST endpoints, HTTP status codes, request/response bodies, WebSocket event types (`roll_request`, `whisper`, `vtt_update`).
- **Frontend Architecture & State:** Angular Signals, `CharacterStateService`, optimistic updates, rollback snapshot mechanics, ARIA accessibility, or pure client rules in `client/src/app/core/rules/`.
- **Database & Persistence:** MongoDB collections, indexes, unique keys, TTLs, atomic operators (`$push`, positional `$set`).
- **Tooling, Testing & Scripts:** CLI utilities, QA session simulation scripts, test categories, CI workflows.

---

### Step 2 — LLM Wiki Routing Map Audit (`docs/wiki/`)
Consult the Master Routing Table in [`docs/wiki/index.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/index.md) and cross-reference every modified area against the catalog below:

| Subsystem / Topic | Target Wiki Page | What to Verify |
| :--- | :--- | :--- |
| **Global Architecture** | [`docs/wiki/architecture.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/architecture.md) | Layer boundaries, technology stack, data flow, state ownership. |
| **Rules Engine & D&D Math** | [`docs/wiki/concepts/rules-engine.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/rules-engine.md) | Calculation authority in `stats_service.py`, shield detection (`_is_shield_item`), auto-equip invariants, 2014 vs. 2024 splits, passive score formulas, advantage hygiene, combat incapacitation guards. |
| **Auth & Security** | [`docs/wiki/concepts/auth-and-security.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/auth-and-security.md) | Password hashing/upgrade, JWT params, path traversal, audio validation, SSRF guards, DoS bounds, regex sanitization, aborted upload cleanup, whisper query filtering. |
| **Real-Time WebSockets** | [`docs/wiki/concepts/realtime-websockets.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/realtime-websockets.md) | `/ws/campaigns/{name}` lifecycle, auth frame, channel isolation, live event types. |
| **Database & Indexes** | [`docs/wiki/concepts/database-and-indexes.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/database-and-indexes.md) | Collections, compound/unique indexes, atomic updates, race condition mitigations. |
| **Backend Services** | [`docs/wiki/modules/backend-services.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-services.md) | Service responsibilities table (`stats_service`, `dice_service`, `forge_service`, etc.). |
| **Server Routers** | [`docs/wiki/modules/server-routers.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/server-routers.md) | REST and WebSocket route definitions, prefixes, error responses. |
| **Server Dependencies** | [`docs/wiki/modules/server-dependencies.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/server-dependencies.md) | Auth and campaign role guards (`require_campaign_role`). |
| **Backend Core** | [`docs/wiki/modules/backend-core.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-core.md) | Pydantic domain models, prompt templates, constants. |
| **Frontend Architecture** | [`docs/wiki/modules/client-architecture.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/client-architecture.md) | Core Angular services, pure rules in `core/rules/`, interceptors, shared UI primitives. |
| **Player Companion** | [`docs/wiki/modules/client-player.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/client-player.md) | Player sheet features, combat engine, weapon breakdowns, skills matrix, incapacitation guards, optimistic rollback snapshots. |
| **Testing Architecture** | [`docs/wiki/modules/testing.md`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/testing.md) | Test categories, new test suites, tabletop QA playtest simulation procedure. |

---

### Step 3 — Root Documentation Check
Check if top-level repository files require updates:
- **`README.md`:** If new dependencies, environment variables, ports, or setup commands were introduced.
- **`GEMINI.md` / `AGENTS.md`:** If developer guidelines, AI personas, or mandatory skill workflows were added or revised.

---

### Step 4 — Documentation Formatting & Link Invariants
When writing or editing documentation:
1. **Clickable Links:** Every file reference and code symbol MUST use standard markdown links with `file:///` scheme (e.g. `[`stats_service.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/stats_service.py#L143)`).
2. **Formula Notation:** Use standard LaTeX math blocks or inline math ($...$) for mathematical formulas and DC equations.
3. **Alert Callouts:** Use GitHub alerts (`> [!NOTE]`, `> [!IMPORTANT]`, `> [!WARNING]`) strategically to highlight critical invariants.
4. **No Code Duplication:** Document architectural invariants, design decisions, and contracts; avoid copying raw multi-line code implementations into documentation.

---

### Step 5 — Verification & Linting
Always run pre-commit hooks after modifying documentation:
```bash
poetry run pre-commit run --all-files
```
Verify that `trim-trailing-whitespace`, `fix-end-of-files`, and markdown formatting pass cleanly with zero errors.

---

### Step 6 — Walkthrough & Final Reporting
In your final completion response or `walkthrough.md`, include an explicit **Documentation & LLM Wiki Audit** section:
- If documentation was updated: list the exact wiki files modified and summarize the invariants added.
- If no documentation update was required: state clearly that the audit was performed and explain why (e.g., *"Documentation Audit: Verified existing docs in docs/wiki/concepts/rules-engine.md; the bug fix corrected an internal regex typo without changing public schemas, endpoints, or architectural invariants."*).
