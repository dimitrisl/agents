# 🧠 Phyrexian Forge — LLM Wiki & Knowledge Vault

Welcome to the centralized **LLM Wiki** for **Phyrexian Forge**. This knowledge base provides an architectural, operational, and procedural reference for AI assistants, agents, and developers navigating the codebase.

---

## 🗺️ Master Catalog & Routing Table

When investigating, planning, or executing tasks across the repository, consult the relevant wiki pages below:

### 🏛️ Core Architecture & Cross-Cutting Concepts
* **[Global Architecture](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/architecture.md):** 30,000-foot view of layers, tech stack, data flow, and state boundaries.
* **[Deterministic Rules Engine vs. AI](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/rules-engine.md):** The bio-mechanical boundary between static JSON rules and generative AI.
* **[Real-Time WebSockets](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/realtime-websockets.md):** Connection manager, auth frames, channel isolation, and broadcast mechanics.
* **[Authentication & Security](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/auth-and-security.md):** JWT authentication, RBAC authorization, and path safety sanitizers.
* **[Database Strategy & Race Condition Defenses](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/database-and-indexes.md):** MongoDB schema, collections, unique/query index catalog, and atomic operators.

---

### 📦 Subsystem Modules
* **[Server Core (`server/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/server.md):** FastAPI app factory, lifespan, config, and async Motor connection.
* **[Server Routers (`server/routers/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/server-routers.md):** REST and WebSocket endpoints, error handling, and payload schemas.
* **[Server Dependencies (`server/dependencies/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/server-dependencies.md):** Auth extraction and campaign RBAC access guards.
* **[Backend Core (`backend/core/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-core.md):** Domain schemas (`schemas.py`), prompts, constants, and GenAI provider factory.
* **[Backend Services (`backend/services/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-services.md):** Domain logic: calculation authority (`stats_service`), validation, character forge, and VTT service.
* **[Backend Repositories (`backend/repositories/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-repositories.md):** Cached in-memory repository for static 2014 & 2024 D&D rulesets.
* **[Backend Utilities (`backend/utils/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-utils.md):** Path safety, dice roller, math calculations, and PDF export/import engines.
* **[Static Rules Data (`data/rules/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/data-rules.md):** 2014 & 2024 JSON rule data catalog (classes, spells, feats, backgrounds, species).
* **[Maintenance Scripts (`scripts/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/scripts.md):** Database migrations, spell fetchers, and diagnostic utilities.
* **[Testing Architecture (`tests/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/testing.md):** Test suite layout, fixtures, integration flows, and race condition tests.
