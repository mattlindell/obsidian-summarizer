from unittest.mock import patch, MagicMock

import pytest

from llm.base import LLMProvider
from llm.ollama import OllamaProvider
from llm.openai_compatible import OpenAICompatibleProvider
from llm.factory import create_provider


# --- Ollama Provider ---


def test_ollama_provider_is_llm_provider():
    provider = OllamaProvider(model="llama3", base_url="http://localhost:11434")
    assert isinstance(provider, LLMProvider)


@patch("llm.ollama.requests.post")
def test_ollama_summarize_calls_api(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "This is a summary."}
    mock_post.return_value = mock_response

    provider = OllamaProvider(model="llama3", base_url="http://localhost:11434")
    result = provider.summarize(text="some article text", prompt="Summarize this: some article text")

    assert result == "This is a summary."
    mock_post.assert_called_once_with(
        "http://localhost:11434/api/generate",
        json={"model": "llama3", "prompt": "Summarize this: some article text", "stream": False},
    )


@patch("llm.ollama.requests.post", side_effect=Exception("connection refused"))
def test_ollama_returns_none_on_failure(mock_post):
    provider = OllamaProvider(model="llama3", base_url="http://localhost:11434")
    result = provider.summarize(text="some text", prompt="Summarize this")
    assert result is None


# --- OpenAI Compatible Provider ---


def test_openai_compatible_provider_is_llm_provider():
    provider = OpenAICompatibleProvider(
        model="gpt-4", base_url="https://api.openai.com/v1", api_key="sk-test"
    )
    assert isinstance(provider, LLMProvider)


@patch("llm.openai_compatible.requests.post")
def test_openai_compatible_summarize_calls_api(mock_post):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "OpenAI summary."}}]
    }
    mock_post.return_value = mock_response

    provider = OpenAICompatibleProvider(
        model="gpt-4", base_url="https://api.openai.com/v1", api_key="sk-test"
    )
    result = provider.summarize(text="article", prompt="Summarize: article")

    assert result == "OpenAI summary."
    mock_post.assert_called_once_with(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": "Bearer sk-test", "Content-Type": "application/json"},
        json={
            "model": "gpt-4",
            "messages": [{"role": "user", "content": "Summarize: article"}],
        },
    )


# --- Factory ---


def test_factory_creates_ollama_provider():
    config = {
        "provider": "ollama",
        "model": "llama3",
        "base_url": "http://localhost:11434",
    }
    provider = create_provider(config)
    assert isinstance(provider, OllamaProvider)


def test_factory_creates_openai_compatible_provider():
    config = {
        "provider": "openai_compatible",
        "model": "gpt-4",
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-test",
    }
    provider = create_provider(config)
    assert isinstance(provider, OpenAICompatibleProvider)


def test_factory_raises_on_unknown_provider():
    config = {"provider": "unknown_llm", "model": "x", "base_url": "http://localhost"}
    with pytest.raises(ValueError, match="Unknown LLM provider: unknown_llm"):
        create_provider(config)
