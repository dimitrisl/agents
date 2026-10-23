# 🩸 Phyrexian Forge

Welcome to **Phyrexian Forge**, an AI-powered Dungeons & Dragons (5e & 5.5e) suite featuring automated character forging, strategic optimization, live campaign management, and virtual tabletop mechanics.

---

## 📚 Documentation & LLM Wiki

Comprehensive technical and architectural documentation is organized in the central **[LLM Wiki](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/index.md)**:

* **[Master Catalog & Routing Table](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/index.md)**
* **[Global Architecture](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/architecture.md)**
* **Concepts:**
  * [Deterministic Rules Engine vs. AI](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/rules-engine.md)
  * [Real-Time WebSockets](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/realtime-websockets.md)
  * [Authentication & Security](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/auth-and-security.md)
  * [Database Strategy & Race Condition Defenses](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/concepts/database-and-indexes.md)
* **Subsystem Modules:**
  * [Server Core (`server/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/server.md)
  * [Server Routers (`server/routers/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/server-routers.md)
  * [Server Dependencies (`server/dependencies/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/server-dependencies.md)
  * [Backend Core (`backend/core/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-core.md)
  * [Backend Services (`backend/services/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-services.md)
  * [Backend Repositories (`backend/repositories/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-repositories.md)
  * [Backend Utilities (`backend/utils/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/backend-utils.md)
  * [Static Rules Data (`data/rules/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/data-rules.md)
  * [Maintenance Scripts (`scripts/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/scripts.md)
  * [Testing Architecture (`tests/`)](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/docs/wiki/modules/testing.md)

---

## 🚀 Quick Start

### Prerequisites
- Python 3.13+ with Poetry
- Node.js 18+ and npm (for Angular frontend)

### Installation & Commands
```bash
# Install backend dependencies
poetry install

# Run backend test suite
poetry run pytest tests/ -v

# Run code formatting and lint checks
poetry run pre-commit run --all-files
```
