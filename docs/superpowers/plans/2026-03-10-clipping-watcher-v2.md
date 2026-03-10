# Clipping Watcher v2 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the clipping watcher to handle video content via yt-dlp, detect extraction failures gracefully, use Jinja2 templates for output, abstract LLM providers, and externalize configuration to YAML.

**Architecture:** A pipeline-based processor with URL classification routing to specialized extractors (yt-dlp for video, BeautifulSoup for articles), a content quality gate, pluggable LLM providers behind a common interface, and Jinja2 template rendering. Configuration lives in `config.yaml`.

**Tech Stack:** Python 3.10+, yt-dlp, Jinja2, PyYAML, BeautifulSoup4, watchdog, requests

**Spec:** `docs/superpowers/specs/2026-03-10-clipping-watcher-v2-design.md`

---

## File Structure

```text
obsidian-summarizer/
  clipping_watcher.py           # Refactor: watcher loop + orchestrator only
  config.yaml                   # User config (gitignored)
  config.example.yaml           # Example config (committed)
  extractors/
    __init__.py
    base.py                     # ContentResult dataclass
    classifier.py               # URL classification (video vs article)
    video.py                    # yt-dlp transcript extraction
    article.py                  # BeautifulSoup article extraction
    quality_gate.py             # Content quality check
  llm/
    __init__.py
    base.py                     # LLMProvider abstract base class
    ollama.py                   # OllamaProvider
    openai_compatible.py        # OpenAICompatibleProvider
    factory.py                  # Create provider from config
  templates/
    summary.md.j2               # Full output with AI summary
    failed_extraction.md.j2     # Output with extraction failure note + excerpt
  tests/
    __init__.py
    test_classifier.py
    test_video_extractor.py
    test_article_extractor.py
    test_quality_gate.py
    test_llm_providers.py
    test_template_rendering.py
    test_config.py
    test_clipping_processor.py  # Integration test for the pipeline
  pyproject.toml                # Add yt-dlp, jinja2, pyyaml, pytest
```

---

## Chunk 1: Foundation — Config, Quality Gate, URL Classifier

### Task 1: Add dependencies to pyproject.toml

**Files:**

- Modify: `pyproject.toml`

- [ ] **Step 1: Update pyproject.toml with new dependencies**

```toml
[project]
name = "obsidian-summarizer"
version = "0.2.0"
description = "Watch and process Obsidian clippings"
requires-python = ">=3.10"
dependencies = [
    "beautifulsoup4",
    "requests",
    "watchdog",
    "yt-dlp",
    "jinja2",
    "pyyaml",
]

[project.optional-dependencies]
dev = [
    "pytest",
]

[project.scripts]
obsidian-summarizer = "clipping_watcher:main"
```

- [ ] **Step 2: Install dependencies**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pip install -e ".[dev]"`
Expected: All packages install successfully

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add yt-dlp, jinja2, pyyaml, pytest dependencies"
```

---

### Task 2: Config loading

**Files:**

- Create: `config.example.yaml`
- Create: `config.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write config tests**

```python
# tests/test_config.py
import os
import tempfile
import pytest
from config import load_config, DEFAULT_CONFIG


def test_load_config_returns_defaults_when_no_file():
    config = load_config("nonexistent.yaml")
    assert config["paths"]["clippings_dir"] is not None
    assert config["llm"]["provider"] == "ollama"
    assert config["extraction"]["min_content_length"] == 100


def test_load_config_reads_yaml_file():
    yaml_content = """
paths:
  clippings_dir: /tmp/clippings
  processed_dir: /tmp/processed

llm:
  provider: openai_compatible
  model: gpt-4
  base_url: https://api.openai.com/v1
  api_key: sk-test

extraction:
  min_content_length: 200
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    assert config["paths"]["clippings_dir"] == "/tmp/clippings"
    assert config["llm"]["provider"] == "openai_compatible"
    assert config["llm"]["api_key"] == "sk-test"
    assert config["extraction"]["min_content_length"] == 200


def test_load_config_merges_partial_yaml_with_defaults():
    yaml_content = """
llm:
  model: llama3.1:8b
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    # Overridden value
    assert config["llm"]["model"] == "llama3.1:8b"
    # Defaults preserved
    assert config["llm"]["provider"] == "ollama"
    assert config["extraction"]["min_content_length"] == 100
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Implement config module**

```python
# config.py
import os
import yaml


DEFAULT_CONFIG = {
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


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config(path: str = "config.yaml") -> dict:
    """Load config from YAML file, merging with defaults."""
    config = DEFAULT_CONFIG.copy()

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}
        config = _deep_merge(DEFAULT_CONFIG, user_config)

    # Expand ~ in paths
    for key in config["paths"]:
        config["paths"][key] = os.path.expanduser(config["paths"][key])

    return config
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_config.py -v`
Expected: All 3 tests PASS

- [ ] **Step 5: Create config.example.yaml**

```yaml
# config.example.yaml
paths:
  clippings_dir: ~/Obsidian/Clippings
  processed_dir: ~/Obsidian/Clippings/Processed

llm:
  provider: ollama            # "ollama" or "openai_compatible"
  model: llama3.2:3b
  base_url: http://localhost:11434
  api_key: null               # Required for openai_compatible provider

extraction:
  min_content_length: 100     # Minimum characters to consider extraction successful
```

