import hashlib


def hash_password(password: str) -> str:
    """Consistently hashes a password using SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()
