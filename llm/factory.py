from llm.base import LLMProvider
from llm.ollama import OllamaProvider
from llm.openai_compatible import OpenAICompatibleProvider


def create_provider(config: dict) -> LLMProvider:
    provider = config["provider"]

    if provider == "ollama":
        return OllamaProvider(model=config["model"], base_url=config["base_url"])
    elif provider == "openai_compatible":
        return OpenAICompatibleProvider(
            model=config["model"],
            base_url=config["base_url"],
            api_key=config["api_key"],
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
