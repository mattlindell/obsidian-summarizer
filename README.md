# Obsidian Summarizer

A file watcher that automatically processes [Obsidian](https://obsidian.md) web clippings — extracts content from URLs, sends it through an LLM for summarization, and outputs structured markdown notes.

Handles **articles** (via BeautifulSoup) and **video platforms** (via yt-dlp transcript extraction) including YouTube, Vimeo, Dailymotion, and more. When content can't be extracted, it preserves the original clipping instead of hallucinating a summary.

## Features

- **Video transcript extraction** — pulls subtitles/captions from YouTube and other platforms via yt-dlp
- **Article scraping** — extracts readable text from web pages with BeautifulSoup
- **Content quality gate** — detects when extraction fails and skips LLM summarization
- **Pluggable LLM providers** — supports local Ollama or any OpenAI-compatible API (Claude, GPT, etc.)
- **Jinja2 templates** — customizable output format
- **YAML configuration** — all settings externalized to `config.yaml`

## How It Works

```text
New clipping appears in watched folder
  → Extract URL from frontmatter
  → Classify URL (video platform or article?)
  → Route to appropriate extractor:
      Video  → yt-dlp (subtitles/transcript + metadata)
      Article → BeautifulSoup (HTML scraping)
  → Content quality gate (enough text extracted?)
      Pass → Send to LLM for summary → Output with AI Summary
      Fail → Preserve original clipping excerpt → Output with review notice
  → Save processed file
```

## Prerequisites

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- An LLM provider — either:
  - [Ollama](https://ollama.com/) running locally (default)
  - Any OpenAI-compatible API endpoint

## Installation

```bash
git clone https://github.com/yourusername/obsidian-summarizer.git
cd obsidian-summarizer

# Install dependencies
uv sync

# Install dev dependencies (for testing)
uv sync --group dev
```

## Configuration

Copy the example config and customize:

```bash
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

```yaml
paths:
  clippings_dir: ~/Obsidian/MyVault/Clippings
  processed_dir: ~/Obsidian/MyVault/Clippings/Processed

llm:
  provider: ollama              # "ollama" or "openai_compatible"
  model: llama3.2:3b
  base_url: http://localhost:11434
  api_key: null                 # Required for openai_compatible provider

extraction:
  min_content_length: 100       # Minimum characters to consider extraction successful
```

### LLM Provider Options

**Ollama (local, default):**

```yaml
llm:
  provider: ollama
  model: llama3.2:3b
  base_url: http://localhost:11434
```

**OpenAI-compatible API (Claude, GPT, etc.):**

```yaml
llm:
  provider: openai_compatible
  model: claude-sonnet-4-20250514
  base_url: https://api.anthropic.com/v1
  api_key: sk-ant-your-key-here
```

## Usage

Start the watcher:

```bash
uv run python clipping_watcher.py
```

The watcher monitors your clippings directory for new `.md` files. When a clipping appears (e.g., from the Obsidian Web Clipper browser extension), it automatically processes it and saves the result to the processed directory.

### Input Format

The watcher expects Obsidian web clippings with YAML frontmatter:

```markdown
---
title: "Article Title"
source: "https://example.com/article"
author:
  - "[[Author Name]]"
published: 2026-03-10
---
Original clipping content...
```

### Output Format

**Successful extraction** — includes AI summary:

```markdown
---
title: "Article Title"
source: "https://example.com/article"
author: "Author Name"
tags:
  - clipping
  - resource
  - processed
---
# Article Title

## AI Summary

**SUMMARY:** ...
**KEY CONCEPTS:** ...
**SUGGESTED CATEGORY:** ...

## My Notes
...
```

**Failed extraction** — preserves original content:

```markdown
---
tags:
  - clipping
  - resource
  - needs-review
---
# Article Title

> **Note:** Content could not be automatically extracted for summarization.

## Original Clipping Excerpt
...
```

## Supported Video Platforms

Any platform supported by [yt-dlp](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md), including:

- YouTube (watch, shorts, short URLs)
- Vimeo
- Dailymotion
- Twitch
- Rumble
- Odysee
- BitChute

The extractor tries manual subtitles first, then auto-generated captions, then falls back to the video description.

## Customizing Templates

Output templates are Jinja2 files in the `templates/` directory:

- `summary.md.j2` — used when extraction + summarization succeeds
- `failed_extraction.md.j2` — used when extraction fails the quality gate

Available template variables:

| Variable           | Description                                   |
| ------------------ | --------------------------------------------- |
| `title`            | Content title                                 |
| `source`           | Original URL                                  |
| `author`           | Author name                                   |
| `published`        | Publication date                              |
| `created`          | Processing date                               |
| `llm_summary`      | LLM response (summary template only)          |
| `original_excerpt` | Original clipping text (failed template only) |

## Project Structure

```text
obsidian-summarizer/
├── clipping_watcher.py      # Main watcher and processing pipeline
├── config.py                # YAML config loading with defaults
├── config.example.yaml      # Example configuration
├── extractors/
│   ├── base.py              # ContentResult dataclass
│   ├── classifier.py        # URL classification (video vs article)
│   ├── video.py             # yt-dlp transcript extraction
│   ├── article.py           # BeautifulSoup web scraping
│   └── quality_gate.py      # Content quality validation
├── llm/
│   ├── base.py              # LLMProvider abstract base class
│   ├── ollama.py            # Ollama provider
│   ├── openai_compatible.py # OpenAI-compatible provider
│   └── factory.py           # Provider factory
└── templates/
    ├── summary.md.j2        # Successful extraction template
    └── failed_extraction.md.j2  # Failed extraction template
```

## Testing

```bash
uv run python -m pytest tests/ -v
```

All external calls (HTTP requests, yt-dlp, LLM APIs) are mocked in tests.

## Adding a New LLM Provider

1. Create a new file in `llm/` that implements `LLMProvider`:

```python
from llm.base import LLMProvider

class MyProvider(LLMProvider):
    def __init__(self, model: str, base_url: str, **kwargs):
        self.model = model
        self.base_url = base_url

    def summarize(self, text: str, prompt: str) -> str | None:
        # Your implementation here
        ...
```

2. Register it in `llm/factory.py`:

```python
from llm.my_provider import MyProvider

def create_provider(config: dict) -> LLMProvider:
    provider_type = config["provider"]
    if provider_type == "my_provider":
        return MyProvider(model=config["model"], base_url=config["base_url"])
    ...
```

3. Use it in `config.yaml`:

```yaml
llm:
  provider: my_provider
  model: my-model
  base_url: http://localhost:8080
```

## License

MIT
