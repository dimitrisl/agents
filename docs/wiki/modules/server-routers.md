# 🚦 Subsystem: Server Routers (`server/routers/`)

## 📌 Overview
The `server/routers/` package defines all REST endpoints mounted under `/api/v1` and the WebSocket endpoint under `/ws`.

---

## 🔑 Key Routers

| Router | Prefix | Responsibility |
| :--- | :--- | :--- |
| [`auth_router.py`](../../../server/routers/auth_router.py) | `/auth` | User registration (`/register`), OAuth2 login (`/login`) with transparent legacy SHA-256 to PBKDF2 hash migration, demo accounts (`/demo`), and current user profile (`/me`). Catches duplicate username conflicts (`HTTP 400`). |
| [`character_router.py`](../../../server/routers/character_router.py) | `/characters` | CRUD operations for character sheets, omitted-HP derivation via `stats_service`, `campaign_members` membership guards on `active_campaign` (`POST ""` and `PUT /{char_id}`), optimistic locking via `version`, portrait uploads (`/upload-portrait` saving to `data/portraits` with transactional aborted upload cleanup), custom portrait URLs, PDF import (`/import-pdf`), and PDF export (`/{char_id}/export-pdf` with SSRF redirect hardening). |
| [`campaign_router.py`](../../../server/routers/campaign_router.py) | `/campaigns` | Campaign management, name validation (`'%'`, `'/'`, `'\\'` rejected), party roster, member count aggregation from `campaign_members`, invite codes & DM rotation (`POST /{name}/invite-code/rotate`, exact + case-insensitive join lookup preserving mixed-case tokens), edition-aware party long rest (`POST /{name}/party/long-rest`, restoring 2024 full or 2014 half Hit Dice, Pact slots, class resources, optimistic `version` CAS, and re-syncing exhaustion stats), whispers with database-level query isolation, roll requests (secret DM rolls with case-insensitive skills/saves, 2024 exhaustion penalty, and half-proficiencies), player sheet roll logging (`POST /{name}/rolls` + redaction in `GET /{name}/messages`), notes, encounters (`POST /{name}/encounter` returning `EncounterSyncResponseSchema` with `danger_indicator`; player redaction strips monster secrets while keeping `health_status`), entities, scenes (URL-encoded asset cleanup & path-confined orphan deletion), and campaign cascading deletion. |
| [`forge_router.py`](../../../server/routers/forge_router.py) | `/forge` | AI character generation, portrait generation, manual creation suggestions, level-up enrichment, and Level 19+ Epic Boon stat cap enforcement (`POST /level-up-apply`, cap 30 in 2024 Revision). |
| Static Mounts | `/api/v1/portraits` | Static files mount (`StaticFiles(directory="data/portraits")`) in `server/main.py` serving uploaded avatar images with unique UUIDs. |
| [`homebrew_router.py`](../../../server/routers/homebrew_router.py) | `/campaigns/{name}/homebrew` | Custom magic items, weapons, feats, and spells creation and campaign-scoped queries. |
| [`rules_router.py`](../../../server/routers/rules_router.py) | `/rules` | Static rules lookups, spell filtering, class scaling resolution (`/classes/{name}/scaling`), rules comparison, and AI Oracle. |
| [`session_router.py`](../../../server/routers/session_router.py) | `/campaigns/{name}/sessions` | Audio session transcription, text session recaps, prep ideas, and chronological journey graphs (`/journey` filtered to `is_revealed: True` for non-DM callers). |
| [`assets_router.py`](../../../server/routers/assets_router.py) | `/campaigns/{name}/assets` | Battle map and image asset uploads with URL-encoded campaign paths (`quote`), chunked streaming, 10MB limits, transactional cleanup on aborted uploads, and path traversal protection. |
| [`settings_router.py`](../../../server/routers/settings_router.py) | `/settings` | Per-user AI model selection (Gemini free tier vs. Claude models) and BYOK Anthropic API key management (encrypted at rest via `server/secret_box.py`). |
| [`admin_router.py`](../../../server/routers/admin_router.py) | `/admin` | Admin-only user management (paginated list, ReDoS-safe user search via `re.escape`, concurrent campaign counts via `asyncio.gather`, online status, role promotion/demotion, user deletion) and system metrics. |
| [`dm_router.py`](../../../server/routers/dm_router.py) | `/dm` | AI DM toolkit endpoints for encounter generation, monster tactical briefs, and loot generation. |
| [`bestiary_router.py`](../../../server/routers/bestiary_router.py) | `/bestiary` | Unified Bestiary endpoints combining scaled official 2014/2024 monsters in MongoDB (`official_monsters` collection with automatic fallback to static SRD rules) with custom DM monsters in MongoDB (`custom_monsters` collection). Supports source filtering (`include_official`, `include_mine`, `include_community`), cloning (`based_on`), visibility toggling (`PATCH /{id}/visibility`), and ownership-verified updates/deletions. |
| [`websocket_router.py`](../../../server/routers/websocket_router.py) | `/ws` | Real-time WebSocket connection manager, token/role verification, audience targeting, and VTT event broadcasting. |
