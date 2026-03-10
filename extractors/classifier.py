import re
from enum import Enum


class ContentType(Enum):
    VIDEO = "video"
    ARTICLE = "article"


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
