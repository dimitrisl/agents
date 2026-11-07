# 🛡️ Concept: Authentication & Security (`docs/wiki/concepts/auth-and-security.md`)

## 📌 Overview
Security in **Phyrexian Forge** relies on standard JWT bearer tokens, database-backed Role-Based Access Control (RBAC), owner-scoped mutations to prevent Insecure Direct Object References (IDOR), and strict filesystem path sanitization.

---

## 🔑 Authentication Architecture

1. **Password Hashing & Transparent Migration:**
   - Handled via `passlib.context.CryptContext` using `pbkdf2_sha256`.
   - Backward-compatible verification supports legacy SHA-256 hashes (`legacy_sha256_hash`).
   - **Transparent Hash Upgrade:** When a user with a legacy SHA-256 hash successfully logs in (`/api/v1/auth/login`), the server automatically upgrades their password hash to PBKDF2 (`hash_password(form_data.password)`) and persists it in MongoDB, seamlessly eliminating legacy hashes over time without requiring password resets.

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

### 5. Encrypted User API Keys at Rest (`server/secret_box.py`)
- User-supplied third-party API keys (e.g., personal Anthropic Claude keys stored via `/api/v1/settings`) are never persisted in plaintext in MongoDB.
- Encrypted and decrypted via `cryptography.fernet.Fernet` using a 32-byte key derived from `SHA-256("user-api-keys:" + settings.SECRET_KEY)`.
- API responses only return boolean/masked indicators (`has_anthropic_key`), never echoing the raw or encrypted key back to the client.

### 6. SSRF Protection in PDF Export (`backend/utils/pdf_exporter.py`)
- When fetching external character portraits for PDF sheet export, `requests.get` strictly enforces `allow_redirects=False` and a 5-second timeout.
- This prevents Server-Side Request Forgery (SSRF) via open redirectors attempting to pivot to internal link-local or cloud metadata endpoints (`169.254.169.254`).

### 7. Dice Expression Computational DoS Guard (`backend/services/dice_service.py`)
- Protects the asynchronous event loop against CPU exhaustion from unbounded dice roll expressions (e.g. `100000d100000`):
  - Limits dice count per term: `dice <= 100`.
  - Limits total dice rolled across multi-die expressions: `total_dice <= 200`.
  - Limits dice sides: `sides <= 1000`.
  - Immediately raises `ValueError` before computing or generating random numbers if any limit is exceeded.

### 8. Search Query Sanitization & ReDoS Prevention (`server/routers/admin_router.py`)
- User search queries in admin endpoints are sanitized using `re.escape(search.strip())` before constructing regex patterns for MongoDB queries (`{"$regex": re.escape(search.strip()), "$options": "i"}`).
- Protects against Regular Expression Denial of Service (ReDoS) and malformed regex injections.

### 9. Aborted Upload File System Cleanup (`server/routers/character_router.py`, `server/routers/assets_router.py`)
- File uploads for character portraits and campaign battle map assets wrap file stream writes in `try/except Exception` blocks.
- If the upload stream is truncated, the client disconnects, or subsequent database operations fail, any partially written file on disk is immediately unlinked (`os.remove`), preventing disk exhaustion from abandoned artifacts.

### 10. Whisper Privacy & MongoDB Query-Level Isolation (`server/routers/campaign_router.py`)
- Retrieval of campaign messages and whispers via `/campaigns/{name}/messages` enforces privacy checks directly inside the MongoDB query filter (`$or: [{"whisper_to": None}, {"whisper_to": current_username}, {"sender": current_username}]`).
- Pushing whisper authorization down to the database query prevents confidential whispers from leaking over the wire and eliminates post-query pagination starvation where players could receive empty message batches.

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