- [ ] **Step 6: Create user config.yaml**

```yaml
# config.yaml
paths:
  clippings_dir: C:\Users\matt\Obsidian\VaultMatt\Clippings
  processed_dir: C:\Users\matt\Obsidian\VaultMatt\Clippings\Processed

llm:
  provider: ollama
  model: llama3.2:3b
  base_url: http://localhost:11434

extraction:
  min_content_length: 100
```

- [ ] **Step 7: Commit**

```bash
git add config.py config.example.yaml tests/__init__.py tests/test_config.py
git commit -m "feat: add YAML config loading with defaults and deep merge"
```

---

### Task 3: URL Classifier

**Files:**

- Create: `extractors/__init__.py`
- Create: `extractors/base.py`
- Create: `extractors/classifier.py`
- Create: `tests/test_classifier.py`

- [ ] **Step 1: Write classifier tests**

```python
# tests/test_classifier.py
from extractors.classifier import classify_url, ContentType


def test_youtube_watch_url():
    assert classify_url("https://www.youtube.com/watch?v=uC44zFz7JSM") == ContentType.VIDEO


def test_youtube_short_url():
    assert classify_url("https://youtu.be/uC44zFz7JSM") == ContentType.VIDEO


def test_youtube_shorts_url():
    assert classify_url("https://www.youtube.com/shorts/abc123") == ContentType.VIDEO


def test_vimeo_url():
    assert classify_url("https://vimeo.com/123456789") == ContentType.VIDEO


def test_dailymotion_url():
    assert classify_url("https://www.dailymotion.com/video/x8abc") == ContentType.VIDEO


def test_regular_article_url():
    assert classify_url("https://example.com/blog/my-article") == ContentType.ARTICLE


def test_github_url():
    assert classify_url("https://github.com/user/repo") == ContentType.ARTICLE


def test_empty_url():
    assert classify_url("") == ContentType.ARTICLE
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_classifier.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement base dataclass and classifier**

```python
# extractors/__init__.py
```

```python
# extractors/base.py
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ContentResult:
    """Result of content extraction from any source."""
    title: str = ""
    text: str = ""
    author: Optional[str] = None
    url: str = ""
    content_type: str = ""  # "video" or "article"
    extraction_succeeded: bool = False
    metadata: dict = field(default_factory=dict)  # Extra metadata (duration, description, etc.)
```

```python
# extractors/classifier.py
import re
from enum import Enum


class ContentType(Enum):
    VIDEO = "video"
    ARTICLE = "article"


# Patterns for known video platforms
VIDEO_PATTERNS = [
    r"(?:https?://)?(?:www\.)?youtube\.com/",
    r"(?:https?://)?youtu\.be/",
    r"(?:https?://)?(?:www\.)?vimeo\.com/",
    r"(?:https?://)?(?:www\.)?dailymotion\.com/",
    r"(?:https?://)?(?:www\.)?twitch\.tv/",
    r"(?:https?://)?(?:www\.)?bitchute\.com/",
    r"(?:https?://)?(?:www\.)?rumble\.com/",
    r"(?:https?://)?(?:www\.)?odysee\.com/",
]


def classify_url(url: str) -> ContentType:
    """Classify a URL as video or article content."""
    for pattern in VIDEO_PATTERNS:
        if re.search(pattern, url, re.IGNORECASE):
            return ContentType.VIDEO
    return ContentType.ARTICLE
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_classifier.py -v`
Expected: All 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add extractors/ tests/test_classifier.py
git commit -m "feat: add URL classifier for video vs article detection"
```

---

### Task 4: Content Quality Gate

**Files:**

- Create: `extractors/quality_gate.py`
- Create: `tests/test_quality_gate.py`

- [ ] **Step 1: Write quality gate tests**

```python
# tests/test_quality_gate.py
from extractors.quality_gate import check_content_quality
from extractors.base import ContentResult


def test_good_content_passes():
    result = ContentResult(text="A" * 150, title="Test")
    assert check_content_quality(result, min_length=100) is True


def test_short_content_fails():
    result = ContentResult(text="Too short", title="Test")
    assert check_content_quality(result, min_length=100) is False


def test_empty_content_fails():
    result = ContentResult(text="", title="Test")
    assert check_content_quality(result, min_length=100) is False


def test_whitespace_only_content_fails():
    result = ContentResult(text="   \n\t  \n   ", title="Test")
    assert check_content_quality(result, min_length=100) is False


def test_custom_threshold():
    result = ContentResult(text="Short but ok", title="Test")
    assert check_content_quality(result, min_length=5) is True


def test_exactly_at_threshold():
    result = ContentResult(text="a" * 100, title="Test")
    assert check_content_quality(result, min_length=100) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_quality_gate.py -v`
Expected: FAIL

- [ ] **Step 3: Implement quality gate**

```python
# extractors/quality_gate.py
from extractors.base import ContentResult


def check_content_quality(result: ContentResult, min_length: int = 100) -> bool:
    """Check if extracted content meets minimum quality threshold."""
    text = result.text.strip()
    return len(text) >= min_length
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_quality_gate.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add extractors/quality_gate.py tests/test_quality_gate.py
git commit -m "feat: add content quality gate for extraction validation"
```

