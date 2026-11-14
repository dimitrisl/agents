# 🩸 Phyrexian Forge

Welcome to **Phyrexian Forge**, an AI-powered Dungeons & Dragons (5e & 5.5e) suite featuring automated character forging, strategic optimization, live campaign management, and virtual tabletop mechanics.

---

## 📚 Documentation & LLM Wiki

Comprehensive technical and architectural documentation is organized in the central **[LLM Wiki](docs/wiki/index.md)**:

* **[Master Catalog & Routing Table](docs/wiki/index.md)**
* **[Global Architecture](docs/wiki/architecture.md)**
* **Concepts:**
  * [Deterministic Rules Engine vs. AI](docs/wiki/concepts/rules-engine.md)
  * [Real-Time WebSockets](docs/wiki/concepts/realtime-websockets.md)
  * [Authentication & Security](docs/wiki/concepts/auth-and-security.md)
  * [Database Strategy & Race Condition Defenses](docs/wiki/concepts/database-and-indexes.md)
* **Subsystem Modules:**
  * [Server Core (`server/`)](docs/wiki/modules/server.md)
  * [Server Routers (`server/routers/`)](docs/wiki/modules/server-routers.md)
  * [Server Dependencies (`server/dependencies/`)](docs/wiki/modules/server-dependencies.md)
  * [Backend Core (`backend/core/`)](docs/wiki/modules/backend-core.md)
  * [Backend Services (`backend/services/`)](docs/wiki/modules/backend-services.md)
  * [Backend Repositories (`backend/repositories/`)](docs/wiki/modules/backend-repositories.md)
  * [Backend Utilities (`backend/utils/`)](docs/wiki/modules/backend-utils.md)
  * [Static Rules Data (`data/rules/`)](docs/wiki/modules/data-rules.md)
  * [Maintenance Scripts (`scripts/`)](docs/wiki/modules/scripts.md)
  * [Frontend Architecture, DM Workspace & Forge (`client/src/app/`)](docs/wiki/modules/client-architecture.md)
  * [Player Companion & Character Sheet (`client/src/app/features/player/`)](docs/wiki/modules/client-player.md)
  * [Testing Architecture (`tests/`)](docs/wiki/modules/testing.md)

---

## 🚀 Quick Start & Installation

### Prerequisites
- **Python 3.11 - 3.13** ([python.org](https://www.python.org/))
- **Poetry** ([python-poetry.org](https://python-poetry.org/))
- **Node.js 18+ & npm** ([nodejs.org](https://nodejs.org/))
- **MongoDB** running locally on port `27017` (or configured via `MONGO_URI` in `.env`)

---

### ⚡ One-Click Automated Setup

#### 🐧 Linux & 🍎 macOS
```bash
# 1. Run the automated setup script (installs Python & npm dependencies, generates .env)
./setup.sh

# 2. Start both Backend (FastAPI :8000) and Frontend (Angular :4200)
./start.sh
```

#### 🪟 Windows (PowerShell or Command Prompt)
```powershell
# In PowerShell:
.\setup.ps1
.\start.ps1

# Or simply double-click setup.bat and start.bat
```

---

### 🧪 Manual Commands & Testing
```bash
# Run backend test suite (486 tests)
poetry run pytest tests/ -v

# Run frontend test suite (423 tests across 39 suites)
cd client && npm test -- --watch=false

# Run pre-commit hooks and code formatters
poetry run pre-commit run --all-files
```
