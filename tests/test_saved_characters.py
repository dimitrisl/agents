import os
import pytest
from backend.repositories.character_repository import CharacterRepository
from backend.core.state_manager import update_session_from_dict


def test_load_all_real_database_characters():
    """
    Test that loads every real character currently stored in the MongoDB database
    and verifies that they can be parsed and updated into the session state
    without raising any exceptions.
    """
    # Only run if MONGO_URI is defined
    if not os.environ.get("MONGO_URI"):
        pytest.skip(
            "MONGO_URI is not set in environment. Skipping live character verification."
        )

    repo = CharacterRepository()
    if repo.collection is None:
        pytest.skip(
            "Unable to connect to MongoDB collection. Skipping live character verification."
        )

    character_files = repo.list_all()
    if not character_files:
        pytest.skip("No characters found in the live database to test.")

    for char_file in character_files:
        char_data = repo.load(char_file)
        assert char_data is not None, f"Failed to load character data from: {char_file}"

        # Initialize mock state dict
        mock_state = {}

        # This should execute without throwing exceptions (e.g. StreamlitAPIException, KeyError, etc.)
        try:
            update_session_from_dict(mock_state, char_data)
        except Exception as e:
            pytest.fail(
                f"Failed to load character '{char_file}' into session state: {e}"
            )