---

## Chunk 2: Extractors — Video and Article

### Task 5: Video Extractor (yt-dlp)

**Files:**

- Create: `extractors/video.py`
- Create: `tests/test_video_extractor.py`

- [ ] **Step 1: Write video extractor tests**

Note: These tests mock yt-dlp to avoid network calls.

```python
# tests/test_video_extractor.py
from unittest.mock import patch, MagicMock
from extractors.video import extract_video_content
from extractors.base import ContentResult


def _make_yt_dlp_info(title="Test Video", uploader="Test Channel", duration=300,
                       description="A test video", subtitles=None, automatic_captions=None):
    """Helper to build a yt-dlp info_dict."""
    info = {
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "description": description,
        "subtitles": subtitles or {},
        "automatic_captions": automatic_captions or {},
    }
    return info


def test_extract_with_manual_subtitles():
    subtitle_data = [{"ext": "json3", "url": "http://example.com/subs"}]
    info = _make_yt_dlp_info(
        title="My Video",
        uploader="Creator",
        subtitles={"en": subtitle_data},
    )
    subtitle_text = "Hello world this is the transcript of the video with enough content to pass."

    with patch("extractors.video._get_video_info", return_value=info), \
         patch("extractors.video._download_subtitle_text", return_value=subtitle_text):
        result = extract_video_content("https://www.youtube.com/watch?v=abc123")

    assert isinstance(result, ContentResult)
    assert result.title == "My Video"
    assert result.author == "Creator"
    assert result.text == subtitle_text
    assert result.content_type == "video"


def test_extract_falls_back_to_auto_captions():
    auto_caption_data = [{"ext": "json3", "url": "http://example.com/auto"}]
    info = _make_yt_dlp_info(
        subtitles={},
        automatic_captions={"en": auto_caption_data},
    )
    auto_text = "Auto generated caption text that is long enough to be useful for our purposes."

    with patch("extractors.video._get_video_info", return_value=info), \
         patch("extractors.video._download_subtitle_text", return_value=auto_text):
        result = extract_video_content("https://www.youtube.com/watch?v=abc123")

    assert result.text == auto_text


def test_extract_falls_back_to_description_when_no_subs():
    description = "This is a long description of the video that contains useful information."
    info = _make_yt_dlp_info(
        description=description,
        subtitles={},
        automatic_captions={},
    )

    with patch("extractors.video._get_video_info", return_value=info):
        result = extract_video_content("https://www.youtube.com/watch?v=abc123")

    assert result.text == description


def test_extract_returns_empty_result_on_failure():
    with patch("extractors.video._get_video_info", side_effect=Exception("Network error")):
        result = extract_video_content("https://www.youtube.com/watch?v=abc123")

    assert result.text == ""
    assert result.title == ""


def test_metadata_includes_duration():
    info = _make_yt_dlp_info(duration=600)

    with patch("extractors.video._get_video_info", return_value=info), \
         patch("extractors.video._download_subtitle_text", return_value="Some transcript text"):
        result = extract_video_content("https://www.youtube.com/watch?v=abc123")

    assert result.metadata["duration"] == 600
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_video_extractor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement video extractor**

```python
# extractors/video.py
import yt_dlp
import re
from extractors.base import ContentResult


