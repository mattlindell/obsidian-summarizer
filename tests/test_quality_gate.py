"""Tests for content quality gate."""

from extractors.base import ContentResult
from extractors.quality_gate import check_content_quality


def test_good_content_passes() -> None:
    """Content with 150 chars should pass a threshold of 100."""
    result = ContentResult(text="a" * 150)
    assert check_content_quality(result, min_length=100) is True


def test_short_content_fails() -> None:
    """Short content should fail the default threshold of 100."""
    result = ContentResult(text="Too short")
    assert check_content_quality(result, min_length=100) is False


def test_empty_content_fails() -> None:
    """Empty content should fail."""
    result = ContentResult(text="")
    assert check_content_quality(result) is False


def test_whitespace_only_content_fails() -> None:
    """Whitespace-only content should fail after stripping."""
    result = ContentResult(text="   \n\t  \n   ")
    assert check_content_quality(result) is False


def test_custom_threshold() -> None:
    """Short text should pass with a low custom threshold."""
    result = ContentResult(text="Hello")
    assert check_content_quality(result, min_length=5) is True


def test_exactly_at_threshold() -> None:
    """Content exactly at threshold length should pass."""
    result = ContentResult(text="a" * 100)
    assert check_content_quality(result, min_length=100) is True
