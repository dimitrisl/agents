"""Encrypts user-supplied secrets (e.g. their own Anthropic API key) at rest."""

import base64
import hashlib
import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from server.config import settings

logger = logging.getLogger("PhyrexianForge.SecretBox")

# Decryption runs on every authenticated request; say it once, not per request.
_warned_undecryptable = False


def _fernet() -> Fernet:
    # Derived from the JWT secret so no extra key has to be configured.
    # Rotating SECRET_KEY makes stored keys unreadable; users re-enter them.
    digest = hashlib.sha256(f"user-api-keys:{settings.SECRET_KEY}".encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        global _warned_undecryptable
        if not _warned_undecryptable:
            _warned_undecryptable = True
            logger.warning(
                "A stored API key could not be decrypted (JWT_SECRET_KEY changed or unset?); "
                "ignoring it. Affected users must re-enter their key in Settings."
            )
        return None