def _get_video_info(url: str) -> dict:
    """Extract video metadata using yt-dlp without downloading."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en"],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def _download_subtitle_text(subtitle_entries: list) -> str:
    """Download and extract plain text from subtitle entries."""
    # yt-dlp provides subtitle URLs; fetch the first available format
    for entry in subtitle_entries:
        ext = entry.get("ext", "")
        url = entry.get("url", "")
        if not url:
            continue

        try:
            ydl_opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Download subtitle content
                import requests
                resp = requests.get(url, timeout=10)
                resp.raise_for_status()
                text = resp.text

                # Clean subtitle formatting (remove timestamps, tags)
                # Handle SRT format
                text = re.sub(r"\d+\n\d{2}:\d{2}:\d{2}[.,]\d{3} --> \d{2}:\d{2}:\d{2}[.,]\d{3}\n", "", text)
                # Handle WebVTT/json3 tags
                text = re.sub(r"<[^>]+>", "", text)
                # Handle JSON3 format
                if ext == "json3":
                    try:
                        import json
                        data = json.loads(resp.text)
                        segments = data.get("events", [])
                        parts = []
                        for seg in segments:
                            for s in seg.get("segs", []):
                                t = s.get("utf8", "")
                                if t.strip():
                                    parts.append(t.strip())
                        text = " ".join(parts)
                    except (json.JSONDecodeError, KeyError):
                        pass

                # Clean up whitespace
                text = re.sub(r"\n+", " ", text)
                text = re.sub(r"\s+", " ", text).strip()

                if text:
                    return text
        except Exception:
            continue

    return ""


def extract_video_content(url: str) -> ContentResult:
    """Extract transcript and metadata from a video URL using yt-dlp."""
    try:
        info = _get_video_info(url)
    except Exception:
        return ContentResult(url=url, content_type="video")

    title = info.get("title", "")
    uploader = info.get("uploader", "")
    duration = info.get("duration", 0)
    description = info.get("description", "")

    # Try manual subtitles first, then auto-captions
    text = ""
    subtitles = info.get("subtitles", {})
    auto_captions = info.get("automatic_captions", {})

    for lang in ["en", "en-US", "en-GB"]:
        if lang in subtitles and subtitles[lang]:
            text = _download_subtitle_text(subtitles[lang])
            if text:
                break

    if not text:
        for lang in ["en", "en-US", "en-GB", "en-orig"]:
            if lang in auto_captions and auto_captions[lang]:
                text = _download_subtitle_text(auto_captions[lang])
                if text:
                    break

    # Fall back to description if no subtitles available
    if not text:
        text = description or ""

    return ContentResult(
        title=title,
        text=text,
        author=uploader,
        url=url,
        content_type="video",
        metadata={"duration": duration, "description": description},
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_video_extractor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add extractors/video.py tests/test_video_extractor.py
git commit -m "feat: add yt-dlp video transcript extractor"
```

---

### Task 6: Article Extractor (refactor from existing)

**Files:**

- Create: `extractors/article.py`
- Create: `tests/test_article_extractor.py`

- [ ] **Step 1: Write article extractor tests**

```python
# tests/test_article_extractor.py
from unittest.mock import patch, MagicMock
from extractors.article import extract_article_content
from extractors.base import ContentResult


SAMPLE_HTML = """
<html>
<head><title>Test Article Title</title></head>
<body>
<nav>Navigation stuff</nav>
<article>
    <p>This is the main article content with enough text to be meaningful.
    It contains multiple sentences about an interesting topic that we want
    to extract and summarize properly.</p>
    <p class="author">Jane Doe</p>
</article>
<footer>Footer stuff</footer>
</body>
</html>
"""

MINIMAL_HTML = """
<html>
<head><title>Sparse Page</title></head>
<body><p>Hi</p></body>
</html>
"""


def _mock_response(html, status=200):
    resp = MagicMock()
    resp.content = html.encode("utf-8")
    resp.status_code = status
    resp.raise_for_status = MagicMock()
    return resp


def test_extract_article_content():
    with patch("extractors.article.requests.get", return_value=_mock_response(SAMPLE_HTML)):
        result = extract_article_content("https://example.com/article")

    assert isinstance(result, ContentResult)
    assert "main article content" in result.text
    assert result.content_type == "article"


def test_extract_strips_nav_and_footer():
    with patch("extractors.article.requests.get", return_value=_mock_response(SAMPLE_HTML)):
        result = extract_article_content("https://example.com/article")

    assert "Navigation stuff" not in result.text
    assert "Footer stuff" not in result.text


def test_extract_gets_title():
    with patch("extractors.article.requests.get", return_value=_mock_response(SAMPLE_HTML)):
        result = extract_article_content("https://example.com/article")

    assert result.title == "Test Article Title"


def test_extract_returns_empty_on_failure():
    with patch("extractors.article.requests.get", side_effect=Exception("Connection error")):
        result = extract_article_content("https://example.com/fail")

    assert result.text == ""
    assert result.url == "https://example.com/fail"


def test_extract_handles_minimal_html():
    with patch("extractors.article.requests.get", return_value=_mock_response(MINIMAL_HTML)):
        result = extract_article_content("https://example.com/sparse")

    assert result.title == "Sparse Page"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_article_extractor.py -v`
Expected: FAIL

- [ ] **Step 3: Implement article extractor (refactored from clipping_watcher.py)**

```python
# extractors/article.py
import re
import requests
from bs4 import BeautifulSoup
from extractors.base import ContentResult


def extract_article_content(url: str) -> ContentResult:
    """Extract readable text from a web page using BeautifulSoup."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.content, "html.parser")

        # Remove script and style elements
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        # Try to find the main content
        content = None
        for selector in ["article", '[role="main"]', "main", ".content", "#content"]:
            content = soup.select_one(selector)
            if content:
                break

        if not content:
            content = soup.find("body")

        # Extract text
        text = ""
        if content is not None:
            text = content.get_text(strip=True, separator=" ")
            text = re.sub(r"\s+", " ", text)

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else "Untitled"

        # Extract author
        author = None
        for selector in [".author", '[rel="author"]', ".byline", ".writer"]:
            author_elem = soup.select_one(selector)
            if author_elem:
                author = author_elem.get_text().strip()
                break

        return ContentResult(
            title=title,
            text=text,
            author=author,
            url=url,
            content_type="article",
        )

    except Exception:
        return ContentResult(url=url, content_type="article")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_article_extractor.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add extractors/article.py tests/test_article_extractor.py
git commit -m "feat: refactor article extractor into extractors module"
```

---

## Chunk 3: LLM Provider Abstraction

### Task 7: LLM Provider Interface and OllamaProvider

**Files:**

- Create: `llm/__init__.py`
- Create: `llm/base.py`
- Create: `llm/ollama.py`
- Create: `llm/factory.py`
- Create: `tests/test_llm_providers.py`

- [ ] **Step 1: Write LLM provider tests**

```python
# tests/test_llm_providers.py
from unittest.mock import patch, MagicMock
import json
from llm.base import LLMProvider
from llm.ollama import OllamaProvider
from llm.openai_compatible import OpenAICompatibleProvider
from llm.factory import create_provider


