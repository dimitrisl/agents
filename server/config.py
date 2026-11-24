import logging
import secrets
from typing import Optional

from pydantic import AliasChoices, Field, PrivateAttr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("PhyrexianForge.Config")

_INSECURE_PLACEHOLDER_SECRETS = frozenset(
    {
        "",
        "replace_with_a_secure_random_hex_string_in_production",
        "changeme",
        "secret",
        "your-secret-key",
    }
)


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
    SECRET_KEY: Optional[str] = Field(
        default=None,
        alias="JWT_SECRET_KEY",
    )
    _ephemeral_secret: bool = PrivateAttr(default=False)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS — comma-separated origins, e.g. "http://localhost:4200,https://app.phyrexian.forge"
    CORS_ORIGINS: str = "http://localhost:4200"

    # Debug mode — enables demo login bypass. MUST be False in production.
    DEBUG_MODE: bool = False

    @model_validator(mode="after")
    def _resolve_and_check_secret_key(self) -> "Settings":
        raw_secret = (self.SECRET_KEY or "").strip()
        if raw_secret in _INSECURE_PLACEHOLDER_SECRETS:
            if not self.DEBUG_MODE and self.SECRET_KEY is not None:
                raise RuntimeError(
                    "JWT_SECRET_KEY is set to an insecure placeholder value while DEBUG_MODE=False. "
                    "Set a strong random secret in .env or environment variables."
                )
            self._ephemeral_secret = True
            self.SECRET_KEY = _generate_dev_secret()
        else:
            self._ephemeral_secret = False
            self.SECRET_KEY = raw_secret
        return self

    @property
    def is_ephemeral_secret(self) -> bool:
        return self._ephemeral_secret

    def validate_production_secrets(self) -> None:
        """Fail fast if non-debug mode starts without a persistent JWT_SECRET_KEY."""
        if not self.DEBUG_MODE and (
            self._ephemeral_secret
            or (self.SECRET_KEY or "").strip() in _INSECURE_PLACEHOLDER_SECRETS
        ):
            raise RuntimeError(
                "JWT_SECRET_KEY must be explicitly configured when DEBUG_MODE=False. "
                "Refusing to boot with an ephemeral or placeholder signing key."
            )

    MONGO_URI: str = "mongodb://localhost:27017"
    DATABASE_NAME: str = Field(
        default="phyrexian_forge",
        validation_alias=AliasChoices("DATABASE_NAME", "MONGO_DB_NAME"),
    )

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

    # Whisper retention (days) for TTL index (#155)
    WHISPER_RETENTION_DAYS: int = 365

    # Character Import Limits (#152, #153)
    MAX_PDF_IMPORT_BYTES: int = 10 * 1024 * 1024  # 10 MB
    MAX_PDF_IMPORT_PAGES: int = 10
    MAX_PDF_TEXT_CHARS: int = 40_000
    MAX_FOUNDRY_IMPORT_BYTES: int = 5 * 1024 * 1024  # 5 MB
    DNDBEYOND_IMPORT_RATE_LIMIT: str = "10/minute"

    # Optional Discord OAuth2 Onboarding (#266)
    DISCORD_CLIENT_ID: str = ""
    DISCORD_CLIENT_SECRET: str = ""
    DISCORD_REDIRECT_URI: Optional[str] = None
    FRONTEND_URL: str = ""

    @property
    def discord_oauth_enabled(self) -> bool:
        """True only when both Discord OAuth2 credentials are non-empty."""
        return bool(self.DISCORD_CLIENT_ID.strip() and self.DISCORD_CLIENT_SECRET.strip())

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
