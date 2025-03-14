from abc import abstractmethod
from typing import List, Dict, Literal, Any

from biz.llm.types import ChatChunk


class BaseClient:
    """ Base class for chat models client. """

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], model: str, temperature: float = 0.7) -> str:
        """Chat with the model."""

    @abstractmethod
    def chat_stream(self, messages: List[Dict[str, str]], model: str, temperature: float = 0.7) -> Any:
        """Chat with the model, streaming the results."""

    @abstractmethod
    def convert_to_chunk(self, chunk) -> ChatChunk:
        """Convert a chunk to a Chunk object."""
