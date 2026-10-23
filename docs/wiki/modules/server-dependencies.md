# 💉 Subsystem: Server Dependencies (`server/dependencies/`)

## 📌 Overview
The `server/dependencies/` package implements FastAPI dependency injection providers for authentication, current user resolution, and campaign role-based access control.

---

## 🔑 Key Dependency Providers

| Module | Dependency | Description |
| :--- | :--- | :--- |
| [`auth.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/dependencies/auth.py) | `get_current_user` | Decodes JWT from Authorization header, validates token signature, queries `users` collection, and returns the current user document (without `password_hash`). |
| [`auth.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/dependencies/auth.py) | `get_current_user_from_token` | Core token decoding helper used by both HTTP routes and the WebSocket auth handshake frame. |
| [`campaign.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/dependencies/campaign.py) | `require_campaign_member()` | Verifies that `current_user` has an active record in `campaign_members` for the campaign specified in the route path parameter `{name}`. |
| [`campaign.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/dependencies/campaign.py) | `require_campaign_role(*roles)` | Enforces specific roles (e.g. `require_campaign_role("dm")`). Returns `HTTP 403 Forbidden` if the user's role does not match. |
