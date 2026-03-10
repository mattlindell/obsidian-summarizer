from unittest.mock import patch, MagicMock

from extractors.base import ContentResult
from extractors.video import extract_video_content


def _make_yt_dlp_info(
    title="Test Video",
    uploader="Test Channel",
    duration=300,
    description="A test video",
    subtitles=None,
    automatic_captions=None,
):
    return {
        "title": title,
        "uploader": uploader,
        "duration": duration,
        "description": description,
        "subtitles": subtitles or {},
        "automatic_captions": automatic_captions or {},
    }


@patch("extractors.video._download_subtitle_text", return_value="Hello world transcript")
@patch("extractors.video._get_video_info")
def test_extract_with_manual_subtitles(mock_info, mock_download):
    mock_info.return_value = _make_yt_dlp_info(
        subtitles={"en": [{"ext": "srv3", "url": "http://example.com/sub"}]}
    )

    result = extract_video_content("https://youtube.com/watch?v=abc")

    assert result.title == "Test Video"
    assert result.author == "Test Channel"
    assert result.text == "Hello world transcript"
    assert result.content_type == "video"
    assert result.extraction_succeeded is True
    mock_download.assert_called_once()


@patch("extractors.video._download_subtitle_text", return_value="Auto caption text")
@patch("extractors.video._get_video_info")
def test_extract_falls_back_to_auto_captions(mock_info, mock_download):
    mock_info.return_value = _make_yt_dlp_info(
        subtitles={},
        automatic_captions={"en": [{"ext": "srv3", "url": "http://example.com/auto"}]},
    )

    result = extract_video_content("https://youtube.com/watch?v=abc")

    assert result.text == "Auto caption text"
    assert result.extraction_succeeded is True
    mock_download.assert_called_once()


@patch("extractors.video._download_subtitle_text")
@patch("extractors.video._get_video_info")
def test_extract_falls_back_to_description_when_no_subs(mock_info, mock_download):
    mock_info.return_value = _make_yt_dlp_info(
        subtitles={},
        automatic_captions={},
        description="This is the video description fallback",
    )

    result = extract_video_content("https://youtube.com/watch?v=abc")

    assert result.text == "This is the video description fallback"
    assert result.extraction_succeeded is True
    mock_download.assert_not_called()


@patch("extractors.video._get_video_info", side_effect=Exception("Network error"))
def test_extract_returns_empty_result_on_failure(mock_info):
    result = extract_video_content("https://youtube.com/watch?v=abc")

    assert result.text == ""
    assert result.title == ""
    assert result.content_type == "video"
    assert result.extraction_succeeded is False
    assert result.url == "https://youtube.com/watch?v=abc"


@patch("extractors.video._download_subtitle_text", return_value="Some transcript")
@patch("extractors.video._get_video_info")
def test_metadata_includes_duration(mock_info, mock_download):
    mock_info.return_value = _make_yt_dlp_info(duration=600)

    result = extract_video_content("https://youtube.com/watch?v=abc")

    assert result.metadata["duration"] == 600
    assert "description" in result.metadata
