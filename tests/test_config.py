"""Tests for config loading module."""

import os
from pathlib import Path

import pytest
import yaml

from config import DEFAULT_CONFIG, load_config


def test_load_config_returns_defaults_when_no_file(tmp_path: Path) -> None:
    """load_config returns DEFAULT_CONFIG (with expanded paths) when file doesn't exist."""
    missing = tmp_path / "nonexistent.yaml"
    config = load_config(str(missing))

    assert config["llm"]["provider"] == "ollama"
    assert config["llm"]["model"] == "llama3.2:3b"
    assert config["llm"]["base_url"] == "http://localhost:11434"
    assert config["llm"]["api_key"] is None
    assert config["extraction"]["min_content_length"] == 100

    # Paths should be expanded (no ~ remaining)
    assert "~" not in config["paths"]["clippings_dir"]
    assert "~" not in config["paths"]["processed_dir"]


def test_load_config_reads_yaml_file(tmp_path: Path) -> None:
    """load_config reads a full YAML file and overrides all defaults."""
    yaml_content = {
        "paths": {
            "clippings_dir": "/custom/clippings",
            "processed_dir": "/custom/processed",
        },
        "llm": {
            "provider": "openai_compatible",
            "model": "gpt-4o",
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-test-key",
        },
        "extraction": {
            "min_content_length": 500,
        },
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(yaml_content))

    config = load_config(str(config_file))

    assert config["paths"]["clippings_dir"] == "/custom/clippings"
    assert config["paths"]["processed_dir"] == "/custom/processed"
    assert config["llm"]["provider"] == "openai_compatible"
    assert config["llm"]["model"] == "gpt-4o"
    assert config["llm"]["base_url"] == "https://api.openai.com/v1"
    assert config["llm"]["api_key"] == "sk-test-key"
    assert config["extraction"]["min_content_length"] == 500


def test_load_config_merges_partial_yaml_with_defaults(tmp_path: Path) -> None:
    """Partial YAML only overrides specified keys; defaults fill in the rest."""
    yaml_content = {
        "llm": {
            "model": "mistral:7b",
        },
    }
    config_file = tmp_path / "config.yaml"
    config_file.write_text(yaml.dump(yaml_content))

    config = load_config(str(config_file))

    # Overridden value
    assert config["llm"]["model"] == "mistral:7b"

    # Defaults preserved
    assert config["llm"]["provider"] == "ollama"
    assert config["llm"]["base_url"] == "http://localhost:11434"
    assert config["llm"]["api_key"] is None
    assert config["extraction"]["min_content_length"] == 100

    # Paths should be expanded defaults
    assert "~" not in config["paths"]["clippings_dir"]
    assert "~" not in config["paths"]["processed_dir"]
