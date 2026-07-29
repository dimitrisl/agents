from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    PROJECT_NAME: str = "Phyrexian Forge API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    SECRET_KEY: str = Field(
        default="phyrexian_forge_secret_key_change_in_production_12345",
        alias="JWT_SECRET_KEY",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    MONGO_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = Field(default="phyrexian_forge", alias="MONGO_DB_NAME")

    GEMINI_API_KEY: str = ""


settings = Settings()
