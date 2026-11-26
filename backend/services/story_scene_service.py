"""Modular business logic for DM Story Scenes & Ephemeral Player Visual Handout Pop-ups (#288)."""

import datetime
import os
import re
import uuid
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlparse

from fastapi import HTTPException, status

from backend.services.campaign_service import _maybe_await

_UPLOAD_ASSETS_DIR = os.path.join("data", "uploads")


def sanitize_story_image_url(raw_url: Optional[str]) -> str:
    """Validate and normalize an image URL for story cards.

    Permits safe app-relative paths (`/api/v1/...`, avoiding `//` protocol-relative
    URLs, backslashes, whitespace/control chars, or `..` traversal) and `http://` /
    `https://` URLs with a valid hostname. Blocks dangerous schemes (`javascript:`,
    `data:`, `file:`, empty-host `http://?a=1`, etc.).
    """
    cleaned = str(raw_url or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) > 2048:
        raise ValueError("Image URL exceeds maximum length (2048 characters).")
    if "\\" in cleaned or re.search(r"[\x00-\x1f\x7f\s]", cleaned):
        raise ValueError("Invalid characters in image URL.")

    if cleaned.startswith("/"):
        if cleaned.startswith("//") or ".." in cleaned.split("?", 1)[0]:
            raise ValueError("Invalid relative image path.")
        return cleaned

    parsed = urlparse(cleaned)
    if parsed.scheme.lower() in ("http", "https") and parsed.netloc and parsed.hostname:
        return cleaned

    raise ValueError("Image URL must be an http(s) URL or an internal campaign asset path.")


def normalize_story_cards(raw_cards: Iterable[Any]) -> List[Dict[str, Any]]:
    """Normalize cards list with unique UUID card_ids and sequential 0..n-1 ordering."""
    normalized: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    for idx, card in enumerate(raw_cards or []):
        data = card.model_dump() if hasattr(card, "model_dump") else dict(card or {})
        cid = str(data.get("card_id") or "").strip()
        if not cid or cid in seen_ids:
            cid = str(uuid.uuid4())
        seen_ids.add(cid)
        normalized.append(
            {
                "card_id": cid,
                "title": str(data.get("title") or "").strip() or f"Handout {idx + 1}",
                "image_url": sanitize_story_image_url(data.get("image_url")),
                "caption": str(data.get("caption") or "").strip(),
                "dm_notes": str(data.get("dm_notes") or ""),
                "entity_id": (str(data.get("entity_id")).strip() or None)
                if data.get("entity_id") is not None
                else None,
                "order": idx,
            }
        )
    return normalized


def extract_campaign_asset_filename(url: Optional[str], campaign_name: str) -> Optional[str]:
    """Return the uploaded filename if ``url`` is an internal campaign asset path.

    Strictly anchors to relative paths (never matching foreign ``http(s)://`` hosts),
    strips query/fragment components, and requires a single filename segment.
    """
    cleaned = str(url or "").strip()
    if not cleaned or not cleaned.startswith("/") or cleaned.startswith("//"):
        return None
    path_only = cleaned.split("#", 1)[0].split("?", 1)[0]
    encoded_name = quote(campaign_name, safe="")
    prefixes = (
        f"/api/v1/campaigns/{campaign_name}/assets/",
        f"/api/v1/campaigns/{encoded_name}/assets/",
        f"/campaigns/{campaign_name}/assets/",
        f"/campaigns/{encoded_name}/assets/",
    )
    tail: Optional[str] = None
    for prefix in prefixes:
        if path_only.startswith(prefix):
            tail = path_only[len(prefix) :]
            break
    if not tail or "/" in tail or "\\" in tail or tail in (".", ".."):
        return None
    filename = os.path.basename(tail).strip()
    if not filename or filename != tail:
        return None
    return filename


