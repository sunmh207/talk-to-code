import os
from typing import Dict, List, Any

from openai import OpenAI

from biz.llm.client.base import BaseClient
from biz.llm.types import ChatChunk


class OpenAIClient(BaseClient):
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API key is required. Please provide it or set it in the environment variables.")

        self.client = OpenAI(api_key=self.api_key)
        self.default_model = os.getenv("OPENAI_API_MODEL", "gpt-4o-mini")

    def chat(self, messages: List[Dict[str, str]], model: str = "gpt-4o-mini") -> str:

        completions = self.client.chat.completions.create(
            messages=messages,
            model=model,
        )
        return completions.choices[0].message.content

    def chat_stream(self, messages: List[Dict[str, str]], model: str = "gpt-4o-mini") -> Any:
        """Chat with the model, streaming the results."""
        completions = self.client.chat.completions.create(
            messages=messages,
            model=model,
            stream=True,
            timeout=10  # 10秒钟未响应，则超时
        )
        return completions

    def convert_to_chunk(self, chunk) -> ChatChunk:
        if chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            return ChatChunk(type="chunk", content=content)
        elif "stop" == chunk.choices[0].finish_reason:
            return ChatChunk(type="stop")
