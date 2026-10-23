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

### 4. Audio File Upload Security (`backend/utils/audio_validator.py`)
- **Metadata & Extension Verification:** Validates allowed extensions (`.mp3`, `.wav`, `.m4a`, `.ogg`, `.webm`, `.flac`, `.aac`) and cross-validates against compatible MIME types (including RFC standards and browser variants).
- **Magic Byte Signature Inspection:** Validates binary container headers and audio stream syncwords:
  - **MP3:** Validates ID3v2 headers (version, revision, syncsafe integer constraints) and raw MPEG-1/2 frame sync.
  - **WAV:** Verifies `RIFF`/`RIFX` header and `WAVE` format marker.
  - **OGG:** Verifies `OggS` container capture pattern.
  - **FLAC:** Requires `fLaC` stream marker (even when preceded by ID3 tags).
  - **M4A:** Inspects `ftyp` box for audio brands (`m4a `, `mp41`, etc.) while explicitly rejecting image/non-audio ISOBMFF formats (`avif`, `heic`).
  - **WebM:** Verifies EBML header `\x1a\x45\xdf\xa3` and `webm`/`matroska` DocType.
  - **AAC:** Requires genuine ADTS frame sync (`0xFFF`, layer `00`) or `ADIF` stream marker.
  - **Disallowed Signatures:** Strictly rejects disguised executables (ELF, PE/MZ, Mach-O), archives (`7z`, `RAR`, `GZIP`, `XZ`), and scripts (`#!`, `<?php`, `<script`, HTML/XML).
- **Defensive Streaming & Size Cap (100MB):** Defensively streams uploads in 1MB chunks directly to disk while counting bytes. If the file exceeds `MAX_AUDIO_FILE_SIZE_BYTES` (100MB), the stream aborts with `HTTP 413 Content Too Large` and cleans up temporary files to prevent disk/memory exhaustion.

---

## ⏱️ Rate Limiting & DoS / Quota Exhaustion Defenses (`server/rate_limiter.py`)

To protect the server from credential brute-forcing and safeguard the Gemini API quota/wallet against infinite loops or abuse, **SlowAPI** is integrated:

### 1. Key Extraction & Isolation
- **Unauthenticated / Auth Endpoints:** Rate limited strictly per client IP address (`ip:<ip_address>`), resolving `X-Forwarded-For` when behind reverse proxies.
- **Authenticated / AI Endpoints:** Rate limited per user (`user:<user_id>`), fast-extracted from JWT Bearer tokens without requiring synchronous DB lookups.
- **Fallback:** Defaults to client IP when no valid token is provided.

### 2. Configured Thresholds
- **Auth Login (`/auth/login`, `/auth/demo`):** 5 requests / minute per IP.
- **Auth Registration (`/auth/register`):** 3 requests / minute per IP.
- **AI Endpoints (`/forge/*`, `/rules/query`, `/rules/compare`, `/rules/autofix`, `/dm/*`, `/homebrew/forge`):** 10 requests / minute per authenticated user.
- **Session Audio AI Processing (`/campaigns/{name}/sessions/audio`):** 2 requests / minute per DM.
- **Global Fallback:** 100 requests / minute per user/IP.

### 3. Standard 429 Responses & Headers
- On limit exhaustion, returns `HTTP 429 Too Many Requests` with:
  - `Retry-After: <seconds>`
  - `X-RateLimit-Limit: <limit>`
  - `X-RateLimit-Remaining: 0`
  - `X-RateLimit-Reset: <timestamp>`
  - JSON payload: `{"detail": "Rate limit exceeded: ...", "error": "Rate limit exceeded: ..."}`
- Testing hook: `settings.RATE_LIMIT_ENABLED = False` or `limiter.enabled = False` bypasses rate limits in test environments; `limiter.reset()` clears windows between tests.
