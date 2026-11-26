# 📡 Concept: Real-Time WebSockets (`docs/wiki/concepts/realtime-websockets.md`)

## 📌 Overview
Phyrexian Forge uses **FastAPI WebSockets** to maintain low-latency, bidirectional synchronization between Dungeon Masters and players during live game sessions.

Polling HTTP endpoints for live campaign state is strictly prohibited. All live combat actions, whisper messages, initiative updates, and VTT token coordinates stream across the WebSocket connection.

---

## 🏗️ Architecture & Connection Lifecycle

```
[ Player / DM Client ]
        │
        │ 1. Connect to ws://host/ws/campaigns/{campaign_id}
        ▼
[ WebSocket Endpoint ] (server/routers/websocket_router.py)
        │
        │ 2. Wait for first frame: {"type": "auth", "token": "...", "character": "..."}
        ▼
[ Token & Role Verification ]
  - Verify JWT from payload
  - Fetch member document from MongoDB (db.campaign_members)
  - Determine verified role ("dm" or "player")
  - Verify character ownership if specified
        │
        │ 3. Register with ConnectionManager
        ▼
[ ConnectionManager.connect() ]
        │
        │ 4. Bidirectional Event Loop
        ▼
  - Handle VTT moves, token changes, sync requests
  - Broadcast roll requests, results, whispers, party updates
```

---

## 🔒 Security & Privacy Guarantees

1. **Server-Side Role Authority:**
   - The connection role is determined exclusively by querying `db.campaign_members` using the user's verified JWT identity. Query parameters or client claims requesting "dm" status are ignored.

2. **Character Spoofing Defense:**
   - If an auth frame specifies a character name, the backend queries MongoDB to verify that `owner_id == user.id` and `active_campaign == campaign_id`. Spoofed character names are stripped, dropping the connection to an anonymous player.

3. **Audience-Targeted Whispers & Roll Requests (`user_ids` + `char_id`):**
   - Whispers and roll requests route by verified `user_ids` alongside `characters` (`recipient_character_id` / `target_char_id`) when targeting specific characters. This prevents homonym character collisions across different players while still reaching a multi-character player regardless of which sheet is currently active on their WebSocket connection. Other players connected to the channel receive zero network packets containing the private whisper content.

4. **VTT Redaction for Players (`VTTService.redact_for_player`):**
   - Tokens marked with `is_hidden = True` are filtered out before sending state frames to player connections. They exist neither in the UI nor in browser network payloads.

5. **Secret Rolls:**
   - When the DM requests a secret roll (e.g. Stealth or Insight), the prompt is sent to the player (`user_ids` + `target_char_id`), but the numerical result and dice breakdown are broadcast solely to the DM connection (`dm_only=True`).

6. **Campaign Roll Logs (`campaign_roll`):**
   - Player character-sheet rolls submitted via [`POST /api/v1/campaigns/{name}/rolls`](../../../server/routers/campaign_router.py) resolve character ownership by `char_id` (with `sender_username` attached), persist to `campaign_roll_logs` first, and broadcast live as `type: "campaign_roll"` frames (`dm_only=False` for `public`, `dm_only=True` for `dm` whisper mode). Historical `GET /messages` replays redact `visibility == "dm"` entries for non-DM party members unless `sender_user_id == current_user_id`.

7. **Member Removal & Homonym Socket Isolation (`disconnect_campaign_member`):**
   - Removing a character via `DELETE /api/v1/campaigns/{name}/party/{char_id}` passes `owner_id` alongside `user_id` (`kicked_user_id` only when no owned characters remain) and `character_name` to [`ConnectionManager.disconnect_campaign_member`](../../../server/routers/websocket_router.py). Name-based socket closure requires `c.user_id == owner_id` when `owner_id` is present and skips teardown for unowned paper heroes, ensuring another player sharing the same `char_name` never receives a spurious `1008` closure.

8. **Live Party Join & Encounter Echo Hygiene (`party_member_joined` & `encounter_update`):**
   - Joining a campaign via [`POST /api/v1/campaigns/join`](../../../server/routers/campaign_router.py) or adding a character via [`POST /api/v1/campaigns/{name}/party/members`](../../../server/routers/campaign_router.py) broadcasts `type: "party_member_joined"` so the DM's live Party Roster refreshes without a manual reload.
   - [`POST /api/v1/forge/level-up-apply`](../../../server/routers/forge_router.py) atomically updates only matching combatant rows (`char_id` strictly when present, falling back to non-empty `char_name` only when unlinked) and recomputes `danger_indicator` inside `campaign_encounters` before broadcasting `party_update`, while [`dm.component.ts`](../../../client/src/app/features/dm/dm.component.ts) cancels stale debounced writes across campaign switches/`endCombat()` and ignores same-generation `encounter_update` echoes while a local write is pending or in flight.

9. **Session Revocation & Forced Password Rotation Guards:**
   - WebSocket handshakes enforce JWT `purpose == "access"`, `token_version` (`tv >= user.token_version`), and close with `1008` when `must_change_password` is `True`.
   - Password changes ([`auth_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/auth_router.py)) and admin resets ([`admin_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/admin_router.py)) invoke `manager.disconnect_user(...)` to close all active campaign WebSockets (`1008`) for that user immediately.

10. **DM Story Scenes & Ephemeral Player Pop-ups (`scene_popup` / `scene_popup_dismiss`, `#288`):**
    - [`story_scenes_router.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/routers/story_scenes_router.py) enforces `require_campaign_role("dm")` on all scene reads/writes (`campaign_story_scenes`), guaranteeing unrevealed handouts never leak to players before broadcast.
    - Casting a handout card (`POST /cast`) strips private `dm_notes` via [`build_scene_popup_payload`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/backend/services/story_scene_service.py) and broadcasts `type: "scene_popup"` either campaign-wide (`target_mode="all"`) or strictly to resolved `user_ids` + `characters` (`target_mode="selected"`).
    - Casting `type: "scene_popup_dismiss"` (`POST /dismiss`) remotely clears active player lightboxes; reveals are strictly ephemeral client-side (no player handout archive or post-refresh persistence).
