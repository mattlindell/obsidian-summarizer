from typing import Optional

import requests

from llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str) -> None:
        self.model = model
        self.base_url = base_url

    def summarize(self, text: str, prompt: str) -> Optional[str]:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            return response.json()["response"]
        except Exception:
            return None
