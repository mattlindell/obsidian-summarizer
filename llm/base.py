from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    @abstractmethod
    def summarize(self, text: str, prompt: str) -> Optional[str]:
        ...