def test_ollama_provider_is_llm_provider():
    provider = OllamaProvider(model="test", base_url="http://localhost:11434")
    assert isinstance(provider, LLMProvider)


def test_ollama_summarize_calls_api():
    provider = OllamaProvider(model="llama3.2:3b", base_url="http://localhost:11434")
    mock_response = MagicMock()
    mock_response.json.return_value = {"response": "This is a summary."}
    mock_response.raise_for_status = MagicMock()

    with patch("llm.ollama.requests.post", return_value=mock_response) as mock_post:
        result = provider.summarize("article text", "Summarize this")

    assert result == "This is a summary."
    mock_post.assert_called_once()
    call_json = mock_post.call_args[1]["json"]
    assert call_json["model"] == "llama3.2:3b"


def test_ollama_returns_none_on_failure():
    provider = OllamaProvider(model="test", base_url="http://localhost:11434")

    with patch("llm.ollama.requests.post", side_effect=Exception("Connection refused")):
        result = provider.summarize("text", "prompt")

    assert result is None


def test_openai_compatible_provider_is_llm_provider():
    provider = OpenAICompatibleProvider(
        model="gpt-4", base_url="https://api.openai.com/v1", api_key="sk-test"
    )
    assert isinstance(provider, LLMProvider)


def test_openai_compatible_summarize_calls_api():
    provider = OpenAICompatibleProvider(
        model="gpt-4", base_url="https://api.openai.com/v1", api_key="sk-test"
    )
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Summary from OpenAI."}}]
    }
    mock_response.raise_for_status = MagicMock()

    with patch("llm.openai_compatible.requests.post", return_value=mock_response) as mock_post:
        result = provider.summarize("article text", "Summarize this")

    assert result == "Summary from OpenAI."
    headers = mock_post.call_args[1]["headers"]
    assert "Bearer sk-test" in headers["Authorization"]


def test_factory_creates_ollama_provider():
    config = {"provider": "ollama", "model": "llama3.2:3b", "base_url": "http://localhost:11434", "api_key": None}
    provider = create_provider(config)
    assert isinstance(provider, OllamaProvider)


def test_factory_creates_openai_compatible_provider():
    config = {"provider": "openai_compatible", "model": "gpt-4", "base_url": "https://api.openai.com/v1", "api_key": "sk-test"}
    provider = create_provider(config)
    assert isinstance(provider, OpenAICompatibleProvider)


def test_factory_raises_on_unknown_provider():
    import pytest
    config = {"provider": "unknown", "model": "x", "base_url": "http://x", "api_key": None}
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_provider(config)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_llm_providers.py -v`
Expected: FAIL

- [ ] **Step 3: Implement LLM provider base, ollama, openai_compatible, and factory**

```python
# llm/__init__.py
```

```python
# llm/base.py
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def summarize(self, text: str, prompt: str) -> Optional[str]:
        """Send text to the LLM and return the summary response."""
        ...
```

```python
# llm/ollama.py
from typing import Optional
import requests
from llm.base import LLMProvider


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str):
        self.model = model
        self.base_url = base_url.rstrip("/")

    def summarize(self, text: str, prompt: str) -> Optional[str]:
        try:
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={"model": self.model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            return response.json()["response"]
        except Exception:
            return None
```

```python
# llm/openai_compatible.py
from typing import Optional
import requests
from llm.base import LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, model: str, base_url: str, api_key: str):
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def summarize(self, text: str, prompt: str) -> Optional[str]:
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception:
            return None
```

```python
# llm/factory.py
from llm.base import LLMProvider
from llm.ollama import OllamaProvider
from llm.openai_compatible import OpenAICompatibleProvider


def create_provider(config: dict) -> LLMProvider:
    """Create an LLM provider from config dict."""
    provider_type = config["provider"]

    if provider_type == "ollama":
        return OllamaProvider(model=config["model"], base_url=config["base_url"])
    elif provider_type == "openai_compatible":
        return OpenAICompatibleProvider(
            model=config["model"], base_url=config["base_url"], api_key=config["api_key"]
        )
    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_llm_providers.py -v`
Expected: All 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add llm/ tests/test_llm_providers.py
git commit -m "feat: add LLM provider abstraction with ollama and openai-compatible"
```

---

## Chunk 4: Templates and Watcher Refactor

### Task 8: Jinja2 Templates

**Files:**

- Create: `templates/summary.md.j2`
- Create: `templates/failed_extraction.md.j2`
- Create: `tests/test_template_rendering.py`

- [ ] **Step 1: Write template rendering tests**

