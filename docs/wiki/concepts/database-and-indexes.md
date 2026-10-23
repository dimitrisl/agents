# 🗄️ Concept: Database Strategy & Race Condition Defenses (`docs/wiki/concepts/database-and-indexes.md`)

## 📌 Overview
Phyrexian Forge uses **MongoDB Atlas** accessed asynchronously via **Motor** (`AsyncIOMotorClient`). All dynamic entities (users, characters, campaigns, members, entities, session logs, whispers, roll requests) reside in a single database named `phyrexian_forge` (configurable via `settings.DATABASE_NAME`).

---

## 🗂️ Core Collections Schema

| Collection | Key Fields | Purpose |
| :--- | :--- | :--- |
| `users` | `id`, `username`, `password_hash`, `email`, `created_at` | User accounts and authentication credentials. |
| `characters` | `char_id`, `owner_id`, `char_name`, `char_class`, `char_level`, `stats`, `version`, `active_campaign` | Full character sheet documents. |
| `campaigns` | `campaign_name`, `owner_id`, `edition`, `invite_code`, `party`, `vtt_state` | Campaign metadata, party roster, and VTT grid state. |
| `campaign_members` | `campaign_id`, `user_id`, `role` (`dm`\|`player`), `character_id`, `joined_at` | Campaign membership and permissions table. |
| `campaign_entities` | `campaign_name`, `name`, `type`, `content`, `tags`, `created_at` | NPCs, locations, factions, and lore cards. |
| `session_logs` | `campaign_name`, `session_number`, `title`, `summary`, `real_world_date` | Chronological session recaps and journal. |
| `campaign_whispers` | `campaign_name`, `sender`, `recipient`, `message`, `timestamp` | In-game text messages and whispers. |
| `campaign_roll_requests` | `campaign_name`, `char_filename`, `roll_type`, `stat`, `status`, `result` | Dice roll requests issued by DM. |
| `homebrew_content` | `campaign_name`, `creator_dm_id`, `type`, `item_data` | Custom weapons, spells, and items scoped to a campaign. |

---

## 🛡️ Index Catalog (`server/db_async.py`)

All collections are indexed defensively during startup via `init_indexes(database)`:

```python
INDEX_DEFINITIONS = [
    # Live messaging & rolls
    ("campaign_whispers", [("campaign_name", 1)], {"name": "idx_campaign_whispers_campaign_name"}),
    ("campaign_roll_requests", [("campaign_name", 1)], {"name": "idx_campaign_roll_requests_campaign_name"}),

    # Characters: unique char_id plus query performance
    ("characters", [("char_id", 1)], {"unique": True, "name": "uniq_char_id"}),
    ("characters", [("owner_id", 1)], {"name": "idx_characters_owner_id"}),
    ("characters", [("active_campaign", 1)], {"name": "idx_characters_active_campaign"}),
    ("characters", [("char_id", 1), ("owner_id", 1)], {"name": "idx_characters_char_id_owner_id"}),

    # Users: unique username and unique id
    ("users", [("username", 1)], {"unique": True, "name": "uniq_users_username"}),
    ("users", [("id", 1)], {"unique": True, "name": "uniq_users_id"}),

    # Campaigns: unique campaign_name
    ("campaigns", [("campaign_name", 1)], {"unique": True, "name": "uniq_campaigns_campaign_name"}),

    # Campaign members: compound unique index to prevent duplicate joins
    ("campaign_members", [("campaign_id", 1), ("user_id", 1)], {"unique": True, "name": "uniq_campaign_members_campaign_user"}),

    # Entities and logs
    ("campaign_entities", [("campaign_name", 1)], {"name": "idx_campaign_entities_campaign_name"}),
    ("session_logs", [("campaign_name", 1), ("session_number", -1)], {"name": "idx_session_logs_campaign_session"}),
]
```

---

## ⚡ Concurrency & Race Condition Invariants

1. **Defensive Index Startup:**
   - Index creation catches errors in individual `try/except` blocks. Pre-existing duplicates log an error but never crash server startup.

2. **DuplicateKeyError Handling:**
   - `auth_router.register`: Catches `DuplicateKeyError` and returns `HTTP 400 Bad Request`.
   - `campaign_router.save_campaign`: Uses `insert_one` for new campaigns and catches `DuplicateKeyError` to return `HTTP 409 Conflict`.
   - `campaign_router.join_campaign_by_code`: Executes `insert_one` on `campaign_members` **before** updating `campaigns.party` or `characters.active_campaign`. If the user has already joined, it catches `DuplicateKeyError` and returns `HTTP 409 Conflict` without mutating other documents.

3. **Optimistic Locking on Character Edits:**
   - Characters include an integer `version` field.
   - `PUT /characters/{char_id}` checks `{"version": client_version}` and increments on save (`$inc: {"version": 1}`). Concurrent writes trigger `HTTP 409 Conflict`.

4. **Atomic Positional Updates for VTT:**
   - Token moves in `vtt_service.py` use positional operator `vtt_state.tokens.$.x` rather than blind document replacement.
