"""Comprehensive unit & API tests for Issue #288: DM Story Scenes & Visual Handout Pop-ups."""

import io
from unittest.mock import AsyncMock
from urllib.parse import quote

import mongomock
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.core.constants import EDITION_2014, EDITION_2024
from backend.core.schemas import StorySceneCardSchema
from backend.services.campaign_service import delete_campaign_cascade
from backend.services.story_scene_service import (
    extract_campaign_asset_filename,
    normalize_story_cards,
)
from server.db_async import get_database
from server.dependencies.auth import get_current_user
from server.main import app
from server.routers.websocket_router import manager


class _AsyncColl:
    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, query=None, *args, **kwargs):
        return self._coll.find_one(query or {}, *args, **kwargs)

    def find(self, query=None, *args, **kwargs):
        docs = list(self._coll.find(query or {}, *args, **kwargs))

        class _Cur:
            def __init__(self, d):
                self._d = d

            def sort(self, key_or_list, direction=1):
                if isinstance(key_or_list, str):
                    self._d.sort(
                        key=lambda x: (x.get(key_or_list) is None, x.get(key_or_list)),
                        reverse=(direction < 0),
                    )
                return self

            async def to_list(self, length=None):
                return list(self._d) if length is None else list(self._d[:length])

            def __aiter__(self):
                self._it = iter(self._d)
                return self

            async def __anext__(self):
                try:
                    return next(self._it)
                except StopIteration:
                    raise StopAsyncIteration

        return _Cur(docs)

    async def count_documents(self, query=None):
        return self._coll.count_documents(query or {})

    async def insert_one(self, doc):
        return self._coll.insert_one(doc)

    async def update_one(self, query, update, upsert=False):
        r = self._coll.update_one(query, update, upsert=upsert)

        class _Res:
            matched_count = r.matched_count
            modified_count = r.modified_count

        return _Res()

    async def update_many(self, query, update):
        r = self._coll.update_many(query, update)

        class _Res:
            matched_count = r.matched_count
            modified_count = r.modified_count

        return _Res()

    async def delete_one(self, query):
        r = self._coll.delete_one(query)

        class _Res:
            deleted_count = r.deleted_count

        return _Res()

    async def delete_many(self, query):
        r = self._coll.delete_many(query)

        class _Res:
            deleted_count = r.deleted_count

        return _Res()


class _AsyncDB:
    def __init__(self, mongo_db):
        self._db = mongo_db
        self._colls = {}

    def __getitem__(self, name: str):
        if name not in self._colls:
            self._colls[name] = _AsyncColl(self._db[name])
        return self._colls[name]


class _FakeWs:
    def __init__(self):
        self.sent = []

    async def send_json(self, data):
        self.sent.append(data)


def test_story_scene_card_url_validation():
    ok_http = StorySceneCardSchema(title="Tavern", image_url="https://example.com/tavern.png")
    assert ok_http.image_url == "https://example.com/tavern.png"

    ok_asset = StorySceneCardSchema(
        title="NPC", image_url="/api/v1/campaigns/Test/assets/abc123.png"
    )
    assert ok_asset.image_url.startswith("/api/v1/campaigns/")

    for bad_url in (
        "javascript:alert(1)",
        "data:image/svg+xml;base64,PHN2Zz4=",
        "//evil.example/a.png",
        "/api/v1/campaigns/../secret.png",
        "http://?a=1",
        "https://#x",
        "/\\evil.png",
        "https://example.com/has space.png",
    ):
        with pytest.raises(ValidationError):
            StorySceneCardSchema(title="Bad", image_url=bad_url)

    # Anchored filename extraction rejects foreign hosts & strips fragments/queries
    assert (
        extract_campaign_asset_filename(
            "/api/v1/campaigns/Sunken%20Vault/assets/abc.png?v=1#top", "Sunken Vault"
        )
        == "abc.png"
    )
    assert (
        extract_campaign_asset_filename(
            "https://evil.example/api/v1/campaigns/Sunken%20Vault/assets/abc.png", "Sunken Vault"
        )
        is None
    )
    assert (
        extract_campaign_asset_filename(
            "/api/v1/campaigns/Sunken%20Vault/assets/sub/abc.png", "Sunken Vault"
        )
        is None
    )

    # Duplicate card_ids in a single payload are deduplicated cleanly
    cards = normalize_story_cards(
        [
            {"card_id": "dup-1", "title": "First", "image_url": "https://example.com/a.png"},
            {"card_id": "dup-1", "title": "Second", "image_url": "https://example.com/b.png"},
        ]
    )
    assert len({c["card_id"] for c in cards}) == 2


