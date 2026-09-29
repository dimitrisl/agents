import logging

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient

from server.config import settings

logger = logging.getLogger("PhyrexianForge.AsyncDB")

client: AsyncIOMotorClient = None


async def connect_to_mongo():
    global client
    logger.info("Connecting to MongoDB Atlas async via Motor...")
    client = AsyncIOMotorClient(settings.MONGO_URI)

    # Initialize indexes for campaign collections
    database = client[settings.DATABASE_NAME]
    try:
        await database["campaign_whispers"].create_index([("campaign_name", pymongo.ASCENDING)])
        await database["campaign_roll_requests"].create_index(
            [("campaign_name", pymongo.ASCENDING)]
        )
        logger.info("Ensured indexes for campaign_whispers and campaign_roll_requests")
    except Exception as e:
        logger.error(f"Failed to create indexes: {e}")

    logger.info("Async MongoDB connection initialized.")


async def close_mongo_connection():
    global client
    logger.info("Closing async MongoDB connection...")
    if client:
        client.close()
        logger.info("Async MongoDB connection closed.")


async def get_database():
    global client
    if client is None:
        client = AsyncIOMotorClient(settings.MONGO_URI)
    return client[settings.DATABASE_NAME]
