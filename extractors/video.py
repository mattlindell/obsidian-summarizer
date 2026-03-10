"""Video content extractor using yt-dlp for transcript and metadata."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import yt_dlp

from extractors.base import ContentResult

logger = logging.getLogger(__name__)

_MANUAL_LANG_KEYS = ("en", "en-US", "en-GB")
_AUTO_LANG_KEYS = ("en", "en-US", "en-GB", "en-orig")


def _get_video_info(url: str) -> dict[str, Any]:
    """Extract video metadata and subtitle info via yt-dlp without downloading."""
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "en-US", "en-GB", "en-orig"],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(url, download=False)


def _clean_srt_text(raw: str) -> str:
    """Strip SRT sequence numbers, timestamps, and WebVTT tags from subtitle text."""
    # Remove WebVTT header
    raw = re.sub(r"WEBVTT.*?\n\n", "", raw, count=1, flags=re.DOTALL)
    # Remove SRT sequence numbers (standalone digits on a line)
    raw = re.sub(r"^\d+\s*$", "", raw, flags=re.MULTILINE)
    # Remove SRT/WebVTT timestamps  e.g. 00:00:01,234 --> 00:00:03,456
    raw = re.sub(r"\d{2}:\d{2}:\d{2}[.,]\d{3}\s*-->.*", "", raw)
    # Remove WebVTT tags like <c>, </c>, <00:00:01.234>
    raw = re.sub(r"<[^>]+>", "", raw)
    # Collapse whitespace
    raw = re.sub(r"\n{2,}", "\n", raw)
    return raw.strip()


def _parse_json3(data: str) -> str:
    """Parse yt-dlp json3 subtitle format, extracting text from events."""
    try:
        parsed = json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return ""
    segments: list[str] = []
    for event in parsed.get("events", []):
        for seg in event.get("segs", []):
            text = seg.get("utf8", "")
            if text and text != "\n":
                segments.append(text)
    return " ".join(segments).strip()


def _download_subtitle_text(subtitle_entries: list[dict[str, Any]]) -> str:
    """Download subtitle content from yt-dlp subtitle entry list and clean it."""
    import urllib.request

    # Prefer json3, then srv3/vtt/srt
    preferred_order = ("json3", "srv3", "vtt", "srt")
    entries_by_ext: dict[str, dict] = {}
    for entry in subtitle_entries:
        ext = entry.get("ext", "")
        if ext not in entries_by_ext:
            entries_by_ext[ext] = entry

    chosen = None
    for ext in preferred_order:
        if ext in entries_by_ext:
            chosen = entries_by_ext[ext]
            break
    if chosen is None and subtitle_entries:
        chosen = subtitle_entries[0]
    if chosen is None:
        return ""

    url = chosen.get("url", "")
    if not url:
        return ""

    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception:
        logger.warning("Failed to download subtitle from %s", url, exc_info=True)
        return ""

    ext = chosen.get("ext", "")
    if ext == "json3":
        return _parse_json3(raw)
    return _clean_srt_text(raw)


def _find_subtitle_entries(
    info: dict[str, Any],
) -> list[dict[str, Any]] | None:
    """Walk the subtitle/auto-caption dicts looking for English entries."""
    # 1. Manual subtitles
    subtitles = info.get("subtitles") or {}
    for lang in _MANUAL_LANG_KEYS:
        if lang in subtitles and subtitles[lang]:
            return subtitles[lang]

    # 2. Automatic captions
    auto = info.get("automatic_captions") or {}
    for lang in _AUTO_LANG_KEYS:
        if lang in auto and auto[lang]:
            return auto[lang]

    return None


def extract_video_content(url: str) -> ContentResult:
    """Extract video transcript and metadata, returning a ContentResult."""
    try:
        info = _get_video_info(url)
    except Exception:
        logger.warning("Failed to extract video info for %s", url, exc_info=True)
        return ContentResult(url=url, content_type="video")

    title = info.get("title", "")
    uploader = info.get("uploader")
    duration = info.get("duration")
    description = info.get("description", "")

    # Try to get transcript from subtitles
    text = ""
    entries = _find_subtitle_entries(info)
    if entries is not None:
        text = _download_subtitle_text(entries)

    # Fall back to description
    if not text:
        text = description or ""

    return ContentResult(
        title=title,
        text=text,
        author=uploader,
        url=url,
        content_type="video",
        extraction_succeeded=True,
        metadata={
            "duration": duration,
            "description": description,
        },
    )
