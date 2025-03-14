import os
from typing import Dict, List, Any

from dotenv import load_dotenv
from openai import OpenAI

from biz.llm.client.base import BaseClient
from biz.llm.types import ChatChunk


class DeepSeekClient(BaseClient):
    def __init__(self, api_key: str = None):
        if not os.getenv("DEEPSEEK_API_KEY"):
            load_dotenv()
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com")
        if not self.api_key:
            raise ValueError("API key is required. Please provide it or set it in the environment variables.")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        self.default_model = os.getenv("DEEPSEEK_API_MODEL", "deepseek-chat")

    def chat(self, messages: List[Dict[str, str]], model: str = "deepseek-chat") -> str:

        completions = self.client.chat.completions.create(
            messages=messages,
            model=model,
        )
        return completions.choices[0].message.content

    def chat_stream(self, messages: List[Dict[str, str]], model: str = "deepseek-chat") -> Any:
        """Chat with the model, streaming the results."""
        completions = self.client.chat.completions.create(
            messages=messages,
            model=model,
            stream=True,
            timeout=30
        )
        return completions

    def convert_to_chunk(self, chunk) -> ChatChunk:
        if chunk.choices[0].delta.content is not None:
            content = chunk.choices[0].delta.content
            return ChatChunk(type="chunk", content=content)
        elif "stop" == chunk.choices[0].finish_reason:
            return ChatChunk(type="stop")
