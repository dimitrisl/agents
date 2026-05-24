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
