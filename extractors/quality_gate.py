"""Content quality gate for extraction validation."""

from extractors.base import ContentResult


def check_content_quality(result: ContentResult, min_length: int = 100) -> bool:
    """Check if extracted content meets minimum quality threshold."""
    text = result.text.strip()
    return len(text) >= min_length
