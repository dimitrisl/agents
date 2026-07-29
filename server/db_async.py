import logging
from motor.motor_asyncio import AsyncIOMotorClient
from server.config import settings

logger = logging.getLogger("PhyrexianForge.AsyncDB")


class Database:
    client: AsyncIOMotorClient = None


db = Database()


async def connect_to_mongo():
    logger.info("Connecting to MongoDB Atlas async via Motor...")
    db.client = AsyncIOMotorClient(settings.MONGO_URI)
    logger.info("Async MongoDB connection initialized.")


async def close_mongo_connection():
    logger.info("Closing async MongoDB connection...")
    if db.client:
        db.client.close()
        logger.info("Async MongoDB connection closed.")


def get_database():
    if db.client is None:
        db.client = AsyncIOMotorClient(settings.MONGO_URI)
    return db.client[settings.DATABASE_NAME]
