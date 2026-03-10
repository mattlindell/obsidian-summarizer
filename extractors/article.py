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
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        content = None
        for selector in ["article", '[role="main"]', "main", ".content", "#content"]:
            content = soup.select_one(selector)
            if content:
                break
        if not content:
            content = soup.find("body")

        text = ""
        if content is not None:
            text = content.get_text(strip=True, separator=" ")
            text = re.sub(r"\s+", " ", text)

        title_tag = soup.find("title")
        title = title_tag.get_text().strip() if title_tag else "Untitled"

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
