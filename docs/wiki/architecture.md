# 🏛️ Global Architecture (`docs/wiki/architecture.md`)

## 📌 Executive Summary
**Phyrexian Forge** is a specialized D&D (5e & 5.5e) suite providing AI-assisted character forging, strategic build validation, live Virtual Tabletop (VTT), combat initiative tracking, and real-time DM-player interaction.

The system is designed with a strict **layered architecture** and a clear separation of concerns between deterministic game mechanics and non-deterministic AI generation.

---

## 🛠️ Technology Stack

| Layer | Technology | Key Responsibility |
| :--- | :--- | :--- |
| **Frontend** | Angular 19 (Signals, RxJS, Custom CSS) | Reactive UI, client-side character state, dice rendering, VTT grid, and WebSocket client. Maintained exclusively by @michalis89. |
| **Backend Transport** | FastAPI, Python 3.13+ | RESTful endpoints (`/api/v1`), WebSocket channels (`/ws`), dependency injection, authentication. |
| **Persistence** | MongoDB Atlas (via Motor async driver) | Persistent storage for users, characters, campaigns, members, entities, and logs. |
| **Rules Engine** | Static JSON (`data/rules/`) + `RulesRepository` | Immutable source of truth for D&D 2014 & 2024 classes, spells, feats, and items. |
| **Calculation Engine** | `backend/services/stats_service.py` | Single source of truth for derived statistics (AC, HP, Save DCs, Proficiencies). |
| **AI Engine** | Google GenAI SDK (Gemini 1.5 Flash / Pro) | Thematic generation, backstory enrichment, DM session recap extraction, and voice session processing. |

---

## 🧱 Layered Responsibility & Flow

```
[ Angular 19 Client ]
        │  ▲
        │  │ HTTP (REST) & WebSockets
        ▼  │
[ FastAPI Transport Layer ] (server/main.py, routers/, dependencies/)
        │  ▲
        │  │ Validated Schemas (backend/core/schemas.py)
        ▼  │
[ Business Services ] (backend/services/ - stats, validation, forge, vtt)
     │            │             │
     ▼            ▼             ▼
[ AI Engine ]  [ MongoDB ]  [ Rules Repository ]
 (Gemini SDK)   (Motor Async)   (data/rules/*.json)
```

1. **Client Layer:** Renders the dark "Phyrexian" aesthetic UI. Manages transient state using Angular 19 Signals in `CharacterStateService` and `CampaignStateService`.
2. **API Layer (`server/`):** Validates incoming requests via Pydantic schemas, verifies JWT credentials, enforces campaign RBAC roles (`require_campaign_role("dm")`), and delegates all domain work to services.
3. **Domain Service Layer (`backend/services/`):** Contains pure business logic decoupled from HTTP frameworks.
4. **Data Access Layer:**
   - **Dynamic Data:** Persisted asynchronously in MongoDB.
   - **Static Rules:** Loaded synchronously on startup into in-memory dictionaries with LRU caching.

---

## 🔒 Jurisdiction & Collaboration Rules
- **Backend Domain:** Exclusively Python 3.13+, FastAPI, Motor, Pydantic, and backend services.
- **Frontend Domain:** Maintained by @michalis89. The backend agent must never modify Angular/TypeScript files.
- **Git Branching Strategy:** All feature development merges into `dev`. Production releases target `main`. Normal development never commits directly to `main`.
