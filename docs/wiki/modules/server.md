# 🌐 Subsystem: Server Core (`server/`)

## 📌 Overview
The `server/` directory contains the FastAPI server foundation, configuration, database connectivity, and application lifespan.

---

## 🔑 Key Files

| File | Responsibility |
| :--- | :--- |
| [`server/main.py`](../../../server/main.py) | Application factory (`app = FastAPI(...)`), async lifespan context manager (`lifespan`), CORS middleware, `/api/v1/portraits` static file mount, rate-limit-exempt `GET /api/v1/health` probe, and router mounting. |
| [`server/config.py`](../../../server/config.py) | Pydantic Settings model reading environment variables (`MONGO_URI`, `DATABASE_NAME`, `GEMINI_API_KEY`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `DEBUG_MODE`, `TRUSTED_PROXIES`). |
| [`server/db_async.py`](../../../server/db_async.py) | Async Motor MongoDB client lifecycle, singleton accessor (`get_database()`), and index initialization (`init_indexes()`). |
| [`Dockerfile.backend`](../../../Dockerfile.backend) & [`docker-compose.yml`](../../../docker-compose.yml) | Non-root (`appuser`) Python 3.13 production image bundling `data/rules/` & `data/pdf_mappings/`, running `uvicorn --proxy-headers` scoped strictly to explicit `TRUSTED_PROXIES` CIDRs (loopback-bound backend port by default), container healthcheck against `/api/v1/health`, and persistent volumes for `mongo_data`, `portraits_data` (`/app/data/portraits`), `uploads_data` (`/app/data/uploads`), and `module_pics_data` (`/app/data/module_pics`). |

---

## 📐 Invariants
1. **Async Lifespan:** The server connects to MongoDB during startup and closes the client during shutdown via the `@asynccontextmanager` in `main.py`.
2. **Defensive Indexing:** Index setup in `db_async.py` handles exceptions gracefully per index definition, preventing startup failures on pre-existing data conflicts.
3. **Health Probe Isolation:** `GET /api/v1/health` is decorated with `@limiter.exempt`, runs `await db.command("ping")`, returns `200 healthy` when MongoDB responds, and returns `503 unhealthy` on failure without leaking internal database URIs or stack traces.