async def _find_doc(coll: Any, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Find one doc safely across Motor and lightweight async/sync test collections."""
    return await _maybe_await(coll.find_one(query))


async def cleanup_unreferenced_story_assets(
    db: Any,
    campaign_name: str,
    candidate_urls: Iterable[Optional[str]],
    *,
    exclude_scene_id: Optional[str] = None,
) -> None:
    """Remove orphaned campaign asset files removed from story scenes.

    Never deletes a file still referenced by another story scene (excluding
    ``exclude_scene_id``), a VTT scene map/token, or a World Entity image.
    """
    seen_filenames: set[str] = set()
    for url in candidate_urls or []:
        filename = extract_campaign_asset_filename(url, campaign_name)
        if not filename or filename in seen_filenames:
            continue
        seen_filenames.add(filename)

        pattern = rf"/assets/{re.escape(filename)}(?:\?|#|$)"

        # Check remaining story scenes
        story_query: Dict[str, Any] = {
            "campaign_name": campaign_name,
            "cards.image_url": {"$regex": pattern},
        }
        if exclude_scene_id:
            story_query["scene_id"] = {"$ne": exclude_scene_id}
        if await _find_doc(db["campaign_story_scenes"], story_query):
            continue

        # Check VTT scenes (maps and tokens)
        if await _find_doc(
            db["campaign_scenes"],
            {
                "campaign_name": campaign_name,
                "$or": [
                    {"grid.background_image_url": {"$regex": pattern}},
                    {"tokens.image_url": {"$regex": pattern}},
                ],
            },
        ):
            continue

        # Check World Entities vault
        if await _find_doc(
            db["campaign_entities"],
            {"campaign_name": campaign_name, "image_url": {"$regex": pattern}},
        ):
            continue

        asset_owner = await _find_doc(db["campaign_assets"], {"filename": filename})
        if (
            not asset_owner
            or asset_owner.get("campaign_name") != campaign_name
            or asset_owner.get("kind") != "scene"
        ):
            continue

        uploads_base = os.path.realpath(_UPLOAD_ASSETS_DIR)
        file_path = os.path.realpath(os.path.join(uploads_base, filename))
        if os.path.commonpath([uploads_base, file_path]) == uploads_base and os.path.exists(
            file_path
        ):
            try:
                os.remove(file_path)
            except OSError:
                pass

        await _maybe_await(
            db["campaign_assets"].delete_one({"campaign_name": campaign_name, "filename": filename})
        )


async def resolve_cast_targets(
    db: Any,
    campaign_name: str,
    target_mode: str,
    target_char_ids: Iterable[str],
) -> Tuple[List[str], List[str], List[str]]:
    """Resolve targeted party characters into verified ``(char_ids, user_ids, char_names)``.

    Raises HTTP 400 when ``target_mode == 'selected'`` resolves no valid active campaign characters,
    preventing accidental party-wide spoilers.
    """
    if target_mode != "selected":
        return [], [], []

    clean_ids = list(
        dict.fromkeys(str(cid).strip() for cid in (target_char_ids or []) if str(cid).strip())
    )
    if not clean_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Select at least one character for targeted reveal.",
        )

    cursor = db["characters"].find(
        {"active_campaign": campaign_name, "char_id": {"$in": clean_ids}}
    )
    docs = (
        await cursor.to_list(length=len(clean_ids))
        if hasattr(cursor, "to_list")
        else [d async for d in cursor]
    )

    resolved_ids: List[str] = []
    user_ids: List[str] = []
    char_names: List[str] = []
    for doc in docs:
        cid = str(doc.get("char_id") or "").strip()
        if not cid:
            continue
        resolved_ids.append(cid)
        oid = str(doc.get("owner_id") or "").strip()
        if oid and oid not in user_ids:
            user_ids.append(oid)
        cname = str(doc.get("char_name") or "").strip()
        if cname and cname not in char_names:
            char_names.append(cname)

    if not resolved_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No matching characters found in this campaign for targeted reveal.",
        )

    return resolved_ids, user_ids, char_names


def build_scene_popup_payload(
    scene: Dict[str, Any],
    card: Dict[str, Any],
    *,
    target_mode: str,
    target_char_ids: List[str],
    now: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """Build player-safe ephemeral popup payload (strips all private ``dm_notes``)."""
    sent_at = (now or datetime.datetime.now(datetime.timezone.utc)).isoformat()
    return {
        "scene_id": str(scene.get("scene_id") or ""),
        "scene_title": str(scene.get("title") or "").strip(),
        "card_id": str(card.get("card_id") or ""),
        "title": str(card.get("title") or "").strip(),
        "image_url": str(card.get("image_url") or "").strip(),
        "caption": str(card.get("caption") or "").strip(),
        "target_mode": target_mode,
        "target_char_ids": list(target_char_ids),
        "sent_at": sent_at,
    }
