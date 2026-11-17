import hashlib
import logging
import os
import shutil
import time
import urllib.parse
import uuid
from typing import Iterable

import httpx

from backend.core.prompts import PORTRAIT_PROMPT
from server.config import settings

logger = logging.getLogger("DnDAssistant.ImageUtils")

PORTRAIT_DIR = os.path.join("data", "portraits")


def _ensure_dir():
    os.makedirs(PORTRAIT_DIR, exist_ok=True)


async def generate_portrait_url(
    char_data: dict, force: bool = False, custom_prompt: str | None = None
) -> str:
    """
    Generates a character portrait using image.pollinations.ai,
    downloads it, saves it to a local folder, and returns the public API URL.
    """
    _ensure_dir()

    if custom_prompt and custom_prompt.strip():
        force = True

    # If the character already has a local portrait that exists, just return it.
    existing_portrait = char_data.get("char_portrait")
    base_url_path = f"{settings.API_V1_STR}/portraits/"
    from backend.utils.path_safety import safe_path

    if not force and existing_portrait and existing_portrait.startswith(base_url_path):
        filename = os.path.basename(existing_portrait)
        try:
            local_path = safe_path(os.path.join(PORTRAIT_DIR, filename), scope="portraits")
            if os.path.exists(local_path):
                return f"{base_url_path}{os.path.basename(local_path)}"
        except ValueError:
            logger.warning("Blocked invalid local portrait path: %r", existing_portrait)
    elif not force and existing_portrait and existing_portrait.startswith("data/portraits/"):
        # Legacy support (confined strictly to PORTRAIT_DIR)
        try:
            local_path = safe_path(existing_portrait, scope="portraits")
            if os.path.exists(local_path):
                filename = os.path.basename(local_path)
                return f"{base_url_path}{filename}"
        except ValueError:
            logger.warning(
                "Blocked traversal attempt in legacy portrait path: %r", existing_portrait
            )

    race = char_data.get("race", "Human")
    char_class = char_data.get("char_class", "Warrior")
    background = char_data.get("background", "")
    backstory = char_data.get("backstory", "")
    alignment = char_data.get("alignment", "")
    gender = char_data.get("gender", "")

    # Extract keywords from backstory (first 150 chars) to avoid prompt bloat
    visual_hooks = backstory[:150] if backstory else ""
    if custom_prompt and custom_prompt.strip():
        visual_hooks = (
            f"{custom_prompt.strip()}. {visual_hooks}".strip(". ")
            if visual_hooks
            else custom_prompt.strip()
        )

    # Construct a rich, descriptive prompt
    prompt = PORTRAIT_PROMPT.format(
        gender=gender,
        race=race,
        char_class=char_class,
        background=background if background else "N/A",
        alignment=alignment if alignment else "N/A",
        visual_hooks=visual_hooks if visual_hooks else "N/A",
    )

    # URL encode the full prompt
    encoded_prompt = urllib.parse.quote(prompt)

    # Use a stable seed based on char_id to keep the URL consistent
    char_id = char_data.get("char_id") or str(uuid.uuid4())[:8]
    if force:
        seed_src = f"{char_id}_{uuid.uuid4()}"
    else:
        seed_src = char_id
    seed = int(hashlib.md5(seed_src.encode()).hexdigest(), 16) % 999999

    image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=512&height=512&seed={seed}&nologo=true"

    try:
        max_image_bytes = 10 * 1024 * 1024
        image_buffer = bytearray()
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", image_url, timeout=15.0) as response:
                response.raise_for_status()
                content_type = (response.headers.get("content-type") or "").lower()
                if not content_type.startswith("image/"):
                    logger.warning(f"Rejected non-image portrait content-type: {content_type!r}")
                    return None
                content_length = response.headers.get("content-length")
                if (
                    content_length
                    and content_length.isdigit()
                    and int(content_length) > max_image_bytes
                ):
                    logger.warning(
                        f"Rejected oversized portrait Content-Length ({content_length} bytes)"
                    )
                    return None
                async for chunk in response.aiter_bytes():
                    image_buffer.extend(chunk)
                    if len(image_buffer) > max_image_bytes:
                        logger.warning(
                            f"Rejected oversized portrait payload (>{max_image_bytes} bytes)"
                        )
                        return None

        image_bytes = bytes(image_buffer)
        if not image_bytes or len(image_bytes) < 1024:
            return None
        if not any(
            validate_image_magic_bytes(image_bytes[:16], ext)
            for ext in (".png", ".jpg", ".webp", ".gif")
        ):
            logger.warning("Rejected portrait payload with unrecognized image magic bytes")
            return None

        # Save locally
        from backend.utils.path_safety import safe_path

        timestamp = int(time.time())
        safe_char_id = _secure_filename(char_id)
        filename = f"{safe_char_id}_{timestamp}.png" if force else f"{safe_char_id}.png"
        filepath = safe_path(os.path.join(PORTRAIT_DIR, filename), scope="portraits")

        with open(filepath, "wb") as f:
            f.write(image_bytes)

        logger.info(f"Successfully downloaded and saved portrait to {filepath}")
        return f"{base_url_path}{filename}"
    except Exception as e:
        logger.error(f"Failed to generate and download portrait: {e}")
        return None


