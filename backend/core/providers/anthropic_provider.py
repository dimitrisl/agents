import json
import logging
from functools import lru_cache
from typing import Any, Dict, Optional, Type

import anthropic
from fastapi import HTTPException
from pydantic import BaseModel

from backend.core.config_loader import get_ai_settings
from backend.core.providers.llm_provider import LLMProvider

logger = logging.getLogger("DnDAssistant.AnthropicProvider")

MAX_TOKENS = 16000
# Opus 5.5 defaults to "medium" while Sonnet 5.5 defaults to "high"; pin one level
# so cost/latency are predictable across the Claude options in Settings.
EFFORT = "medium"
# Server-side refusal fallbacks ("default" routing) are offered on these models.
SERVER_FALLBACK_MODELS = {"claude-opus-5-5", "claude-sonnet-5-5"}
SERVER_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(LLMProvider):
    """Claude via the user's own Anthropic API key.

    Temperature is accepted for interface compatibility but not sent: current
    Claude models reject sampling parameters. File-based work (module PDFs,
    session audio) stays on Gemini, see RoutingProvider.
    """

    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)

    def _model(self) -> str:
        return get_ai_settings().get("preferred_model", "claude-sonnet-5-5")

    def _create(self, model: str, prompt: str, system: Optional[str] = None) -> str:
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": MAX_TOKENS,
            "messages": [{"role": "user", "content": prompt}],
            "output_config": {"effort": EFFORT},
        }
        if system:
            kwargs["system"] = system

        try:
            if model in SERVER_FALLBACK_MODELS:
                response = self.client.beta.messages.create(
                    betas=[SERVER_FALLBACK_BETA], fallbacks="default", **kwargs
                )
            else:
                response = self.client.messages.create(**kwargs)
        # 400 rather than 401 for a bad key: a 401 would log the user out of the app.
        except anthropic.AuthenticationError:
            raise HTTPException(
                status_code=400,
                detail="Your Anthropic API key was rejected. Update it in Settings.",
            )
        except anthropic.PermissionDeniedError:
            raise HTTPException(
                status_code=400,
                detail=f"Your Anthropic API key has no access to {model}.",
            )
        except anthropic.RateLimitError:
            raise HTTPException(
                status_code=429,
                detail="Anthropic rate limit reached. Please wait a moment and try again.",
            )
        except anthropic.APIStatusError as e:
            logger.error(f"Anthropic API error ({e.status_code}): {e.message}")
            status = 503 if e.status_code >= 500 else 502
            raise HTTPException(status_code=status, detail=f"Claude request failed: {e.message}")
        except anthropic.APIConnectionError as e:
            logger.error(f"Could not reach Anthropic API: {e}")
            raise HTTPException(status_code=503, detail="Could not reach the Anthropic API.")

        if response.stop_reason == "refusal":
            raise HTTPException(status_code=422, detail="Claude declined this request.")
        if response.stop_reason == "max_tokens":
            logger.warning(f"Claude response hit max_tokens ({MAX_TOKENS}); output is truncated.")

        return "".join(block.text for block in response.content if block.type == "text")

    def generate_text(self, prompt: str, temperature: Optional[float] = None) -> str:
        return self._generate_text_cached(prompt, self._model())

    @lru_cache(maxsize=100)
    def _generate_text_cached(self, prompt: str, model: str) -> str:
        return self._create(model, prompt)

    def generate_json(
        self,
        prompt: str,
        schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        full_prompt = (
            prompt
            + "\n\nIMPORTANT: Return ONLY a valid JSON object. Do not include markdown blocks or any other text."
        )
        if schema:
            full_prompt += "\nThe JSON must match this JSON Schema:\n" + json.dumps(
                schema.model_json_schema()
            )

        text = self._create(self._model(), full_prompt, system=system_instruction)
        cleaned_text = text.strip()
        if "```json" in cleaned_text:
            cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned_text:
            cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError as e:
            logger.error(f"JSONDecodeError parsing Claude output: {e}\nRaw Text: {cleaned_text}")
            return None

    def _files_unsupported(self):
        raise HTTPException(
            status_code=400, detail="File-based AI features run on Gemini, not Claude."
        )

    def generate_from_files(
        self, file_ids: list[str], prompt: str, temperature: Optional[float] = None
    ) -> str:
        self._files_unsupported()

    def upload_file(self, file_path: str) -> str:
        self._files_unsupported()

    def generate_json_from_files(
        self, file_ids: list[str], prompt: str, temperature: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        self._files_unsupported()
