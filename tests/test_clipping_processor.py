"""Integration tests for ClippingProcessor pipeline."""

import os
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from extractors.base import ContentResult

SAMPLE_CLIPPING = """---
title: "Test Article Title"
source: "https://example.com/article"
author:
  - "[[Test Author]]"
published: 2026-03-10
created: 2026-03-10
description: "A test article"
tags:
  - "clippings"
---
This is the original clipping content with enough text to be useful.
"""

YOUTUBE_CLIPPING = """---
title: "Test Video Title"
source: "https://www.youtube.com/watch?v=abc123"
author:
  - "[[Video Creator]]"
published: 2026-03-10
created: 2026-03-10
tags:
  - "clippings"
---
![](https://www.youtube.com/watch?v=abc123)

Short video description.
"""


def _make_config(clippings_dir: str, processed_dir: str) -> dict:
    return {
        "paths": {"clippings_dir": clippings_dir, "processed_dir": processed_dir},
        "llm": {
            "provider": "ollama",
            "model": "test",
            "base_url": "http://localhost:11434",
            "api_key": None,
        },
        "extraction": {"min_content_length": 100},
    }


@patch("clipping_watcher.create_provider")
@patch("clipping_watcher.extract_article_content")
def test_process_article_clipping_creates_summary(
    mock_extract_article, mock_create_provider
):
    """Full pipeline: article clipping -> extraction -> LLM -> summary template."""
    mock_extract_article.return_value = ContentResult(
        title="Test Article Title",
        text="A" * 200,
        author="Test Author",
        url="https://example.com/article",
        content_type="article",
        extraction_succeeded=True,
    )

    mock_provider = MagicMock()
    mock_provider.summarize.return_value = "This is the AI summary."
    mock_create_provider.return_value = mock_provider

    with tempfile.TemporaryDirectory() as tmpdir:
        clippings_dir = os.path.join(tmpdir, "clippings")
        processed_dir = os.path.join(tmpdir, "processed")
        os.makedirs(clippings_dir)

        config = _make_config(clippings_dir, processed_dir)

        from clipping_watcher import ClippingProcessor

        processor = ClippingProcessor(config)

        clipping_path = os.path.join(clippings_dir, "test_article.md")
        with open(clipping_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_CLIPPING)

        processor.process_clipping(clipping_path)

        # Verify processed file was created
        processed_files = os.listdir(processed_dir)
        assert len(processed_files) == 1, f"Expected 1 processed file, got {processed_files}"

        processed_path = os.path.join(processed_dir, processed_files[0])
        with open(processed_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "AI Summary" in content
        assert "This is the AI summary." in content
        assert "Test Article Title" in content


@patch("clipping_watcher.create_provider")
@patch("clipping_watcher.extract_article_content")
@patch("clipping_watcher.extract_video_content")
def test_process_video_clipping_uses_video_extractor(
    mock_extract_video, mock_extract_article, mock_create_provider
):
    """Video URLs should route to extract_video_content, not article extractor."""
    mock_extract_video.return_value = ContentResult(
        title="Test Video Title",
        text="B" * 200,
        author="Video Creator",
        url="https://www.youtube.com/watch?v=abc123",
        content_type="video",
        extraction_succeeded=True,
    )

    mock_provider = MagicMock()
    mock_provider.summarize.return_value = "Video summary here."
    mock_create_provider.return_value = mock_provider

    with tempfile.TemporaryDirectory() as tmpdir:
        clippings_dir = os.path.join(tmpdir, "clippings")
        processed_dir = os.path.join(tmpdir, "processed")
        os.makedirs(clippings_dir)

        config = _make_config(clippings_dir, processed_dir)

        from clipping_watcher import ClippingProcessor

        processor = ClippingProcessor(config)

        clipping_path = os.path.join(clippings_dir, "test_video.md")
        with open(clipping_path, "w", encoding="utf-8") as f:
            f.write(YOUTUBE_CLIPPING)

        processor.process_clipping(clipping_path)

        mock_extract_video.assert_called_once()
        mock_extract_article.assert_not_called()

        # Verify processed file was created
        processed_files = os.listdir(processed_dir)
        assert len(processed_files) == 1
        processed_path = os.path.join(processed_dir, processed_files[0])
        with open(processed_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "Video summary here." in content


@patch("clipping_watcher.create_provider")
@patch("clipping_watcher.extract_article_content")
def test_failed_extraction_creates_failed_template(
    mock_extract_article, mock_create_provider
):
    """When extraction quality is too low, use the failed template with original excerpt."""
    mock_extract_article.return_value = ContentResult(
        title="Test Article Title",
        text="too short",
        author="Test Author",
        url="https://example.com/article",
        content_type="article",
        extraction_succeeded=True,
    )

    mock_provider = MagicMock()
    mock_create_provider.return_value = mock_provider

    with tempfile.TemporaryDirectory() as tmpdir:
        clippings_dir = os.path.join(tmpdir, "clippings")
        processed_dir = os.path.join(tmpdir, "processed")
        os.makedirs(clippings_dir)

        config = _make_config(clippings_dir, processed_dir)

        from clipping_watcher import ClippingProcessor

        processor = ClippingProcessor(config)

        clipping_path = os.path.join(clippings_dir, "test_fail.md")
        with open(clipping_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_CLIPPING)

        processor.process_clipping(clipping_path)

        # Verify processed file was created
        processed_files = os.listdir(processed_dir)
        assert len(processed_files) == 1

        processed_path = os.path.join(processed_dir, processed_files[0])
        with open(processed_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "could not be automatically extracted" in content
        assert "AI Summary" not in content
        # LLM should NOT have been called
        mock_provider.summarize.assert_not_called()
