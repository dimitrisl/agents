# 🌐 Subsystem: Server Core (`server/`)

## 📌 Overview
The `server/` directory contains the FastAPI server foundation, configuration, database connectivity, and application lifespan.

---

## 🔑 Key Files

| File | Responsibility |
| :--- | :--- |
| [`server/main.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/main.py) | Application factory (`app = FastAPI(...)`), async lifespan context manager (`lifespan`), CORS middleware, static file mounting (`/data/portraits`), and router mounting. |
| [`server/config.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/config.py) | Pydantic Settings model reading environment variables (`MONGO_URI`, `DATABASE_NAME`, `GEMINI_API_KEY`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `DEBUG_MODE`). |
| [`server/db_async.py`](file:///home/dimitrisl/Public/yet_another_dnd_project/agents/server/db_async.py) | Async Motor MongoDB client lifecycle, singleton accessor (`get_database()`), and index initialization (`init_indexes()`). |

---

## 📐 Invariants
1. **Async Lifespan:** The server connects to MongoDB during startup and closes the client during shutdown via the `@asynccontextmanager` in `main.py`.
2. **Defensive Indexing:** Index setup in `db_async.py` handles exceptions gracefully per index definition, preventing startup failures on pre-existing data conflicts.
