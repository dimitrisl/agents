import logging
import os
from contextlib import asynccontextmanager

import slowapi.middleware
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded

from server.config import settings
from server.db_async import close_mongo_connection, connect_to_mongo
from server.rate_limiter import (
    PhyrexianSlowAPIMiddleware,
    custom_find_route_handler,
    limiter,
    rate_limit_exceeded_handler,
)
from server.routers import (
    admin_router,
    assets_router,
    auth_router,
    campaign_router,
    character_router,
    dm_router,
    forge_router,
    homebrew_router,
    rules_router,
    session_router,
    websocket_router,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("PhyrexianForge.Server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB async
    logger.info("Initializing Phyrexian Forge FastAPI Backend Server...")
    os.makedirs(os.path.join("data", "portraits"), exist_ok=True)
    try:
        await connect_to_mongo()
    except Exception as e:
        logger.error(f"Failed during async MongoDB connection initialization: {e}")
    yield
    # Shutdown: Close connection
    logger.info("Shutting down Phyrexian Forge FastAPI Backend Server...")
    try:
        await close_mongo_connection()
    except Exception as e:
        logger.error(f"Failed during async MongoDB connection shutdown: {e}")


# Patch slowapi route handler lookup for nested FastAPI routers
slowapi.middleware._find_route_handler = custom_find_route_handler

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# SlowAPI Rate Limiting setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(PhyrexianSlowAPIMiddleware)

# CORS Configuration for Angular frontend (outermost middleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router.router, prefix=settings.API_V1_STR)
app.include_router(admin_router.router, prefix=settings.API_V1_STR)
app.include_router(character_router.router, prefix=settings.API_V1_STR)
app.include_router(forge_router.router, prefix=settings.API_V1_STR)
app.include_router(campaign_router.router, prefix=settings.API_V1_STR)
app.include_router(homebrew_router.router, prefix=settings.API_V1_STR)
app.include_router(dm_router.router, prefix=settings.API_V1_STR)
app.include_router(rules_router.router, prefix=settings.API_V1_STR)
app.include_router(session_router.router, prefix=settings.API_V1_STR)
app.include_router(assets_router.router, prefix=settings.API_V1_STR)
app.include_router(websocket_router.router)

os.makedirs(os.path.join("data", "portraits"), exist_ok=True)

# Mount portrait images directory
app.mount(
    f"{settings.API_V1_STR}/portraits",
    StaticFiles(directory=os.path.join("data", "portraits")),
    name="portraits",
)


@app.get("/")
async def root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
    }


def main():
    import uvicorn

    uvicorn.run("server.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
