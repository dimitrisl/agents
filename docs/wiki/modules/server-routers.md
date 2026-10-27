# 🚦 Subsystem: Server Routers (`server/routers/`)

## 📌 Overview
The `server/routers/` package defines all REST endpoints mounted under `/api/v1` and the WebSocket endpoint under `/ws`.

---

## 🔑 Key Routers

| Router | Prefix | Responsibility |
| :--- | :--- | :--- |
| [`auth_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/auth_router.py) | `/auth` | User registration (`/register`), OAuth2 login (`/login`), demo accounts (`/demo`), and current user profile (`/me`). Catches duplicate username conflicts (`HTTP 400`). |
| [`character_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/character_router.py) | `/characters` | CRUD operations for character sheets, optimistic locking via `version`, portrait uploads (`/upload-portrait` saving to `data/portraits`), custom portrait URLs, PDF import (`/import-pdf`), and PDF export (`/{char_id}/export-pdf`). |
| [`campaign_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/campaign_router.py) | `/campaigns` | Campaign management, party roster, invite codes, whispers, roll requests, notes, encounters, entities, and campaign cascading deletion. |
| [`forge_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/forge_router.py) | `/forge` | AI character generation, portrait generation, manual creation suggestions, and level-up enrichment. |
| Static Mounts | `/api/v1/portraits` | Static files mount (`StaticFiles(directory="data/portraits")`) in `server/main.py` serving uploaded avatar images with unique UUIDs. |
| [`homebrew_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/homebrew_router.py) | `/campaigns/{name}/homebrew` | Custom magic items, weapons, feats, and spells creation and campaign-scoped queries. |
| [`rules_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/rules_router.py) | `/rules` | Static rules lookups, spell filtering, class scaling resolution (`/classes/{name}/scaling`), rules comparison, and AI Oracle. |
| [`session_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/session_router.py) | `/campaigns/{name}/sessions` | Audio session transcription, text session recaps, and prep ideas. |
| [`assets_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/assets_router.py) | `/campaigns/{name}/assets` | Battle map and image asset uploads with chunked streaming, 10MB limits, and path traversal protection. |
| [`websocket_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/websocket_router.py) | `/ws` | Real-time WebSocket connection manager, token/role verification, audience targeting, and VTT event broadcasting. |
