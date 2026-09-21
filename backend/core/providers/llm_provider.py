from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type

from pydantic import BaseModel


class LLMProvider(ABC):
    """
    Abstract Base Class for LLM Providers.
    Ensures that any AI provider (Gemini, OpenAI, Anthropic, etc.)
    conforms to a standard interface.
    """

    @abstractmethod
    def generate_text(self, prompt: str, temperature: Optional[float] = None) -> str:
        """
        Generates standard text response from a prompt.
        """
        pass

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        schema: Optional[Type[BaseModel]] = None,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generates a structured JSON response from a prompt.
        """
        pass

    @abstractmethod
    def generate_from_files(
        self, file_ids: list[str], prompt: str, temperature: Optional[float] = None
    ) -> str:
        """
        Generates a text response using uploaded files for context.
        """
        pass

    @abstractmethod
    def upload_file(self, file_path: str) -> str:
        """
        Uploads a file to the provider's storage (if supported) and returns a file ID.
        """
        pass

    @abstractmethod
    def generate_json_from_files(
        self, file_ids: list[str], prompt: str, temperature: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generates structured JSON using uploaded files for context.
        """
        pass
