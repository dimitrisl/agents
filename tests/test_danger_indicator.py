from unittest.mock import AsyncMock

import pytest

from backend.services.encounter_service import calculate_danger_indicator


@pytest.mark.anyio
async def test_danger_indicator_trivial():
    # 4 Level 1 Heroes
    # Easy: 100
    combatants = [
        {"is_player": True, "char_id": "c1"},
        {"is_player": True, "char_id": "c2"},
        {"is_player": True, "char_id": "c3"},
        {"is_player": True, "char_id": "c4"},
        # 1 CR 0 Enemy (10 XP)
        {"is_player": False, "max_hp": 4},
    ]

    from unittest.mock import MagicMock

    mock_db = {"characters": MagicMock()}
    mock_db["characters"].find.return_value.to_list = AsyncMock(
        return_value=[
            {"char_id": "c1", "char_level": 1},
            {"char_id": "c2", "char_level": 1},
            {"char_id": "c3", "char_level": 1},
            {"char_id": "c4", "char_level": 1},
        ]
    )

    result = await calculate_danger_indicator(combatants, mock_db)
    assert result == "Trivial"


@pytest.mark.anyio
async def test_danger_indicator_medium():
    # 4 Level 1 Heroes (Easy: 100, Medium: 200, Hard: 300)
    # 4 Goblins (CR 1/8, 25 XP each) -> Base 100 XP
    # Multiplier: 2.0 -> Adjusted 200 XP
    # Returns Medium
    combatants = [
        {"is_player": True, "char_id": "c1"},
        {"is_player": True, "char_id": "c2"},
        {"is_player": True, "char_id": "c3"},
        {"is_player": True, "char_id": "c4"},
        {"is_player": False, "max_hp": 7},  # CR 1/8
        {"is_player": False, "max_hp": 7},
        {"is_player": False, "max_hp": 7},
        {"is_player": False, "max_hp": 7},
    ]

    from unittest.mock import MagicMock

    mock_db = {"characters": MagicMock()}
    mock_db["characters"].find.return_value.to_list = AsyncMock(
        return_value=[
            {"char_id": "c1", "char_level": 1},
            {"char_id": "c2", "char_level": 1},
            {"char_id": "c3", "char_level": 1},
            {"char_id": "c4", "char_level": 1},
        ]
    )

    result = await calculate_danger_indicator(combatants, mock_db)
    assert result == "Medium"


@pytest.mark.anyio
async def test_danger_indicator_deadly():
    # 3 Level 5 Heroes (Easy: 750, Medium: 1500, Hard: 2250, Deadly: 3300)
    # 1 Dragon (Max HP: 200 -> CR 9 -> 5000 XP)
    # 3 Heroes -> Multiplier moves up one tier (1 enemy -> x1.5)
    # Adjusted XP: 7500
    combatants = [
        {"is_player": True, "char_id": "c1"},
        {"is_player": True, "char_id": "c2"},
        {"is_player": True, "char_id": "c3"},
        {"is_player": False, "max_hp": 200},
    ]

    from unittest.mock import MagicMock

    mock_db = {"characters": MagicMock()}
    mock_db["characters"].find.return_value.to_list = AsyncMock(
        return_value=[
            {"char_id": "c1", "char_level": 5},
            {"char_id": "c2", "char_level": 5},
            {"char_id": "c3", "char_level": 5},
        ]
    )

    result = await calculate_danger_indicator(combatants, mock_db)
    assert result == "Deadly"
