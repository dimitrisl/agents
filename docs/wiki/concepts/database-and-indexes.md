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
| `campaign_members` | `campaign_id`, `user_id`, `role` (`dm`\|`player`), `character_id`, `character_ids`, `joined_at` | Campaign membership, permissions, and multi-character enrollment per user. |
| `campaign_entities` | `campaign_name`, `name`, `type`, `content`, `tags`, `created_at` | NPCs, locations, factions, and lore cards. |
| `session_logs` | `campaign_name`, `session_number`, `title`, `summary`, `real_world_date` | Chronological session recaps and journal. |
| `campaign_whispers` | `campaign_name`, `sender`, `sender_user_id`, `sender_character_id`, `recipient`, `recipient_user_id`, `recipient_character_id`, `message`, `timestamp` | In-game text messages and ID-disambiguated whispers. |
| `campaign_roll_requests` | `campaign_name`, `char_filename`, `target_char_id`, `target_owner_id`, `roll_type`, `stat`, `status`, `result` | Dice roll requests issued by DM. |
| `campaign_roll_logs` | `id`, `campaign_name`, `sender_user_id`, `sender_username`, `char_id`, `char_name`, `roll_label`, `roll_type`, `formula`, `total`, `visibility`, `created_at` | Persistent log of player sheet rolls (`public` or `dm`-whispered). |
| `homebrew_content` | `campaign_name`, `creator_dm_id`, `type`, `item_data` | Custom weapons, spells, and items scoped to a campaign. |
| `custom_monsters` | `id`, `name`, `creator_dm_id`, `is_public`, `cr_numeric`, `edition` | Custom DM and community homebrew monsters. |
| `official_monsters` | `id`, `name`, `edition`, `cr_numeric`, `type`, `stats`, `actions` | Scaled database vault of official 2014 & 2024 monsters. |

---

## 🛡️ Index Catalog (`server/db_async.py`)

All collections are indexed defensively during startup via `init_indexes(database)`:

```python
INDEX_DEFINITIONS = [
    # Live messaging & rolls
    ("campaign_whispers", [("campaign_name", 1)], {"name": "idx_campaign_whispers_campaign_name"}),
    ("campaign_roll_requests", [("campaign_name", 1)], {"name": "idx_campaign_roll_requests_campaign_name"}),
    ("campaign_roll_logs", [("campaign_name", 1), ("created_at", -1)], {"name": "idx_campaign_roll_logs_campaign_created"}),

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

    # Bestiary: custom monsters collection
    ("custom_monsters", [("id", 1)], {"unique": True, "name": "uniq_custom_monsters_id"}),
    ("custom_monsters", [("creator_dm_id", 1)], {"name": "idx_custom_monsters_creator_dm_id"}),
    ("custom_monsters", [("is_public", 1)], {"name": "idx_custom_monsters_is_public"}),
    ("custom_monsters", [("creator_dm_id", 1), ("is_public", 1)], {"name": "idx_custom_monsters_creator_public"}),

    # Bestiary: official monsters collection (seeded from 2014 & 2024 Monster Manuals)
    ("official_monsters", [("id", 1)], {"unique": True, "name": "uniq_official_monsters_id"}),
    ("official_monsters", [("edition", 1), ("cr_numeric", 1), ("name", 1)], {"name": "idx_official_monsters_edition_cr_name"}),
    ("official_monsters", [("edition", 1), ("type", 1)], {"name": "idx_official_monsters_edition_type"}),
]
```

---

## ⚡ Concurrency & Race Condition Invariants

1. **Defensive Index Startup:**
   - Index creation catches errors in individual `try/except` blocks. Pre-existing duplicates log an error but never crash server startup.

2. **DuplicateKeyError Handling:**
   - `auth_router.register`: Catches `DuplicateKeyError` and returns `HTTP 400 Bad Request`.
   - `campaign_router.save_campaign`: Uses `insert_one` for new campaigns and catches `DuplicateKeyError` to return `HTTP 409 Conflict`.
   - `campaign_router.join_campaign_by_code`: Checks existing membership in `campaign_members`. If the user has not joined yet, it executes `insert_one` with `character_id` and `character_ids` **before** updating `campaigns.party` or `characters.active_campaign` (catching `DuplicateKeyError` on races -> `HTTP 409 Conflict`). If the user is already a member and supplies a different owned character, it atomically enrolls the additional `char_id` via `$addToSet` on `character_ids` (rejecting duplicate enrollment of the *same* character with `HTTP 409 Conflict`).

3. **Optimistic Locking on Character Edits:**
   - Characters include an integer `version` field.
   - `PUT /characters/{char_id}` checks `{"version": client_version}` and increments on save (`$inc: {"version": 1}`). Concurrent writes trigger `HTTP 409 Conflict`.

4. **Atomic Positional Updates for VTT:**
   - Token moves in `vtt_service.py` use positional operator `vtt_state.tokens.$.x` rather than blind document replacement.
