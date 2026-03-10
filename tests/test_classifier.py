"""Tests for URL classifier."""

from extractors.classifier import ContentType, classify_url


class TestClassifyUrl:
    def test_youtube_watch_url(self):
        assert classify_url("https://www.youtube.com/watch?v=abc123") == ContentType.VIDEO

    def test_youtube_short_url(self):
        assert classify_url("https://youtu.be/abc123") == ContentType.VIDEO

    def test_youtube_shorts_url(self):
        assert classify_url("https://www.youtube.com/shorts/abc123") == ContentType.VIDEO

    def test_vimeo_url(self):
        assert classify_url("https://vimeo.com/123456") == ContentType.VIDEO

    def test_dailymotion_url(self):
        assert classify_url("https://www.dailymotion.com/video/x7tgad0") == ContentType.VIDEO

    def test_regular_article_url(self):
        assert classify_url("https://example.com/some-article") == ContentType.ARTICLE

    def test_github_url(self):
        assert classify_url("https://github.com/user/repo") == ContentType.ARTICLE

    def test_empty_url(self):
        assert classify_url("") == ContentType.ARTICLE