```python
# tests/test_template_rendering.py
import os
from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def _render(template_name, **kwargs):
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(template_name)
    return template.render(**kwargs)


def test_summary_template_renders_frontmatter():
    output = _render(
        "summary.md.j2",
        title="Test Article",
        source="https://example.com",
        author="Jane Doe",
        published="2026-03-10",
        created="2026-03-10",
        llm_summary="This is the AI summary.",
    )
    assert 'title: "Test Article"' in output
    assert 'source: "https://example.com"' in output
    assert 'author: "Jane Doe"' in output
    assert "This is the AI summary." in output
    assert "AI Summary" in output


def test_summary_template_has_my_notes_section():
    output = _render(
        "summary.md.j2",
        title="Test",
        source="https://example.com",
        author="Unknown",
        published="Unknown",
        created="2026-03-10",
        llm_summary="Summary here.",
    )
    assert "## My Notes" in output
    assert "Key takeaways" in output


def test_failed_extraction_template_shows_notice():
    output = _render(
        "failed_extraction.md.j2",
        title="Failed Article",
        source="https://example.com",
        author="Unknown",
        published="Unknown",
        created="2026-03-10",
        original_excerpt="Some original clipping text here.",
    )
    assert "could not be automatically extracted" in output.lower() or "could not be automatically extracted" in output
    assert "Some original clipping text here." in output
    assert "AI Summary" not in output


def test_failed_extraction_template_has_my_notes_section():
    output = _render(
        "failed_extraction.md.j2",
        title="Failed",
        source="https://example.com",
        author="Unknown",
        published="Unknown",
        created="2026-03-10",
        original_excerpt="Excerpt.",
    )
    assert "## My Notes" in output


def test_both_templates_have_dataview_query():
    for template_name in ["summary.md.j2", "failed_extraction.md.j2"]:
        output = _render(
            template_name,
            title="Test",
            source="https://example.com",
            author="Unknown",
            published="Unknown",
            created="2026-03-10",
            llm_summary="Summary.",
            original_excerpt="Excerpt.",
        )
        assert "dataview" in output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_template_rendering.py -v`
Expected: FAIL

- [ ] **Step 3: Create summary template**

```jinja2
{# templates/summary.md.j2 #}
---
title: "{{ title }}"
source: "{{ source }}"
author: "{{ author }}"
published: "{{ published }}"
created: "{{ created }}"
tags:
  - clipping
  - resource
  - processed
---
# {{ title }}

## AI Summary

{{ llm_summary }}

## My Notes

**Key takeaways:** what are the 1-3 most important things you learned?

**Action items:** What specific actions or next steps does this inspire?

**Questions & follow-up:** what questions does this raise? What should I research next?

**Connections:** How does this relate to other things I know or are working on?

**Quality assessment:** How accurate/useful was this? Would I recommend it to others?

## Linked Projects/Domains

```dataview
list
where contains(file.outlinks, this.file.link) and (contains(file.tags, "project") or contains(file.tags, "area") or contains(file.tags, "domain"))
```

```

- [ ] **Step 4: Create failed extraction template**

```jinja2
{# templates/failed_extraction.md.j2 #}
---
title: "{{ title }}"
source: "{{ source }}"
author: "{{ author }}"
published: "{{ published }}"
created: "{{ created }}"
tags:
  - clipping
  - resource
  - needs-review
---
# {{ title }}

> **Note:** Content could not be automatically extracted for summarization. Original clipping excerpt preserved below for manual review.

## Original Clipping Excerpt

{{ original_excerpt }}

## My Notes

**Key takeaways:** what are the 1-3 most important things you learned?

**Action items:** What specific actions or next steps does this inspire?

**Questions & follow-up:** what questions does this raise? What should I research next?

**Connections:** How does this relate to other things I know or are working on?

**Quality assessment:** How accurate/useful was this? Would I recommend it to others?

## Linked Projects/Domains

```dataview
list
where contains(file.outlinks, this.file.link) and (contains(file.tags, "project") or contains(file.tags, "area") or contains(file.tags, "domain"))
```

```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_template_rendering.py -v`
Expected: All 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add templates/ tests/test_template_rendering.py
git commit -m "feat: add Jinja2 output templates for summary and failed extraction"
```

---

### Task 9: Refactor clipping_watcher.py — the main pipeline

**Files:**

- Modify: `clipping_watcher.py`
- Create: `tests/test_clipping_processor.py`

- [ ] **Step 1: Write integration tests for the pipeline**

