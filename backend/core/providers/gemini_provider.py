import json
import logging
import os
from typing import Any, Dict, Optional, Type

from google import genai
from pydantic import BaseModel

from backend.core.config_loader import load_config
from backend.core.providers.llm_provider import LLMProvider

logger = logging.getLogger("DnDAssistant.GeminiProvider")


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            config = load_config()
            self.api_key = config.get("server", {}).get("GEMINI_API_KEY")

        if not self.api_key:
            logger.error("GEMINI_API_KEY is missing. GeminiProvider will fail to generate content.")
            self.client = None
        else:
            self.client = genai.Client(api_key=self.api_key)

    def _get_model(self, use_pro: bool = False) -> str:
        config = load_config()
        ai_settings = config.get("ai_settings", {})

        if use_pro:
            return ai_settings.get("pro_model", "gemini-2.5-pro")

        preferred = ai_settings.get("preferred_model", "gemini-2.5-flash")
        fallback = ai_settings.get("fallback_model", "gemini-2.5-flash")

        try:
            if not self.client:
                return fallback

            model_info = self.client.models.list()
            model_names = [m.name for m in model_info]

            for name in model_names:
                if preferred.lower() in name:
                    return name[7:] if name.startswith("models/") else name

            stable_default = "gemini-2.5-flash"
            for name in model_names:
                if stable_default in name:
                    return name[7:] if name.startswith("models/") else name

            return fallback[7:] if fallback.startswith("models/") else fallback
        except Exception as e:
            logger.warning(f"Failed to fetch model list, defaulting to {fallback}. Error: {e}")
            return fallback[7:] if fallback.startswith("models/") else fallback

    def generate_text(self, prompt: str, temperature: Optional[float] = None) -> str:
        if not self.client:
            return "❌ Error: GEMINI_API_KEY is missing in your .env file."

        try:
            if temperature is None:
                config = load_config()
                temperature = config.get("ai_settings", {}).get("temperature")

            model = self._get_model()
            response = self.client.models.generate_content(
                model=model,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=temperature,
                ),
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg or "high demand" in error_msg.lower():
                return "⚠️ The AI is currently experiencing high demand. Please wait a few seconds and try again."
            logger.error(f"Failed to generate response: {e}", exc_info=True)
            return f"❌ Failed to generate response: {error_msg}"

    def generate_json(
        self,
        prompt: str,
        schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        try:
            if temperature is None:
                config = load_config()
                temperature = config.get("ai_settings", {}).get("temperature")

            full_prompt = (
                prompt
                + "\n\nIMPORTANT: Return ONLY a valid JSON object. Do not include markdown blocks or any other text."
            )
            model = self._get_model()

            if system_instruction:
                full_prompt = f"{system_instruction}\n\n{full_prompt}"

            config_kwargs = {
                "response_mime_type": "application/json",
                "temperature": temperature,
            }
            if schema:
                config_kwargs["response_schema"] = schema

            response = self.client.models.generate_content(
                model=model,
                contents=full_prompt,
                config=genai.types.GenerateContentConfig(**config_kwargs),
            )

            if not response or not response.text:
                return None

            cleaned_text = response.text.strip()
            if "```json" in cleaned_text:
                cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_text:
                cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()

            return json.loads(cleaned_text)
        except Exception as e:
            logger.error(f"Failed to generate JSON from Gemini: {e}")
            return None

    def generate_from_files(
        self, file_ids: list[str], prompt: str, temperature: Optional[float] = None
    ) -> str:
        if not self.client:
            return "❌ Error: AI Client not initialized."

        try:
            contents = []
            for file_id in file_ids:
                try:
                    file_obj = self.client.files.get(name=file_id)
                    contents.append(file_obj)
                except Exception as e:
                    logger.error(f"Could not retrieve file {file_id}: {e}")

            contents.append(prompt)
            model = self._get_model(use_pro=True)

            response = self.client.models.generate_content(
                model=model,
                contents=contents,
            )
            return response.text
        except Exception as e:
            return f"❌ Failed to generate from files: {str(e)}"

    def upload_file(self, file_path: str) -> str:
        if not self.client:
            raise ValueError("Gemini Client not initialized.")
        try:
            logger.info(f"Uploading {file_path} to Gemini...")
            gemini_file = self.client.files.upload(file=file_path)
            logger.info(f"Successfully uploaded: {gemini_file.name}")
            return gemini_file.name
        except Exception as e:
            logger.error(f"Failed to upload file to Gemini: {e}")
            raise

    def generate_json_from_files(
        self, file_ids: list[str], prompt: str, temperature: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        if not self.client:
            return None

        try:
            if temperature is None:
                config = load_config()
                temperature = config.get("ai_settings", {}).get("temperature")

            contents = []
            for file_id in file_ids:
                try:
                    file_obj = self.client.files.get(name=file_id)
                    contents.append(file_obj)
                except Exception as e:
                    logger.error(f"Could not retrieve file {file_id}: {e}")

            full_prompt = (
                prompt
                + "\n\nIMPORTANT: Return ONLY a valid JSON object or array. Do not include markdown blocks or any other text."
            )
            contents.append(full_prompt)

            model = self._get_model(use_pro=True)

            response = self.client.models.generate_content(
                model=model,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=temperature,
                ),
            )

            if not response or not response.text:
                return None

            cleaned_text = response.text.strip()
            if "```json" in cleaned_text:
                cleaned_text = cleaned_text.split("```json")[1].split("```")[0].strip()
            elif "```" in cleaned_text:
                cleaned_text = cleaned_text.split("```")[1].split("```")[0].strip()

            return json.loads(cleaned_text)
        except Exception as e:
            logger.error(f"Failed to generate JSON from files: {str(e)}")
            return None
