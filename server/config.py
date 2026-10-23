import logging
import secrets

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("PhyrexianForge.Config")


def _generate_dev_secret() -> str:
    """Generate a random secret for development. Logs a warning."""
    key = secrets.token_urlsafe(64)
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

    # Rate Limiting & Proxies
    RATE_LIMIT_ENABLED: bool = True
    AUTH_LOGIN_RATE_LIMIT: str = "5/minute"
    AUTH_REGISTER_RATE_LIMIT: str = "3/minute"
    AI_RATE_LIMIT: str = "10/minute"
    AUDIO_SESSION_RATE_LIMIT: str = "2/minute"
    GLOBAL_RATE_LIMIT: str = "100/minute"
    TRUSTED_PROXIES: str = "127.0.0.1,::1,testclient,localhost"

    # Audio session uploads (100 MB max cap)
    MAX_AUDIO_FILE_SIZE_BYTES: int = 100 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS into a list."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def trusted_proxy_list(self) -> list[str]:
        """Parse comma-separated TRUSTED_PROXIES into a list."""
        return [p.strip() for p in self.TRUSTED_PROXIES.split(",") if p.strip()]


settings = Settings()
if settings.SECRET_KEY and len(settings.SECRET_KEY.encode("utf-8")) < 32:
    logger.warning(
        "JWT_SECRET_KEY is shorter than 32 bytes (256 bits). "
        "RFC 7518 requires keys for HMAC-SHA256 to be at least 32 bytes."
    )
if settings.GEMINI_API_KEY:
    import os

    os.environ["GEMINI_API_KEY"] = settings.GEMINI_API_KEY