@pytest.mark.parametrize("edition", [EDITION_2014, EDITION_2024])
def test_story_scenes_crud_rbac_targeting_and_cleanup(edition: str, tmp_path, monkeypatch):
    monkeypatch.setattr("backend.services.story_scene_service._UPLOAD_ASSETS_DIR", str(tmp_path))
    monkeypatch.setattr("server.routers.assets_router.ASSETS_DIR", str(tmp_path))

    mock_db = _AsyncDB(mongomock.MongoClient()[f"story_288_{edition[:4]}"])
    dm_user = {"id": "dm-user", "username": "dm", "is_admin": False}
    p1_user = {"id": "p1-user", "username": "alice", "is_admin": False}
    p2_user = {"id": "p2-user", "username": "bob", "is_admin": False}
    camp_name = f"Sunken Vault {edition[:4]}"

    mock_db["campaigns"]._coll.insert_one(
        {
            "campaign_name": camp_name,
            "dm_id": "dm-user",
            "owner_id": "dm-user",
            "dnd_edition": edition,
        }
    )
    mock_db["campaign_members"]._coll.insert_many(
        [
            {"campaign_id": camp_name, "user_id": "dm-user", "role": "dm"},
            {"campaign_id": camp_name, "user_id": "p1-user", "role": "player"},
            {"campaign_id": camp_name, "user_id": "p2-user", "role": "player"},
        ]
    )
    mock_db["characters"]._coll.insert_many(
        [
            {
                "char_id": "char-1",
                "char_name": "Lyra",
                "owner_id": "p1-user",
                "active_campaign": camp_name,
                "dnd_edition": edition,
            },
            {
                "char_id": "char-2",
                "char_name": "Bram",
                "owner_id": "p2-user",
                "active_campaign": camp_name,
                "dnd_edition": edition,
            },
        ]
    )

    active_user = {"current": dm_user}
    orig = app.dependency_overrides.copy()
    app.dependency_overrides[get_database] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: active_user["current"]
    manager.active_connections.pop(camp_name, None)

    try:
        client = TestClient(app)

        # 1. DM uploads scene image (kind=scene)
        png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        up_res = client.post(
            f"/api/v1/campaigns/{camp_name}/assets",
            files={"file": ("tavern.png", io.BytesIO(png_bytes), "image/png")},
            data={"kind": "scene"},
        )
        assert up_res.status_code == 200, up_res.text
        uploaded_url = up_res.json()["url"]
        assert up_res.json()["kind"] == "scene"
        uploaded_file = tmp_path / up_res.json()["filename"]
        assert uploaded_file.exists()

        # Shared entity asset upload (to test orphan safety when deleting scene)
        up_ent = client.post(
            f"/api/v1/campaigns/{camp_name}/assets",
            files={"file": ("baron.png", io.BytesIO(png_bytes), "image/png")},
            data={"kind": "scene"},
        )
        assert up_ent.status_code == 200
        entity_url = up_ent.json()["url"]
        entity_file = tmp_path / up_ent.json()["filename"]
        mock_db["campaign_entities"]._coll.insert_one(
            {
                "campaign_name": camp_name,
                "name": "Baron",
                "type": "npc",
                "content": "Shady noble",
                "image_url": entity_url,
            }
        )

        # 2. DM creates a Story Scene with two handout cards + private notes
        create_res = client.post(
            f"/api/v1/campaigns/{camp_name}/story-scenes",
            json={
                "title": "Crimson Tavern",
                "dm_notes": "Secret cultists upstairs",
                "cards": [
                    {
                        "title": "Main Hall",
                        "image_url": uploaded_url,
                        "caption": "Smoke hangs low over the hearth.",
                        "dm_notes": "Trapdoor behind bar (DC 15).",
                    },
                    {
                        "title": "The Baron",
                        "image_url": entity_url,
                        "caption": "A scarred nobleman raises his glass.",
                        "dm_notes": "He is actually a rakshasa.",
                    },
                    {
                        "title": "Draft Empty Card",
                        "image_url": "",
                        "caption": "",
                    },
                ],
            },
        )
        assert create_res.status_code == 201, create_res.text
        scene = create_res.json()
        assert scene["title"] == "Crimson Tavern"
        assert len(scene["cards"]) == 3
        scene_id = scene["scene_id"]
        card1_id = scene["cards"][0]["card_id"]
        card2_id = scene["cards"][1]["card_id"]
        card3_id = scene["cards"][2]["card_id"]

        # 3. Players are blocked (403) from reading or mutating prepared scenes OR listing/uploading scene assets
        active_user["current"] = p1_user
        assert client.get(f"/api/v1/campaigns/{camp_name}/assets?kind=scene").status_code == 403
        assert (
            client.post(
                f"/api/v1/campaigns/{camp_name}/assets",
                files={"file": ("hack.png", io.BytesIO(png_bytes), "image/png")},
                data={"kind": "scene"},
            ).status_code
            == 403
        )
        all_assets_for_player = client.get(f"/api/v1/campaigns/{camp_name}/assets")
        assert all_assets_for_player.status_code == 200
        assert all(a.get("kind") != "scene" for a in all_assets_for_player.json())

        for method, path, body in (
            ("get", f"/api/v1/campaigns/{camp_name}/story-scenes", None),
            ("post", f"/api/v1/campaigns/{camp_name}/story-scenes", {"title": "Hack", "cards": []}),
            ("put", f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}", {"title": "Hack"}),
            ("delete", f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}", None),
            (
                "post",
                f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}/cast",
                {"card_id": card1_id, "target_mode": "all"},
            ),
            (
                "post",
                f"/api/v1/campaigns/{camp_name}/story-scenes/dismiss",
                {"target_mode": "all"},
            ),
        ):
            r = (
                getattr(client, method)(path, json=body)
                if body is not None
                else getattr(client, method)(path)
            )
            assert r.status_code == 403, (
                f"Expected 403 for player {method} {path}, got {r.status_code}"
            )

        # Verify campaign asset retrieval works for member p2_user and blocks outsiders (403)
        active_user["current"] = p2_user
        asset_res = client.get(uploaded_url)
        assert asset_res.status_code == 200
        active_user["current"] = {"id": "outsider", "username": "eve", "is_admin": False}
        assert client.get(uploaded_url).status_code == 403

        # 4. Back to DM: Register live WS sockets and test targeted vs all broadcast
        active_user["current"] = dm_user
        from server.routers.websocket_router import CampaignConnection

        dm_ws, p1_ws, p2_ws = _FakeWs(), _FakeWs(), _FakeWs()
        manager.active_connections[camp_name] = [
            CampaignConnection(websocket=dm_ws, role="dm", user_id="dm-user"),
            CampaignConnection(websocket=p1_ws, role="player", character="Lyra", user_id="p1-user"),
            CampaignConnection(websocket=p2_ws, role="player", character="Bram", user_id="p2-user"),
        ]

        # Casting a card without image returns 400
        bad_cast = client.post(
            f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}/cast",
            json={"card_id": card3_id, "target_mode": "all"},
        )
        assert bad_cast.status_code == 400

        # Targeted mode with unknown char returns 400
        bad_target = client.post(
            f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}/cast",
            json={"card_id": card1_id, "target_mode": "selected", "target_char_ids": ["nope"]},
        )
        assert bad_target.status_code == 400

        # Broadcast to ALL players — strips dm_notes completely!
        cast_all = client.post(
            f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}/cast",
            json={"card_id": card1_id, "target_mode": "all"},
        )
        assert cast_all.status_code == 200, cast_all.text
        assert len(p1_ws.sent) == 1
        assert len(p2_ws.sent) == 1
        frame = p1_ws.sent[0]
        assert frame["type"] == "scene_popup"
        assert frame["payload"]["title"] == "Main Hall"
        assert frame["payload"]["caption"] == "Smoke hangs low over the hearth."
        assert frame["payload"]["image_url"] == uploaded_url
        assert "dm_notes" not in frame["payload"]

        # Broadcast SELECTED only to char-1 (Lyra) — p2_ws receives ZERO frames!
        cast_sel = client.post(
            f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}/cast",
            json={"card_id": card2_id, "target_mode": "selected", "target_char_ids": ["char-1"]},
        )
        assert cast_sel.status_code == 200, cast_sel.text
        assert len(p1_ws.sent) == 2
        assert p1_ws.sent[1]["payload"]["title"] == "The Baron"
        assert p1_ws.sent[1]["payload"]["target_char_ids"] == ["char-1"]
        assert len(p2_ws.sent) == 1  # untouched!

        # Remote dismiss broadcast (targeted & all)
        dis_res = client.post(
            f"/api/v1/campaigns/{camp_name}/story-scenes/dismiss",
            json={"target_mode": "selected", "target_char_ids": ["char-1"]},
        )
        assert dis_res.status_code == 200
        assert len(p1_ws.sent) == 3
        assert p1_ws.sent[2]["type"] == "scene_popup_dismiss"
        assert len(p2_ws.sent) == 1

        # 5. Update scene removes card 1 -> prunes unreferenced uploaded_file,
        #    while an untracked file in data/uploads (not registered in campaign_assets) is NEVER deleted!
        untracked_file = tmp_path / "transient_session_audio.mp3"
        untracked_file.write_bytes(b"fake-audio")
        untracked_url = (
            f"/api/v1/campaigns/{quote(camp_name, safe='')}/assets/transient_session_audio.mp3"
        )
        upd_with_untracked = client.put(
            f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}",
            json={
                "cards": [
                    {
                        "card_id": card1_id,
                        "title": "Main Hall",
                        "image_url": uploaded_url,
                    },
                    {
                        "card_id": "forged-card",
                        "title": "Forged Pointer",
                        "image_url": untracked_url,
                    },
                    {
                        "card_id": card2_id,
                        "title": "The Baron",
                        "image_url": entity_url,
                    },
                ]
            },
        )
        assert upd_with_untracked.status_code == 200

        upd_res = client.put(
            f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}",
            json={
                "cards": [
                    {
                        "card_id": card2_id,
                        "title": "The Baron",
                        "image_url": entity_url,
                        "caption": "Updated caption",
                    }
                ]
            },
        )
        assert upd_res.status_code == 200
        assert not uploaded_file.exists()
        assert untracked_file.exists()
        assert entity_file.exists()

        # 6. Deleting scene must NOT delete entity_file because campaign_entities still references it!
        # Also verify max+1 ordering safety after create -> delete -> create!
        sc_extra = client.post(
            f"/api/v1/campaigns/{camp_name}/story-scenes",
            json={"title": "Second Scene", "cards": []},
        )
        assert sc_extra.status_code == 201
        assert sc_extra.json()["order"] == 1
        del_res = client.delete(f"/api/v1/campaigns/{camp_name}/story-scenes/{scene_id}")
        assert del_res.status_code == 200
        assert entity_file.exists()
        sc_after_del = client.post(
            f"/api/v1/campaigns/{camp_name}/story-scenes",
            json={"title": "Third Scene", "cards": []},
        )
        assert sc_after_del.status_code == 201
        assert sc_after_del.json()["order"] == 2
        assert (
            mock_db["campaign_story_scenes"]._coll.count_documents({"campaign_name": camp_name})
            == 2
        )
    finally:
        manager.active_connections.pop(camp_name, None)
        app.dependency_overrides = orig


@pytest.mark.anyio
async def test_delete_campaign_cascade_clears_story_scenes(monkeypatch):
    mock_db = _AsyncDB(mongomock.MongoClient()["story_cascade"])
    camp_name = "Cascade Scenes"
    mock_db["campaigns"]._coll.insert_one({"campaign_name": camp_name, "owner_id": "u1"})
    mock_db["campaign_story_scenes"]._coll.insert_one(
        {"scene_id": "sc-1", "campaign_name": camp_name, "title": "Opening", "cards": []}
    )
    mock_db["characters"]._coll.insert_one({"char_id": "c1", "active_campaign": camp_name})

    monkeypatch.setattr("backend.services.campaign_service.logger", AsyncMock())
    await delete_campaign_cascade(mock_db, camp_name, broadcast=False)
    assert mock_db["campaign_story_scenes"]._coll.count_documents({"campaign_name": camp_name}) == 0
