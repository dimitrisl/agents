# 🛡️ Concept: Authentication & Security (`docs/wiki/concepts/auth-and-security.md`)

## 📌 Overview
Security in **Phyrexian Forge** relies on standard JWT bearer tokens, database-backed Role-Based Access Control (RBAC), owner-scoped mutations to prevent Insecure Direct Object References (IDOR), and strict filesystem path sanitization.

---

## 🔑 Authentication Architecture

1. **Password Hashing:**
   - Handled via `passlib.context.CryptContext` using `pbkdf2_sha256`.
   - Backward-compatible verification supports legacy SHA-256 hashes (`legacy_sha256_hash`).

2. **JWT Access Tokens:**
   - Signed using `HS256` with `settings.SECRET_KEY` (minimum 32-byte key required by RFC 7518).
   - Payload contains `sub` (user ID) and `username`.
   - Default expiration is configured via `settings.ACCESS_TOKEN_EXPIRE_MINUTES` (7 days).

3. **Debug Mode Isolation:**
   - Demo logins (e.g. `mitsos`, `adventurer`) are gated behind `settings.DEBUG_MODE = True`.
   - In production environments (`DEBUG_MODE = False`), demo authentication endpoints return `HTTP 403 Forbidden`.

---

## 🛡️ Authorization & IDOR Defenses

### 1. Campaign Role Guards (`server/dependencies/campaign.py`)
- `require_campaign_role("dm")`: Verifies that the authenticated user has an active membership record in `campaign_members` with `role == "dm"`.
- `require_campaign_member()`: Verifies that the user belongs to the campaign as either a DM or a player.

### 2. Owner-Scoped Mutations (IDOR Prevention)
- Updates and deletions to characters in `character_router.py` enforce `{"char_id": char_id, "owner_id": current_user["id"]}`.
- Character creation and PDF imports generate a fresh `uuid4` if an existing `char_id` belongs to another user.
- A user cannot move another user's hero into a campaign during `/campaigns/join`.

### 3. File System & Path Traversal Guards (`backend/utils/path_safety.py`)
- All file reads, uploads, and image writes must pass through `safe_path(filepath, scope="portraits"|"uploads")`.
- Validates that the resolved absolute path resides strictly within the designated directory using `os.path.commonpath`. Any attempts to use `../` or absolute root paths raise an immediate `HTTP 400 Bad Request`.
