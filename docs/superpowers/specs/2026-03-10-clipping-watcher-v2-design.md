# Clipping Watcher v2 Design

## Problem

The current clipping watcher fails on video content (YouTube, Vimeo, etc.) because BeautifulSoup scrapes HTML page chrome instead of actual content. Ollama then fabricates summaries from the title alone. Some article sites also fail due to paywalls, JS rendering, or poor structure. Additionally, the output format is hardcoded and the configuration (paths, LLM settings) is not externalizable for sharing.

## Goals

1. Reliably extract content from video platforms via subtitles/transcripts
2. Detect when content extraction fails and handle gracefully instead of hallucinating
3. Externalize output formats into Jinja2 templates
4. Abstract LLM provider so users can choose local or cloud services
5. Move all configuration into a YAML config file

## Architecture

### Content Pipeline

```text
New clipping
  -> extract metadata from frontmatter
  -> classify URL (video platform vs article)
  -> route to extractor:
       video  -> yt-dlp (subtitles/transcript + metadata)
       article -> BeautifulSoup (existing scraper)
  -> content quality gate (min ~100 meaningful characters)
  -> route to output:
       pass -> LLM summarization -> summary template
       fail -> original clipping excerpt -> failed extraction template
  -> write processed file
```

### URL Classifier

Regex-based detection for video platforms. Anything yt-dlp supports (YouTube, Vimeo, Dailymotion, etc.) routes to the video extractor. Everything else routes to BeautifulSoup.

### Video Extractor (yt-dlp)

Pulls subtitles/transcript text plus metadata (title, uploader, duration, description). Prefers manual captions over auto-generated. Falls back to auto-generated if manual unavailable.

### Article Extractor (BeautifulSoup)

Existing scraper, unchanged. Strips scripts/styles/nav/footer, finds main content area, extracts text.

### Content Quality Gate

Checks if extracted text meets a minimum threshold (configurable, default 100 characters). If below threshold, extraction is considered failed.

### LLM Provider Abstraction

Base interface with a `summarize(text, prompt) -> str` method. Two built-in providers:

- **OllamaProvider** — local ollama instance (default)
- **OpenAICompatibleProvider** — works with Claude API, OpenAI, or any OpenAI-compatible endpoint via base URL + API key

### Jinja2 Templates (`templates/`)

- **`summary.md.j2`** — full output with AI Summary section (successful extraction)
- **`failed_extraction.md.j2`** — metadata + failure note + original clipping excerpt (failed extraction)

Both templates share: YAML frontmatter, My Notes prompts, Linked Projects/Domains dataview query. The difference is the middle content section.

### Configuration (`config.yaml`)

```yaml
paths:
  clippings_dir: ~/Obsidian/VaultMatt/Clippings
  processed_dir: ~/Obsidian/VaultMatt/Clippings/Processed

llm:
  provider: ollama
  model: llama3.2:3b
  base_url: http://localhost:11434
  api_key: null

extraction:
  min_content_length: 100
```

A `config.example.yaml` ships with the repo. Users copy and customize.

## File Structure

```text
obsidian-summarizer/
  clipping_watcher.py          # refactored: classifier, extractors, quality gate, template rendering
  config.yaml                  # user config (gitignored)
  config.example.yaml          # example config (committed)
  templates/
    summary.md.j2
    failed_extraction.md.j2
  test_article_processor.py    # existing, update as needed
  pyproject.toml               # add yt-dlp, jinja2, pyyaml
```

## Dependencies

Add to pyproject.toml:

- `yt-dlp` — video platform transcript/subtitle extraction
- `jinja2` — template rendering
- `pyyaml` — config file parsing

## What Stays the Same

- Watchdog file watcher loop
- Processed filename convention (`{safe_title}_{date}.md`)
- Frontmatter structure (title, source, author, published, created, tags)
- My Notes section prompts
- Linked Projects/Domains dataview query

## Failed Extraction Output

When content extraction fails, the processed file:

1. Omits the AI Summary section entirely
2. Includes a note at the top: "Content could not be automatically extracted for summarization."
3. Preserves an excerpt from the original clipping markdown for manual review

## Out of Scope

- Whisper/audio transcription (future, when Jetson is running)
- Playwright fallback for JS-heavy sites (potential future addition)
- Custom LLM prompt configuration (use defaults for now)
