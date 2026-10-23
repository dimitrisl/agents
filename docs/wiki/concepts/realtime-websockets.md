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

3. **Audience-Targeted Whispers:**
   - Whispers directed to a specific player are routed only to the recipient and sender connections (`audience = [recipient, sender]`). Other players connected to the channel receive zero network packets containing the whisper content.

4. **VTT Redaction for Players (`VTTService.redact_for_player`):**
   - Tokens marked with `is_hidden = True` are filtered out before sending state frames to player connections. They exist neither in the UI nor in browser network payloads.

5. **Secret Rolls:**
   - When the DM requests a secret roll (e.g. Stealth or Insight), the prompt is sent to the player, but the numerical result and dice breakdown are broadcast solely to the DM connection (`dm_only=True`).
