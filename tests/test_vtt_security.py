"""Regression tests for the VTT hardening.

Covers atomic token updates, campaigns stored with `vtt_state: null`, hidden
tokens never reaching players, and the asset endpoint refusing path traversal.
"""

import asyncio

import mongomock
import pytest
from fastapi import HTTPException

from backend.core.schemas import VTTStateSchema, VTTTokenSchema
from backend.services.vtt_service import VTTService
from server.routers.assets_router import get_asset

CAMPAIGN = "The Obsidian Citadel"


class _AsyncCollection:
    """Minimal async facade over a mongomock collection."""

    def __init__(self, coll):
        self._coll = coll

    async def find_one(self, *args, **kwargs):
        return self._coll.find_one(*args, **kwargs)

    async def update_one(self, *args, **kwargs):
        return self._coll.update_one(*args, **kwargs)


class _AsyncDB:
    def __init__(self):
        self.campaigns = _AsyncCollection(mongomock.MongoClient().db.campaigns)


@pytest.fixture
def db():
    database = _AsyncDB()
    # Exactly what POST /campaigns stores for a fresh campaign.
    database.campaigns._coll.insert_one({"campaign_name": CAMPAIGN, "vtt_state": None})
    return database


def _token(token_id, name=None, **extra):
    return {"id": token_id, "name": name or token_id, **extra}


def test_first_write_works_on_a_campaign_with_null_vtt_state(db):
    state = asyncio.run(VTTService().add_token(db, CAMPAIGN, _token("goblin")))
    assert [t.id for t in state.tokens] == ["goblin"]


def test_adding_the_same_token_twice_replaces_instead_of_duplicating(db):
    service = VTTService()
    asyncio.run(service.add_token(db, CAMPAIGN, _token("goblin", x=1)))
    state = asyncio.run(service.add_token(db, CAMPAIGN, _token("goblin", x=7)))
    assert len(state.tokens) == 1
    assert state.tokens[0].x == 7


def test_adds_and_removes_do_not_clobber_each_other(db):
    service = VTTService()
    asyncio.run(service.add_token(db, CAMPAIGN, _token("a")))
    asyncio.run(service.add_token(db, CAMPAIGN, _token("b")))
    state = asyncio.run(service.remove_token(db, CAMPAIGN, "a"))
    assert [t.id for t in state.tokens] == ["b"]


def test_grid_update_only_touches_sent_fields_and_ignores_unknown_ones(db):
    service = VTTService()
    state = asyncio.run(service.update_grid(db, CAMPAIGN, {"cell_size": 70, "evil": 1}))
    assert state.grid.cell_size == 70
    assert state.grid.width == 30  # untouched default


def test_toggle_vtt(db):
    state = asyncio.run(VTTService().toggle_vtt(db, CAMPAIGN, True))
    assert state.is_active is True


def test_a_player_can_only_move_their_own_token(db):
    service = VTTService()
    asyncio.run(service.add_token(db, CAMPAIGN, _token("lyra", "Lyra", x=0, y=0)))
    asyncio.run(service.add_token(db, CAMPAIGN, _token("orc", "Orc", x=0, y=0)))

    state = asyncio.run(service.move_token(db, CAMPAIGN, "orc", 5, 5, "player", "Lyra"))
    assert {t.id: (t.x, t.y) for t in state.tokens}["orc"] == (0, 0)

    state = asyncio.run(service.move_token(db, CAMPAIGN, "lyra", 5, 5, "player", "Lyra"))
    assert {t.id: (t.x, t.y) for t in state.tokens}["lyra"] == (5, 5)


def test_redaction_removes_hidden_tokens_without_mutating_the_original():
    state = VTTStateSchema(
        tokens=[
            VTTTokenSchema(id="seen", name="Seen"),
            VTTTokenSchema(id="ambush", name="Ambush", is_hidden=True),
        ]
    )
    redacted = VTTService.redact_for_player(state)
    assert [t.id for t in redacted.tokens] == ["seen"]
    assert [t.id for t in state.tokens] == ["seen", "ambush"]


@pytest.mark.parametrize("filename", ["../../etc/passwd", "../uploads_evil/x.png", "/etc/passwd"])
def test_asset_endpoint_refuses_path_traversal(filename):
    with pytest.raises(HTTPException) as exc:
        asyncio.run(get_asset(CAMPAIGN, filename, db=None, campaign_member={}))
    assert exc.value.status_code == 400
