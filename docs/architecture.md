# Architecture

## System Overview

```mermaid
graph TB
    subgraph "Input"
        Clipper[Obsidian Web Clipper] -->|creates .md file| ClipDir[Clippings Directory]
    end

    subgraph "Watcher"
        ClipDir -->|watchdog event| Processor[ClippingProcessor]
    end

    subgraph "Pipeline"
        Processor --> Meta[Extract Metadata]
        Meta --> Classify[URL Classifier]
        Classify -->|VIDEO| VideoExt[Video Extractor<br/>yt-dlp]
        Classify -->|ARTICLE| ArticleExt[Article Extractor<br/>BeautifulSoup]
        VideoExt --> Gate[Quality Gate]
        ArticleExt --> Gate
        Gate -->|pass| LLM[LLM Provider]
        Gate -->|fail| FailTpl[Failed Extraction Template]
        LLM --> SumTpl[Summary Template]
        LLM -->|error| FailTpl
    end

    subgraph "Output"
        SumTpl --> ProcDir[Processed Directory]
        FailTpl --> ProcDir
    end
```

## Module Dependency Graph

```mermaid
graph LR
    CW[clipping_watcher.py] --> Config[config.py]
    CW --> Classifier[extractors/classifier]
    CW --> Video[extractors/video]
    CW --> Article[extractors/article]
    CW --> QG[extractors/quality_gate]
    CW --> Factory[llm/factory]
    CW --> Jinja[templates/*.j2]

    Video --> Base[extractors/base]
    Article --> Base
    QG --> Base
    Classifier --> |ContentType| CW

    Factory --> Ollama[llm/ollama]
    Factory --> OpenAI[llm/openai_compatible]
    Ollama --> LLMBase[llm/base]
    OpenAI --> LLMBase
```

## Data Flow

### ContentResult

The `ContentResult` dataclass is the standard exchange format between extractors and the pipeline:

```python
@dataclass
class ContentResult:
    title: str = ""
    text: str = ""              # Main extracted content
    author: Optional[str] = None
    url: str = ""
    content_type: str = ""      # "video" or "article"
    extraction_succeeded: bool = False
    metadata: dict = {}         # Extra data (duration, description, etc.)
```

### Video Extraction Fallback Chain

```mermaid
graph TD
    Start[extract_video_content] --> Info[_get_video_info via yt-dlp]
    Info --> ManSubs{Manual subtitles?<br/>en, en-US, en-GB}
    ManSubs -->|yes| Download[_download_subtitle_text]
    ManSubs -->|no| AutoCaps{Auto captions?<br/>en, en-US, en-GB, en-orig}
    AutoCaps -->|yes| Download
    AutoCaps -->|no| Desc[Use video description]
    Download --> Result[ContentResult]
    Desc --> Result
    Info -->|error| Empty[Empty ContentResult]
```

### Configuration Merge

User config is deep-merged with defaults — partial configs only override specified keys:

```
DEFAULT_CONFIG          config.yaml              Merged Result
{                       {                        {
  llm: {                  llm: {                   llm: {
    provider: ollama        model: llama3.1:8b       provider: ollama    ← default
    model: llama3.2:3b    }                          model: llama3.1:8b  ← override
    base_url: ...         }                          base_url: ...       ← default
  }                                                }
}                                                }
```

## LLM Provider Interface

```mermaid
classDiagram
    class LLMProvider {
        <<abstract>>
        +summarize(text, prompt) Optional~str~
    }
    class OllamaProvider {
        -model: str
        -base_url: str
        +summarize(text, prompt) Optional~str~
    }
    class OpenAICompatibleProvider {
        -model: str
        -base_url: str
        -api_key: str
        +summarize(text, prompt) Optional~str~
    }

    LLMProvider <|-- OllamaProvider
    LLMProvider <|-- OpenAICompatibleProvider
```

New providers implement `LLMProvider.summarize()` and register in `llm/factory.py`.

## Template System

Two Jinja2 templates share common sections but differ in their primary content:

| Section | summary.md.j2 | failed_extraction.md.j2 |
|---------|---------------|-------------------------|
| Frontmatter | tags: processed | tags: needs-review |
| Primary content | AI Summary (LLM response) | Failure notice + original excerpt |
| My Notes | Prompts for manual annotation | Same |
| Dataview query | Linked projects lookup | Same |

## Error Handling Strategy

All components follow **graceful degradation**:

1. **Extractors** — return empty `ContentResult` on failure (never raise)
2. **Quality gate** — catches empty/garbage extractions before LLM
3. **LLM providers** — return `None` on failure (never raise)
4. **Pipeline** — falls back to failed extraction template if LLM fails
5. **Watcher** — catches all exceptions in `process_clipping`, logs, and continues watching
