# 💉 Subsystem: Server Dependencies (`server/dependencies/`)

## 📌 Overview
The `server/dependencies/` package implements FastAPI dependency injection providers for authentication, current user resolution, and campaign role-based access control.

---

## 🔑 Key Dependency Providers

| Module | Dependency | Description |
| :--- | :--- | :--- |
| [`auth.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/dependencies/auth.py) | `get_current_user` | Decodes JWT from Authorization header, validates signature, verifies user state via `get_current_user_from_token`, and enforces `must_change_password` lock (`HTTP 403` outside `/auth/*`). |
| [`auth.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/dependencies/auth.py) | `get_current_user_from_token` | Core token decoding helper used by both HTTP routes and WebSocket auth frames; enforces `iat >= created_at`, `tv >= user.token_version`, computes `is_demo`/`has_password`/`auth_providers`, and strips `password_hash`. |
| [`campaign.py`](../../../server/dependencies/campaign.py) | `require_campaign_member()` | Verifies that `current_user` has an active record in `campaign_members` for the campaign specified in the route path parameter `{name}`. |
| [`campaign.py`](../../../server/dependencies/campaign.py) | `require_campaign_role(*roles)` | Enforces specific roles (e.g. `require_campaign_role("dm")`). Returns `HTTP 403 Forbidden` if the user's role does not match. |
