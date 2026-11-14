import os

ALLOWED_DIRS = {
    "portraits": os.path.realpath("data/portraits"),
    "uploads": os.path.realpath("data/uploads"),
    "module_pics": os.path.realpath("data/module_pics"),
}


def safe_path(path: str, scope: str = "portraits") -> str:
    """Ensures a path is confined to an allowed directory."""
    base = ALLOWED_DIRS.get(scope)
    if not base:
        raise ValueError(f"Unknown path scope: {scope}")
    resolved = os.path.realpath(path)
    if os.path.commonpath([base, resolved]) != base:
        raise ValueError(f"Path traversal detected: {path} is outside of {base}")
    return resolved
