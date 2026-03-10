"""Configuration loading with YAML support and deep merge with defaults."""

import copy
import os
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG: dict[str, Any] = {
    "paths": {
        "clippings_dir": "~/Obsidian/Clippings",
        "processed_dir": "~/Obsidian/Clippings/Processed",
    },
    "llm": {
        "provider": "ollama",
        "model": "llama3.2:3b",
        "base_url": "http://localhost:11434",
        "api_key": None,
    },
    "extraction": {
        "min_content_length": 100,
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge *override* into *base*, returning a new dict.

    Nested dicts are merged; all other values in *override* replace the
    corresponding value in *base*.
    """
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _expand_paths(config: dict[str, Any]) -> dict[str, Any]:
    """Expand ``~`` in every value under the ``paths`` section."""
    if "paths" in config:
        config["paths"] = {
            k: os.path.expanduser(v) if isinstance(v, str) else v
            for k, v in config["paths"].items()
        }
    return config


def load_config(path: str | Path = "config.yaml") -> dict[str, Any]:
    """Load configuration from a YAML file, deep-merged with defaults.

    * If the file does not exist, the built-in defaults are returned.
    * Partial YAML files are supported -- only the keys present in the file
      override the defaults; everything else keeps its default value.
    * Tilde (``~``) in path values is expanded to the user's home directory.
    """
    path = Path(path)
    user_config: dict[str, Any] = {}

    if path.is_file():
        with open(path, encoding="utf-8") as fh:
            loaded = yaml.safe_load(fh)
            if isinstance(loaded, dict):
                user_config = loaded

    merged = _deep_merge(DEFAULT_CONFIG, user_config)
    return _expand_paths(merged)
