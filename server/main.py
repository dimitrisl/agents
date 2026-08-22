import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from server.config import settings
from server.db_async import close_mongo_connection, connect_to_mongo
from server.routers import (
    auth_router,
    campaign_router,
    character_router,
    dm_router,
    forge_router,
    rules_router,
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
    await connect_to_mongo()
    yield
    # Shutdown: Close connection
    logger.info("Shutting down Phyrexian Forge FastAPI Backend Server...")
    await close_mongo_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

# CORS Configuration for Angular frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth_router.router, prefix=settings.API_V1_STR)
app.include_router(character_router.router, prefix=settings.API_V1_STR)
app.include_router(forge_router.router, prefix=settings.API_V1_STR)
app.include_router(campaign_router.router, prefix=settings.API_V1_STR)
app.include_router(dm_router.router, prefix=settings.API_V1_STR)
app.include_router(rules_router.router, prefix=settings.API_V1_STR)
app.include_router(websocket_router.router)

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
