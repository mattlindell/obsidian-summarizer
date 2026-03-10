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
    metadata: dict = field(default_factory=dict)
