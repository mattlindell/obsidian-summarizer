from unittest.mock import MagicMock, patch

from extractors.article import extract_article_content

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


@patch("extractors.article.requests.get", return_value=_mock_response(SAMPLE_HTML))
def test_extract_article_content(mock_get):
    result = extract_article_content("https://example.com/article")
    assert "main article content" in result.text
    assert result.content_type == "article"


@patch("extractors.article.requests.get", return_value=_mock_response(SAMPLE_HTML))
def test_extract_strips_nav_and_footer(mock_get):
    result = extract_article_content("https://example.com/article")
    assert "Navigation stuff" not in result.text
    assert "Footer stuff" not in result.text


@patch("extractors.article.requests.get", return_value=_mock_response(SAMPLE_HTML))
def test_extract_gets_title(mock_get):
    result = extract_article_content("https://example.com/article")
    assert result.title == "Test Article Title"


@patch("extractors.article.requests.get", side_effect=Exception("Connection error"))
def test_extract_returns_empty_on_failure(mock_get):
    result = extract_article_content("https://example.com/fail")
    assert result.text == ""


@patch("extractors.article.requests.get", return_value=_mock_response(MINIMAL_HTML))
def test_extract_handles_minimal_html(mock_get):
    result = extract_article_content("https://example.com/minimal")
    assert result.title == "Sparse Page"
