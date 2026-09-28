import os

ALLOWED_DIRS = {
    "portraits": os.path.abspath("data/portraits"),
    "uploads": os.path.abspath("data/uploads"),
    "module_pics": os.path.abspath("data/module_pics"),
}


def safe_path(path: str, scope: str = "portraits") -> str:
    """Ensures a path is confined to an allowed directory."""
    base = ALLOWED_DIRS.get(scope)
    if not base:
        raise ValueError(f"Unknown path scope: {scope}")
    resolved = os.path.abspath(path)
    if not resolved.startswith(base + os.sep) and resolved != base:
        raise ValueError(f"Path traversal detected: {path} is outside of {base}")
    return resolved
