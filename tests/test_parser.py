"""Test HTML parser: sections, breadcrumbs, code blocks."""

from docwarden.parser import parse_page


def test_sections_split_on_headings(sample_html):
    sections = parse_page(sample_html, content_selector="article")
    titles = [s.section_title for s in sections]
    assert "Path Parameters" in titles
    assert "Example" in titles
    assert "Data Validation" in titles


def test_breadcrumb_nested_headings(sample_html):
    sections = parse_page(sample_html, content_selector="article")
    types_section = next((s for s in sections if s.section_title == "Supported Types"), None)
    assert types_section is not None
    assert "Data Validation" in types_section.breadcrumb
    assert "Supported Types" in types_section.breadcrumb


def test_code_block_preserved(sample_html):
    sections = parse_page(sample_html, content_selector="article")
    example = next(s for s in sections if s.section_title == "Example")
    assert "```" in example.content
    assert "item_id" in example.content


def test_nav_footer_stripped():
    html = """<html><body>
    <nav>Should be stripped</nav>
    <article>
      <h1>Title</h1>
      <p>Real content here.</p>
    </article>
    <footer>Also stripped</footer>
    </body></html>"""
    sections = parse_page(html, content_selector="article")
    full = " ".join(s.content for s in sections)
    assert "Should be stripped" not in full
    assert "Also stripped" not in full
    assert "Real content here" in full


def test_anchor_extracted():
    html = """<html><body><article>
    <h2 id="path-params">Path Params</h2>
    <p>Details here.</p>
    </article></body></html>"""
    sections = parse_page(html, content_selector="article")
    s = next((x for x in sections if x.section_title == "Path Params"), None)
    assert s is not None
    assert s.anchor == "path-params"


def test_empty_sections_not_returned():
    html = """<html><body><article>
    <h2>Empty</h2>
    <h2>Has content</h2>
    <p>Some text.</p>
    </article></body></html>"""
    sections = parse_page(html, content_selector="article")
    titles = [s.section_title for s in sections]
    assert "Has content" in titles
    # "Empty" section has no content so should be absent or empty
    empty_secs = [s for s in sections if s.section_title == "Empty"]
    assert all(not s.content.strip() for s in empty_secs) or "Empty" not in titles


def test_fallback_to_body_when_selector_missing():
    html = """<html><body>
    <div class="content">
      <h1>Hello</h1>
      <p>World</p>
    </div>
    </body></html>"""
    # selector won't match — should fall back to body
    sections = parse_page(html, content_selector="article")
    assert any("World" in s.content for s in sections)
