import hashlib
import threading
from typing import Any, Dict, Optional, Type

from fastapi import HTTPException
from pydantic import BaseModel

from backend.core.config_loader import get_ai_settings, get_user_api_key, provider_for_model
from backend.core.providers.anthropic_provider import AnthropicProvider
from backend.core.providers.gemini_provider import GeminiProvider
from backend.core.providers.llm_provider import LLMProvider

_provider_instance = None
_provider_lock = threading.Lock()


class RoutingProvider(LLMProvider):
    """
    Picks the provider per call from the current user's model choice.

    Text/JSON calls follow the selected model (Gemini, or Claude with the user's
    own key). File calls always use Gemini: file ids come from the Gemini Files
    API and audio transcription is Gemini-only.
    """

    def __init__(self):
        self._gemini: Optional[GeminiProvider] = None
        self._anthropic: Dict[str, AnthropicProvider] = {}
        self._lock = threading.Lock()

    @property
    def gemini(self) -> GeminiProvider:
        if self._gemini is None:
            with self._lock:
                if self._gemini is None:
                    self._gemini = GeminiProvider()
        return self._gemini

    def _anthropic_for(self, api_key: str) -> AnthropicProvider:
        cache_key = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
        with self._lock:
            if cache_key not in self._anthropic:
                self._anthropic[cache_key] = AnthropicProvider(api_key)
            return self._anthropic[cache_key]

    def _text_provider(self) -> LLMProvider:
        model = get_ai_settings().get("preferred_model")
        if provider_for_model(model) == "anthropic":
            api_key = get_user_api_key("anthropic")
            if not api_key:
                raise HTTPException(
                    status_code=400,
                    detail="Add your Anthropic API key in Settings to use Claude models.",
                )
            return self._anthropic_for(api_key)
        return self.gemini

    @property
    def client(self) -> Any:
        """Truthy when the provider serving text calls is configured (used as a readiness check)."""
        try:
            return self._text_provider().client
        except HTTPException:
            return None

    def generate_text(self, prompt: str, temperature: Optional[float] = None) -> str:
        return self._text_provider().generate_text(prompt, temperature)

    def generate_json(
        self,
        prompt: str,
        schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        return self._text_provider().generate_json(
            prompt, schema=schema, system_instruction=system_instruction, temperature=temperature
        )

    def generate_from_files(
        self, file_ids: list[str], prompt: str, temperature: Optional[float] = None
    ) -> str:
        return self.gemini.generate_from_files(file_ids, prompt, temperature)

    def upload_file(self, file_path: str) -> str:
        return self.gemini.upload_file(file_path)

    def generate_json_from_files(
        self, file_ids: list[str], prompt: str, temperature: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        return self.gemini.generate_json_from_files(file_ids, prompt, temperature)


def get_llm_provider() -> LLMProvider:
    """Factory function to get the shared, per-call routing LLM provider."""
    global _provider_instance
    if _provider_instance is None:
        with _provider_lock:
            if _provider_instance is None:
                _provider_instance = RoutingProvider()

    return _provider_instance
