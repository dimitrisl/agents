import logging
import secrets

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("PhyrexianForge.Config")


def _generate_dev_secret() -> str:
    """Generate a random secret for development. Logs a warning."""
    key = secrets.token_urlsafe(32)
    logger.warning(
        "JWT_SECRET_KEY not set — generated a random ephemeral key. "
        "All tokens will be invalidated on restart. Set JWT_SECRET_KEY in .env for production."
    )
    return key


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

    # Security
    SECRET_KEY: str = Field(
        default_factory=_generate_dev_secret,
        alias="JWT_SECRET_KEY",
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS — comma-separated origins, e.g. "http://localhost:4200,https://app.phyrexian.forge"
    CORS_ORIGINS: str = "http://localhost:4200"

    # Debug mode — enables demo login bypass. MUST be False in production.
    DEBUG_MODE: bool = False

    MONGO_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = Field(default="phyrexian_forge", alias="MONGO_DB_NAME")

    GEMINI_API_KEY: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
if settings.GEMINI_API_KEY:
    import os

    os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
