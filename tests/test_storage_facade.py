from unittest.mock import patch
from backend.core.storage import (
    save_character,
    load_character,
    list_characters,
    delete_character,
    save_campaign,
    load_campaign,
    list_campaigns,
    join_campaign,
    remove_from_campaign,
)


@patch("backend.core.storage._char_repo")
def test_character_storage(mock_repo):
    mock_repo.load.return_value = {"name": "Test"}
    mock_repo.list_all.return_value = ["test.json"]
    save_character({"name": "Test"})
    mock_repo.save.assert_called_once()

    load_character("test.json")
    mock_repo.load.assert_called_once_with("test.json")

    list_characters()
    mock_repo.list_all.assert_called_once()


@patch("backend.core.storage._char_repo")
@patch("backend.core.storage.os.path.exists")
@patch("backend.core.storage.os.remove")
def test_delete_character(mock_remove, mock_exists, mock_char_repo):
    mock_exists.return_value = True
    mock_char_repo.load.return_value = {"active_campaign": "Camp1"}

    with patch("backend.core.storage.remove_from_campaign") as mock_remove_camp:
        delete_character("hero_123.json")
        mock_remove.assert_called_once()
        mock_remove_camp.assert_called_once_with("Camp1", "hero_123.json")
        mock_char_repo.delete.assert_called_once_with("hero_123.json")


@patch("backend.core.storage._get_owner_id")
@patch("backend.core.storage._camp_repo")
def test_campaign_storage(mock_repo, mock_get_id):
    # Setup mock returns
    owner_id = "owner_123"
    mock_get_id.return_value = owner_id
    mock_repo.load.return_value = {"campaign_name": "Camp1", "owner_id": owner_id}
    mock_repo.list_all.return_value = ["Camp1"]

    # 1. Test Save (Now calls load inside to preserve owner)
    save_campaign("Camp1", "Notes")
    assert mock_repo.load.call_count >= 1
    mock_repo.save.assert_called_once_with(
        "Camp1", "Notes", None, dnd_edition=None, owner_id=owner_id
    )

    # 2. Test Load
    mock_repo.load.reset_mock()
    # Ensure load_campaign succeeds by matching the owner_id
    res = load_campaign("Camp1")
    assert res is not None
    assert mock_repo.load.called

    # 3. Test List
    list_campaigns()
    mock_repo.list_all.assert_called_once()

    from backend.core.storage import delete_campaign

    # 4. Test Delete (Calls load inside to verify exists/auth)
    mock_repo.load.reset_mock()
    # Setup delete mock to return a campaign owned by us
    mock_repo.load.return_value = {
        "campaign_name": "CampToDelete",
        "owner_id": owner_id,
    }
    delete_campaign("CampToDelete")
    assert mock_repo.delete.called


@patch("backend.core.storage.load_campaign")
@patch("backend.core.storage.save_campaign")
@patch("backend.core.storage.load_character")
@patch("backend.core.storage.save_character")
def test_join_campaign(mock_save_char, mock_load_char, mock_save_camp, mock_load_camp):
    mock_load_camp.return_value = {"notes": "Some notes", "party": []}
    mock_load_char.return_value = {"char_name": "Hero"}
    mock_save_camp.return_value = True

    result = join_campaign("Camp1", "hero.json")

    assert result is True
    mock_save_camp.assert_called_once_with("Camp1", "Some notes", ["hero.json"])
    mock_save_char.assert_called_once()
    assert mock_save_char.call_args[0][0]["active_campaign"] == "Camp1"


@patch("backend.core.storage.load_campaign")
@patch("backend.core.storage.save_campaign")
@patch("backend.core.storage.load_character")
@patch("backend.core.storage.save_character")
def test_remove_from_campaign(
    mock_save_char, mock_load_char, mock_save_camp, mock_load_camp
):
    mock_load_camp.return_value = {"notes": "Some notes", "party": ["hero.json"]}
    mock_load_char.return_value = {"active_campaign": "Camp1"}
    mock_save_camp.return_value = True

    result = remove_from_campaign("Camp1", "hero.json")

    assert result is True
    mock_save_camp.assert_called_once_with("Camp1", "Some notes", [])
    mock_save_char.assert_called_once()
    assert mock_save_char.call_args[0][0]["active_campaign"] is None


@patch("backend.core.storage.load_campaign")
@patch("backend.core.storage.save_campaign")
def test_whispers_and_secret_rolls(mock_save_camp, mock_load_camp):
    from backend.core.storage import add_roll_request, send_whisper

    mock_load_camp.return_value = {
        "notes": "Some notes",
        "party": ["hero.json"],
        "roll_requests": [],
        "whispers": [],
    }
    mock_save_camp.return_value = True

    # Test add_roll_request with secret
    assert (
        add_roll_request(
            "Camp1", "hero.json", "Hero", "Stealth Check", "Stealth", is_secret=True
        )
        is True
    )
    assert mock_save_camp.called
    saved_reqs = mock_save_camp.call_args[1].get("roll_requests")
    assert saved_reqs is not None
    assert len(saved_reqs) == 1
    assert saved_reqs[0]["is_secret"] is True

    # Test send_whisper
    mock_save_camp.reset_mock()
    assert send_whisper("Camp1", "DM", "Hero", "Hello!") is True
    assert mock_save_camp.called
    saved_whispers = mock_save_camp.call_args[1].get("whispers")
    assert saved_whispers is not None
    assert len(saved_whispers) == 1
    assert saved_whispers[0]["message"] == "Hello!"

    # Test send_whisper pruning (more than 3 whispers in same channel, and whispers across different channels)
    mock_save_camp.reset_mock()
    mock_load_camp.return_value = {
        "notes": "Some notes",
        "party": ["hero.json"],
        "roll_requests": [],
        "whispers": [
            {"id": "w1", "sender": "DM", "recipient": "Hero", "message": "1"},
            {"id": "w2", "sender": "DM", "recipient": "Hero", "message": "2"},
            {"id": "w3", "sender": "DM", "recipient": "Hero", "message": "3"},
            {"id": "w4", "sender": "DM", "recipient": "Fighter", "message": "F1"},
        ],
    }
    assert send_whisper("Camp1", "DM", "Hero", "4") is True
    assert mock_save_camp.called
    saved_whispers = mock_save_camp.call_args[1].get("whispers")
    assert saved_whispers is not None
    # We should have the last 3 for Hero (w2, w3, 4) plus F1 (since Fighter is a different channel)
    assert len(saved_whispers) == 4
    messages = [w["message"] for w in saved_whispers]
    assert "1" not in messages
    assert "2" in messages
    assert "3" in messages
    assert "4" in messages
    assert "F1" in messages
