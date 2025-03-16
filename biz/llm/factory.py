import os

from biz.llm.client.base import BaseClient
from biz.llm.client.deepseek import DeepSeekClient
from biz.llm.client.openai import OpenAIClient


class Factory:
    @staticmethod
    def getClient(provider: str = None) -> BaseClient:
        provider = provider or os.getenv("LLM_PROVIDER", "deepseek")
        chat_model_providers = {
            'openai': lambda: OpenAIClient(),
            'deepseek': lambda: DeepSeekClient(),
        }

        provider_func = chat_model_providers.get(provider)
        if provider_func:
            return provider_func()
        else:
            raise Exception(f'Unknown chat model provider: {provider}')
