import logging

import pymongo
from motor.motor_asyncio import AsyncIOMotorClient

from server.config import settings

logger = logging.getLogger("PhyrexianForge.AsyncDB")

client: AsyncIOMotorClient = None


INDEX_DEFINITIONS = [
    # Campaign live messaging & roll requests
    (
        "campaign_whispers",
        [("campaign_name", pymongo.ASCENDING)],
        {"name": "idx_campaign_whispers_campaign_name"},
    ),
    (
        "campaign_roll_requests",
        [("campaign_name", pymongo.ASCENDING)],
        {"name": "idx_campaign_roll_requests_campaign_name"},
    ),
    # Characters: unique char_id plus query performance indexes
    ("characters", [("char_id", pymongo.ASCENDING)], {"unique": True, "name": "uniq_char_id"}),
    ("characters", [("owner_id", pymongo.ASCENDING)], {"name": "idx_characters_owner_id"}),
    (
        "characters",
        [("active_campaign", pymongo.ASCENDING)],
        {"name": "idx_characters_active_campaign"},
    ),
    (
        "characters",
        [("char_id", pymongo.ASCENDING), ("owner_id", pymongo.ASCENDING)],
        {"name": "idx_characters_char_id_owner_id"},
    ),
    # Users: globally unique username and unique id
    ("users", [("username", pymongo.ASCENDING)], {"unique": True, "name": "uniq_users_username"}),
    ("users", [("id", pymongo.ASCENDING)], {"unique": True, "name": "uniq_users_id"}),
    # Campaigns: unique campaign_name and unique sparse invite_code
    (
        "campaigns",
        [("campaign_name", pymongo.ASCENDING)],
        {"unique": True, "name": "uniq_campaigns_campaign_name"},
    ),
    (
        "campaigns",
        [("invite_code", pymongo.ASCENDING)],
        {"unique": True, "sparse": True, "name": "uniq_campaigns_invite_code"},
    ),
    # Campaign members: compound unique index on (campaign_id, user_id) to prevent duplicate memberships
    (
        "campaign_members",
        [("campaign_id", pymongo.ASCENDING), ("user_id", pymongo.ASCENDING)],
        {"unique": True, "name": "uniq_campaign_members_campaign_user"},
    ),
    # Campaign entities: query index on campaign_name
    (
        "campaign_entities",
        [("campaign_name", pymongo.ASCENDING)],
        {"name": "idx_campaign_entities_campaign_name"},
    ),
    # Session logs: compound query index on (campaign_name ASC, session_number DESC)
    (
        "session_logs",
        [("campaign_name", pymongo.ASCENDING), ("session_number", pymongo.DESCENDING)],
        {"name": "idx_session_logs_campaign_session"},
    ),
    # Whisper TTL index (#155) - expires after WHISPER_RETENTION_DAYS unless has_open_report is True
    (
        "campaign_whispers",
        [("created_at", pymongo.ASCENDING)],
        {
            "name": "ttl_campaign_whispers_created_at",
            "expireAfterSeconds": settings.WHISPER_RETENTION_DAYS * 86400,
            "partialFilterExpression": {"has_open_report": {"$eq": False}},
        },
    ),
    # Whisper reports (#155)
    (
        "whisper_reports",
        [("report_id", pymongo.ASCENDING)],
        {"unique": True, "name": "uniq_whisper_reports_report_id"},
    ),
    (
        "whisper_reports",
        [("status", pymongo.ASCENDING), ("created_at", pymongo.DESCENDING)],
        {"name": "idx_whisper_reports_status_created"},
    ),
    # VTT Scenes, History & Assets (#156)
    (
        "campaign_scenes",
        [("scene_id", pymongo.ASCENDING)],
        {"unique": True, "name": "uniq_campaign_scenes_scene_id"},
    ),
    (
        "campaign_scenes",
        [("campaign_name", pymongo.ASCENDING), ("order", pymongo.ASCENDING)],
        {"name": "idx_campaign_scenes_campaign_order"},
    ),
    (
        "campaign_scene_history",
        [("campaign_name", pymongo.ASCENDING), ("activated_at", pymongo.DESCENDING)],
        {"name": "idx_campaign_scene_history_campaign_activated"},
    ),
    (
        "campaign_assets",
        [("filename", pymongo.ASCENDING)],
        {"unique": True, "name": "uniq_campaign_assets_filename"},
    ),
    (
        "campaign_assets",
        [("campaign_name", pymongo.ASCENDING)],
        {"name": "idx_campaign_assets_campaign_name"},
    ),
]


async def init_indexes(database):
    """
    Ensure all required unique and query performance indexes exist in MongoDB.
    Each index creation is isolated in its own try/except block so that pre-existing
    duplicate entries or conflicts in one collection never crash server startup
    or block other indexes from being created.
    """
    for coll_name, keys, kwargs in INDEX_DEFINITIONS:
        idx_name = kwargs.get("name", str(keys))
        try:
            await database[coll_name].create_index(keys, **kwargs)
            logger.info("Ensured index '%s' on collection '%s'", idx_name, coll_name)
        except Exception as e:
            err_str = str(e)
            if "Index already exists with a different name" in err_str:
                logger.info(
                    "Index '%s' on collection '%s' already exists with a different name: %s",
                    idx_name,
                    coll_name,
                    e,
                )
            else:
                logger.error(
                    "Failed to create index '%s' on collection '%s' "
                    "(duplicate entries or conflict already present?): %s",
                    idx_name,
                    coll_name,
                    e,
                )


async def connect_to_mongo():
    global client
    logger.info("Connecting to MongoDB Atlas async via Motor...")
    client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)

    # Defensively check connectivity before attempting to create indexes
    try:
        await client.admin.command("ping")
        database = client[settings.DATABASE_NAME]
        await init_indexes(database)
        logger.info("Async MongoDB connection and indexes initialized.")
    except Exception as e:
        logger.warning(
            "MongoDB ping/connect failed (%s). Skipping index initialization (offline/testing environment).",
            e,
        )


async def close_mongo_connection():
    global client
    logger.info("Closing async MongoDB connection...")
    if client:
        client.close()
        logger.info("Async MongoDB connection closed.")


async def get_database():
    global client
    if client is None:
        client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
    return client[settings.DATABASE_NAME]
