from backend.core.providers.gemini_provider import GeminiProvider
from backend.core.providers.llm_provider import LLMProvider

_provider_instance = None


def get_llm_provider() -> LLMProvider:
    """
    Factory function to get the configured LLM provider.
    Currently defaults to Gemini, but allows easy switching based on config.
    """
    global _provider_instance
    if _provider_instance is None:
        # config = load_config()
        # In the future, this could be: provider_type = config.get("ai_settings", {}).get("provider", "gemini")
        provider_type = "gemini"

        if provider_type == "gemini":
            _provider_instance = GeminiProvider()
        else:
            raise ValueError(f"Unknown LLM provider type: {provider_type}")

    return _provider_instance
