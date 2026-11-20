"""Thin wrapper around the OpenAI SDK pointed at DeepInfra."""

import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEFAULT_BASE_URL = "https://api.deepinfra.com/v1/openai"
DEFAULT_MODEL = "mistralai/Mistral-Small-3.2-24B-Instruct-2506"


class DeepInfraClient:
    def __init__(self, api_key=None, base_url=None, model=None):
        api_key = api_key or os.environ.get("DEEPINFRA_API_KEY")
        if not api_key:
            raise RuntimeError(
                "DEEPINFRA_API_KEY is not set. Copy .env.example to .env and add "
                "your key, or export it in the environment."
            )
        self.base_url = base_url or os.environ.get("DEEPINFRA_BASE_URL", DEFAULT_BASE_URL)
        self.model = model or os.environ.get("DEEPINFRA_MODEL", DEFAULT_MODEL)
        self._client = OpenAI(api_key=api_key, base_url=self.base_url)

    def chat(self, messages, temperature=0.0, max_tokens=1024):
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = response.choices[0]
        usage = getattr(response, "usage", None)
        return {
            "text": choice.message.content or "",
            "finish_reason": choice.finish_reason,
            "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
        }
