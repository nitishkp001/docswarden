"""Test chunker — the quality-critical stage.

These tests are the primary guard on retrieval quality.
"""

from docwarden.chunker import SOFT_MAX_CHARS, chunk_sections
from docwarden.parser import Section


def _section(title: str, content: str, breadcrumb: str | None = None, level: int = 2) -> Section:
    return Section(
        breadcrumb=breadcrumb or f"Guide > {title}",
        section_title=title,
        anchor=title.lower().replace(" ", "-"),
        content=content,
        level=level,
    )


def test_basic_chunking_returns_chunks():
    sections = [_section("Intro", "This is the intro paragraph.")]
    chunks = chunk_sections(sections)
    assert len(chunks) == 1
    assert "intro" in chunks[0].content.lower()


def test_breadcrumb_present_on_all_chunks():
    sections = [
        _section("A", "Content A", breadcrumb="Doc > A"),
        _section("B", "Content B", breadcrumb="Doc > B"),
    ]
    chunks = chunk_sections(sections)
    for c in chunks:
        assert c.breadcrumb, "breadcrumb must be non-empty"


def test_code_block_stays_with_intro_paragraph():
    content = (
        "Here is how to declare a path parameter:\n\n"
        "```\n@app.get('/items/{item_id}')\ndef read(item_id: int): pass\n```"
    )
    sections = [_section("Example", content)]
    chunks = chunk_sections(sections)
    # Must be in the same chunk, not split
    assert len(chunks) == 1
    assert "```" in chunks[0].content
    assert "path parameter" in chunks[0].content


def test_oversized_section_splits_on_paragraphs():
    # Build a section bigger than SOFT_MAX_CHARS
    paras = [f"Paragraph {i}: " + ("x " * 100) for i in range(30)]
    content = "\n\n".join(paras)
    assert len(content) > SOFT_MAX_CHARS
    sections = [_section("Big", content, breadcrumb="Guide > Big")]
    chunks = chunk_sections(sections)
    assert len(chunks) > 1
    # every split chunk must carry the breadcrumb
    for c in chunks:
        assert c.breadcrumb == "Guide > Big"


def test_oversized_code_block_not_separated_from_prior_prose():
    prose = "This code shows the full configuration:\n\n"
    code_lines = [f"# line {i}" for i in range(200)]
    code_block = "```\n" + "\n".join(code_lines) + "\n```"
    content = prose + code_block
    # Even if over limit, prose+code stay together in one chunk
    sections = [_section("Config", content)]
    chunks = chunk_sections(sections)
    if len(chunks) > 1:
        # code and its prose intro must be in the same chunk
        intro_chunk = next((c for c in chunks if "full configuration" in c.content), None)
        assert intro_chunk is not None
        assert "```" in intro_chunk.content


def test_empty_sections_dropped():
    sections = [
        _section("Empty", "   "),
        _section("Has content", "Some real text here."),
    ]
    chunks = chunk_sections(sections)
    titles = [c.section_title for c in chunks]
    assert "Has content" in titles
    assert "Empty" not in titles


def test_chunk_ord_is_sequential():
    sections = [_section(f"Section {i}", f"Content {i}") for i in range(5)]
    chunks = chunk_sections(sections)
    ords = [c.ord for c in chunks]
    assert ords == list(range(len(chunks)))


def test_nested_heading_breadcrumb():
    sections = [
        Section(
            breadcrumb="Guide > Routing > Dynamic Segments",
            section_title="Dynamic Segments",
            anchor="dynamic-segments",
            content="Dynamic segments are wrapped in brackets.",
            level=3,
        )
    ]
    chunks = chunk_sections(sections)
    assert chunks[0].breadcrumb == "Guide > Routing > Dynamic Segments"


def test_whitespace_only_content_dropped():
    sections = [_section("Blank", "\n\n\t\n")]
    chunks = chunk_sections(sections)
    assert len(chunks) == 0


def test_multiple_code_blocks_in_section():
    content = "First approach:\n\n```\ncode_one()\n```\n\nSecond approach:\n\n```\ncode_two()\n```"
    sections = [_section("Approaches", content)]
    chunks = chunk_sections(sections)
    full = " ".join(c.content for c in chunks)
    assert "code_one" in full
    assert "code_two" in full


def test_adversarial_deep_nesting():
    """Deeply nested headings produce correct breadcrumb at every level."""
    sections = [
        Section("H1 > H2 > H3 > H4", "H4 title", "h4-anchor", "Content deep.", 4),
    ]
    chunks = chunk_sections(sections)
    assert chunks[0].breadcrumb == "H1 > H2 > H3 > H4"


def test_adversarial_table_content():
    html_table_text = "Column A Column B\nvalue1   value2\nvalue3   value4"
    sections = [_section("Table", html_table_text)]
    chunks = chunk_sections(sections)
    assert len(chunks) >= 1
    assert "value1" in chunks[0].content
