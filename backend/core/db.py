import os
import logging
from pymongo import MongoClient
from dotenv import load_dotenv

# Ensure environment variables are loaded
load_dotenv()

logger = logging.getLogger("DnDAssistant.Database")

_client = None
_db = None


def get_db():
    global _client, _db
    if _db is not None:
        return _db

    uri = os.environ.get("MONGO_URI")
    if not uri:
        logger.error("MONGO_URI is missing from .env file!")
        return None

    try:
        _client = MongoClient(uri)
        # We explicitly name the database 'phyrexiadb'
        _db = _client["phyrexiadb"]
        logger.info("Successfully connected to MongoDB Atlas.")
        return _db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return None
