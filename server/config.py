import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Phyrexian Forge API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "phyrexian_forge_secret_key_change_in_production_12345"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    MONGO_URI: str = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    DATABASE_NAME: str = os.getenv("MONGO_DB_NAME", "phyrexian_forge")

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


settings = Settings()
