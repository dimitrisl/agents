from unittest.mock import patch
from backend.services.rules_service import compare_rules


def test_compare_rules():
    """Verify that compare_rules calls the AI with the correct prompt."""
    query = "Great Weapon Master"

    with patch("backend.services.rules_service.generate_ai_response") as mock_gen:
        mock_gen.return_value = "Comparison text"

        result = compare_rules(query)

        assert result == "Comparison text"
        mock_gen.assert_called_once()
        # Verify that the query is in the call
        args, kwargs = mock_gen.call_args
        assert query in args[0]


def test_validate_character_build():
    """Verify that validate_character_build correctly formats the prompt and returns results."""
    from backend.services.rules_service import validate_character_build
    from backend.core.state_manager import get_default_character

    char_data = get_default_character()
    char_data["background"] = "Charlatan / Mercenary"

    with patch("backend.services.rules_service.generate_ai_json") as mock_gen:
        mock_gen.return_value = {
            "is_valid": False,
            "issues": ["Invalid background"],
            "suggestions": [],
            "corrections": {"background": "Charlatan"},
        }

        result = validate_character_build(char_data)

        assert result["is_valid"] is False
        assert "Invalid background" in result["issues"]
        assert result["corrections"]["background"] == "Charlatan"
        mock_gen.assert_called_once()

        # Verify that allowed backgrounds are formatted in the prompt
        args, _ = mock_gen.call_args
        prompt_text = args[0]
        assert "Charlatan" in prompt_text
        assert "Soldier" in prompt_text
