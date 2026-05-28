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


@patch("backend.core.storage._camp_repo")
def test_campaign_storage(mock_repo):
    save_campaign("Camp1", "Notes")
    mock_repo.save.assert_called_once_with(
        "Camp1", "Notes", None, dnd_edition=None, owner_id=None
    )

    load_campaign("Camp1")
    mock_repo.load.assert_called_once_with("Camp1")

    list_campaigns()
    mock_repo.list_all.assert_called_once()

    from backend.core.storage import delete_campaign

    delete_campaign("CampToDelete")
    mock_repo.delete.assert_called_once_with("CampToDelete")


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
