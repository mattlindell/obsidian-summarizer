import os

from jinja2 import Environment, FileSystemLoader

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def _render(template_name: str, **kwargs: str) -> str:
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template(template_name)
    return template.render(**kwargs)


SUMMARY_VARS = {
    "title": "Test Article Title",
    "source": "https://example.com/article",
    "author": "Jane Doe",
    "published": "2025-01-15",
    "created": "2025-01-16",
    "llm_summary": "This is a test summary of the article content.",
}

FAILED_VARS = {
    "title": "Failed Article Title",
    "source": "https://example.com/failed",
    "author": "John Smith",
    "published": "2025-02-01",
    "created": "2025-02-02",
    "original_excerpt": "This is the original clipping text that could not be processed.",
}


def test_summary_template_renders_frontmatter() -> None:
    output = _render("summary.md.j2", **SUMMARY_VARS)
    assert 'title: "Test Article Title"' in output
    assert 'source: "https://example.com/article"' in output
    assert 'author: "Jane Doe"' in output
    assert "## AI Summary" in output
    assert "This is a test summary of the article content." in output


def test_summary_template_has_my_notes_section() -> None:
    output = _render("summary.md.j2", **SUMMARY_VARS)
    assert "## My Notes" in output
    assert "Key takeaways" in output


def test_failed_extraction_template_shows_notice() -> None:
    output = _render("failed_extraction.md.j2", **FAILED_VARS)
    assert "could not be automatically extracted" in output
    assert "This is the original clipping text that could not be processed." in output
    assert "AI Summary" not in output


def test_failed_extraction_template_has_my_notes_section() -> None:
    output = _render("failed_extraction.md.j2", **FAILED_VARS)
    assert "## My Notes" in output
    assert "Key takeaways" in output


def test_both_templates_have_dataview_query() -> None:
    summary_output = _render("summary.md.j2", **SUMMARY_VARS)
    failed_output = _render("failed_extraction.md.j2", **FAILED_VARS)
    assert "dataview" in summary_output
    assert "dataview" in failed_output