```python
# tests/test_clipping_processor.py
import os
import tempfile
from unittest.mock import patch, MagicMock
from clipping_watcher import ClippingProcessor


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


def _make_config(clippings_dir, processed_dir):
    return {
        "paths": {"clippings_dir": clippings_dir, "processed_dir": processed_dir},
        "llm": {"provider": "ollama", "model": "test", "base_url": "http://localhost:11434", "api_key": None},
        "extraction": {"min_content_length": 100},
    }


def test_process_article_clipping_creates_summary():
    with tempfile.TemporaryDirectory() as tmpdir:
        clippings_dir = os.path.join(tmpdir, "clippings")
        processed_dir = os.path.join(tmpdir, "processed")
        os.makedirs(clippings_dir)

        clipping_path = os.path.join(clippings_dir, "test.md")
        with open(clipping_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_CLIPPING)

        config = _make_config(clippings_dir, processed_dir)
        processor = ClippingProcessor(config)

        article_text = "A" * 200  # Enough to pass quality gate

        with patch("clipping_watcher.extract_article_content") as mock_extract, \
             patch("clipping_watcher.create_provider") as mock_provider_factory:

            from extractors.base import ContentResult
            mock_extract.return_value = ContentResult(
                title="Test Article Title", text=article_text,
                author="Test Author", url="https://example.com/article",
                content_type="article",
            )
            mock_provider = MagicMock()
            mock_provider.summarize.return_value = "This is the AI summary."
            mock_provider_factory.return_value = mock_provider

            processor.process_clipping(clipping_path)

        # Check a processed file was created
        processed_files = os.listdir(processed_dir)
        assert len(processed_files) == 1
        with open(os.path.join(processed_dir, processed_files[0]), "r", encoding="utf-8") as f:
            content = f.read()
        assert "AI Summary" in content
        assert "This is the AI summary." in content


def test_process_video_clipping_uses_video_extractor():
    with tempfile.TemporaryDirectory() as tmpdir:
        clippings_dir = os.path.join(tmpdir, "clippings")
        processed_dir = os.path.join(tmpdir, "processed")
        os.makedirs(clippings_dir)

        clipping_path = os.path.join(clippings_dir, "video.md")
        with open(clipping_path, "w", encoding="utf-8") as f:
            f.write(YOUTUBE_CLIPPING)

        config = _make_config(clippings_dir, processed_dir)
        processor = ClippingProcessor(config)

        with patch("clipping_watcher.extract_video_content") as mock_video, \
             patch("clipping_watcher.create_provider") as mock_provider_factory:

            from extractors.base import ContentResult
            mock_video.return_value = ContentResult(
                title="Test Video Title", text="B" * 200,
                author="Video Creator", url="https://www.youtube.com/watch?v=abc123",
                content_type="video", metadata={"duration": 300},
            )
            mock_provider = MagicMock()
            mock_provider.summarize.return_value = "Video summary."
            mock_provider_factory.return_value = mock_provider

            processor.process_clipping(clipping_path)

        mock_video.assert_called_once()
        processed_files = os.listdir(processed_dir)
        assert len(processed_files) == 1


def test_failed_extraction_creates_failed_template():
    with tempfile.TemporaryDirectory() as tmpdir:
        clippings_dir = os.path.join(tmpdir, "clippings")
        processed_dir = os.path.join(tmpdir, "processed")
        os.makedirs(clippings_dir)

        clipping_path = os.path.join(clippings_dir, "fail.md")
        with open(clipping_path, "w", encoding="utf-8") as f:
            f.write(SAMPLE_CLIPPING)

        config = _make_config(clippings_dir, processed_dir)
        processor = ClippingProcessor(config)

        with patch("clipping_watcher.extract_article_content") as mock_extract, \
             patch("clipping_watcher.create_provider"):

            from extractors.base import ContentResult
            mock_extract.return_value = ContentResult(
                title="Test", text="too short", url="https://example.com/article",
                content_type="article",
            )

            processor.process_clipping(clipping_path)

        processed_files = os.listdir(processed_dir)
        assert len(processed_files) == 1
        with open(os.path.join(processed_dir, processed_files[0]), "r", encoding="utf-8") as f:
            content = f.read()
        assert "could not be automatically extracted" in content.lower()
        assert "AI Summary" not in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/test_clipping_processor.py -v`
Expected: FAIL

- [ ] **Step 3: Rewrite clipping_watcher.py**

