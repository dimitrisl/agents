import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
    allow_origins=[
        "http://localhost:4200",  # Angular CLI default dev server
        "http://127.0.0.1:4200",
        "http://localhost:8000",
        "*",
    ],
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


@app.get("/")
async def root():
    return {
        "status": "online",
        "system": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
    }