def promote_preview_portrait(
    portrait_url: str | None, char_id: str
) -> tuple[str | None, str | None]:
    """Promotes a Forge `preview_*.png` portrait onto a character-owned filename.

    Returns `(updated_portrait_url, old_preview_filename_to_check)` when promoted,
    or `(portrait_url, None)` if no local preview file applies.
    """
    prefix = f"{settings.API_V1_STR}/portraits/preview_"
    if not isinstance(portrait_url, str) or not portrait_url.startswith(prefix) or not char_id:
        return portrait_url, None

    from backend.utils.path_safety import safe_path

    src_filename = os.path.basename(portrait_url)
    if not (src_filename.startswith("preview_") and src_filename.endswith(".png")):
        return portrait_url, None

    try:
        src_path = safe_path(os.path.join(PORTRAIT_DIR, src_filename), scope="portraits")
        if not os.path.isfile(src_path):
            return portrait_url, None

        safe_char_id = _secure_filename(char_id)
        if not safe_char_id or safe_char_id.startswith("preview_"):
            return portrait_url, None

        dest_filename = f"{safe_char_id}_{int(time.time())}.png"
        dest_path = safe_path(os.path.join(PORTRAIT_DIR, dest_filename), scope="portraits")
        shutil.copy2(src_path, dest_path)
        return f"{settings.API_V1_STR}/portraits/{dest_filename}", src_filename
    except (OSError, ValueError) as e:
        logger.warning("Failed promoting preview portrait %r: %s", portrait_url, e)
        return portrait_url, None


def prune_unreferenced_preview_portraits(
    referenced_urls: Iterable[str | None] = (),
    now: int | None = None,
    max_age_seconds: int = 86400,
) -> int:
    """Removes stale Forge preview_*.png files not referenced by any character in MongoDB."""
    from backend.utils.path_safety import safe_path

    referenced_names = {
        os.path.basename(str(url))
        for url in referenced_urls
        if isinstance(url, str) and url.strip()
    }
    cutoff = (now if now is not None else int(time.time())) - max_age_seconds
    removed = 0
    try:
        for entry in os.listdir(PORTRAIT_DIR):
            if not (entry.startswith("preview_") and entry.endswith(".png")):
                continue
            if entry in referenced_names:
                continue
            try:
                candidate = safe_path(os.path.join(PORTRAIT_DIR, entry), scope="portraits")
                if os.path.isfile(candidate) and os.path.getmtime(candidate) < cutoff:
                    os.remove(candidate)
                    removed += 1
            except (OSError, ValueError):
                pass
    except OSError:
        pass
    return removed


def _secure_filename(filename: str) -> str:
    import re

    base = os.path.basename(filename)
    # Remove any non-alphanumeric/dot/dash/underscore chars just in case
    return re.sub(r"[^a-zA-Z0-9_\.-]", "_", base)


def save_custom_portrait(image_bytes: bytes, filename: str) -> str:
    """Saves custom uploaded portrait bytes
    to data/portraits/ and returns the public API URL."""
    from backend.utils.path_safety import safe_path

    _ensure_dir()
    safe_name = _secure_filename(filename)
    filepath = safe_path(os.path.join(PORTRAIT_DIR, safe_name), scope="portraits")

    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return f"{settings.API_V1_STR}/portraits/{safe_name}"


ALLOWED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})


def validate_image_magic_bytes(header: bytes, extension: str) -> bool:
    """Verify binary file header matches the declared image extension."""
    ext = (extension or "").lower().strip()
    if ext == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if ext in (".jpg", ".jpeg"):
        return header.startswith(b"\xff\xd8\xff")
    if ext == ".gif":
        return header.startswith((b"GIF87a", b"GIF89a"))
    if ext == ".webp":
        return len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP"
    return False


async def stream_validated_image_upload(
    upload_file,
    dest_path: str,
    file_extension: str,
    max_bytes: int = 10 * 1024 * 1024,
    chunk_size: int = 1024 * 1024,
) -> int:
    """Stream an uploaded image to disk while validating magic bytes and size cap."""
    from fastapi import HTTPException, status

    if file_extension.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported image extension '{file_extension}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
            ),
        )

    total_bytes = 0
    first_chunk = True
    try:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as buffer:
            while chunk := await upload_file.read(chunk_size):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Uploaded image exceeds the 10 MB limit.",
                    )
                if first_chunk:
                    first_chunk = False
                    if not validate_image_magic_bytes(chunk, file_extension):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                f"Invalid image signature: file content does not match "
                                f"expected '{file_extension}' format."
                            ),
                        )
                buffer.write(chunk)

        if total_bytes == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded image file is empty.",
            )
        return total_bytes
    except Exception:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except OSError:
                pass
        raise