```python
# clipping_watcher.py
import os
import re
import time
from datetime import datetime

from jinja2 import Environment, FileSystemLoader
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from config import load_config
from extractors.classifier import classify_url, ContentType
from extractors.video import extract_video_content
from extractors.article import extract_article_content
from extractors.quality_gate import check_content_quality
from llm.factory import create_provider


TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


class ClippingProcessor(FileSystemEventHandler):
    def __init__(self, config: dict):
        self.config = config
        self.clippings_dir = config["paths"]["clippings_dir"]
        self.processed_dir = config["paths"]["processed_dir"]
        self.min_content_length = config["extraction"]["min_content_length"]

        os.makedirs(self.processed_dir, exist_ok=True)

        self.jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
        self.llm_provider = create_provider(config["llm"])

        print(f"Watching: {self.clippings_dir}")
        print(f"Processing to: {self.processed_dir}")

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = str(event.src_path)
        if not file_path.lower().endswith(".md"):
            return

        print(f"\nNew clipping detected: {os.path.basename(file_path)}")
        time.sleep(2)
        self.process_clipping(file_path)

    def extract_metadata_from_clipping(self, file_path):
        """Extract URL, author, title, and published date from the clipping frontmatter."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            metadata = {"url": "", "author": "", "published": "", "title": "", "original_content": content}

            # Extract URL
            for pattern in [r'source:\s*"?([^"\n]+)"?', r'url:\s*"?([^"\n]+)"?', r'https?://[^\s\)]+']:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    url = matches[0].strip()
                    if url.startswith("http"):
                        metadata["url"] = url
                        break

            # Extract author
            author_match = re.search(r'author:\s*\n?\s*-?\s*"?\[\[(.+?)\]\]"?', content, re.IGNORECASE | re.MULTILINE)
            if not author_match:
                author_match = re.search(r'author:\s*"?([^"\n]+)"?', content, re.IGNORECASE)
            if author_match:
                metadata["author"] = author_match.group(1).strip()

            # Extract published date
            published_match = re.search(r'published:\s*"?([^"\n]+)"?', content, re.IGNORECASE)
            if published_match:
                metadata["published"] = published_match.group(1).strip()

            # Extract title
            title_match = re.search(r'title:\s*"?([^"\n]+)"?', content, re.IGNORECASE)
            if title_match:
                metadata["title"] = title_match.group(1).strip().strip('"')

            if not metadata["url"]:
                print("No URL found in clipping")
                return None

            return metadata

        except Exception as e:
            print(f"Error reading clipping file: {e}")
            return None

    def _get_original_excerpt(self, content: str, max_length: int = 1000) -> str:
        """Extract an excerpt from the original clipping, skipping frontmatter."""
        # Remove YAML frontmatter
        frontmatter_match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
        body = content[frontmatter_match.end():] if frontmatter_match else content
        body = body.strip()
        if len(body) > max_length:
            body = body[:max_length] + "\n\n*[Excerpt truncated]*"
        return body

    def process_clipping(self, file_path):
        """Process a single clipping file through the extraction pipeline."""
        try:
            clipping_metadata = self.extract_metadata_from_clipping(file_path)
            if not clipping_metadata:
                print("Skipping - no URL found")
                return

            url = clipping_metadata["url"]
            print(f"Processing URL: {url}")

            # Classify URL and route to extractor
            content_type = classify_url(url)

            if content_type == ContentType.VIDEO:
                print("Detected video content, using yt-dlp...")
                result = extract_video_content(url)
            else:
                print("Detected article content, using BeautifulSoup...")
                result = extract_article_content(url)

            # Use clipping metadata as fallback
            title = clipping_metadata.get("title") or result.title
            author = clipping_metadata.get("author") or result.author or "Unknown"
            published = clipping_metadata.get("published") or "Unknown"
            created = datetime.now().strftime("%Y-%m-%d")

            # Quality gate
            extraction_ok = check_content_quality(result, self.min_content_length)

            if extraction_ok:
                # Summarize with LLM
                prompt = f"""Please analyze this content and provide a structured summary.

Title: {title}
URL: {url}
Content: {result.text[:4000]}

Please respond in this exact format:

**SUMMARY:**
[Provide a concise 2-3 sentence summary of the main points]

**KEY CONCEPTS:**
- [Key concept 1]
- [Key concept 2]
- [Key concept 3]

**SUGGESTED CATEGORY:**
[Suggest whether this belongs in: Attention Deficit Disorder, Home Automation, AI and LLMs, Servers and Infrastructure, Development, Management, Operating Systems, Jeep, Dog, Design, or Other]
"""
                print("Sending to LLM for processing...")
                llm_summary = self.llm_provider.summarize(result.text, prompt)

                if llm_summary:
                    template = self.jinja_env.get_template("summary.md.j2")
                    output = template.render(
                        title=title, source=url, author=author,
                        published=published, created=created,
                        llm_summary=llm_summary,
                    )
                else:
                    print("LLM failed, falling back to failed extraction template")
                    extraction_ok = False

            if not extraction_ok:
                original_excerpt = self._get_original_excerpt(clipping_metadata["original_content"])
                template = self.jinja_env.get_template("failed_extraction.md.j2")
                output = template.render(
                    title=title, source=url, author=author,
                    published=published, created=created,
                    original_excerpt=original_excerpt,
                )

            # Save processed file
            safe_title = re.sub(r'[<>:"/\\|?*]', "", title)[:50]
            processed_filename = f"{safe_title}_{datetime.now().strftime('%Y%m%d')}.md"
            processed_path = os.path.join(self.processed_dir, processed_filename)

            with open(processed_path, "w", encoding="utf-8") as f:
                f.write(output)

            print(f"Processed and saved: {processed_filename}")

        except Exception as e:
            print(f"Error processing clipping: {e}")


def main():
    config = load_config()

    clippings_dir = config["paths"]["clippings_dir"]
    if not os.path.exists(clippings_dir):
        print(f"Error: Clippings directory not found: {clippings_dir}")
        print("Please update config.yaml")
        return

    processor = ClippingProcessor(config)
    observer = Observer()
    observer.schedule(processor, clippings_dir, recursive=False)

    observer.start()
    print(f"\nFolder watcher started!")
    print("Waiting for new clippings...")
    print("Press Ctrl+C to stop")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopping folder watcher...")

    observer.join()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all tests**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add clipping_watcher.py tests/test_clipping_processor.py
git commit -m "feat: refactor watcher with pipeline architecture, templates, and config"
```

---

### Task 10: Add .gitignore and clean up

**Files:**

- Create: `.gitignore`
- Remove: `test_article_processor.py` (superseded by new test suite)

- [ ] **Step 1: Create .gitignore**

```gitignore
# .gitignore
config.yaml
.venv/
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
```

- [ ] **Step 2: Run full test suite one final time**

Run: `cd C:/Users/matt/Documents/Personal/obsidian-summarizer && .venv/Scripts/python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: add .gitignore, clean up project structure"
```
