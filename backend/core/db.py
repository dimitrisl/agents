import logging
import os

import streamlit as st
from pymongo import MongoClient

logger = logging.getLogger("DnDAssistant.Database")


@st.cache_resource(show_spinner=False)
def _init_db():
    uri = os.environ.get("MONGO_URI")
    if not uri:
        logger.error("MONGO_URI is missing from .env file!")
        return None

    try:
        import certifi

        client = MongoClient(uri, tlsCAFile=certifi.where())
        db = client["phyrexiadb"]
        logger.info("Successfully connected to MongoDB Atlas connection pool.")
        return db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return None


def get_db():
    return _init_db()
