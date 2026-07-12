"""End-to-end: index fixture HTML, assert all three MCP tools work correctly."""

import sqlite3

import pytest

from docwarden.indexer import index_html
from docwarden.server import _get_page, _get_section, _search_docs

URL = "https://fastapi.tiangolo.com/tutorial/path-params/"
HTML = """
<html><body><article>
  <h1 id="path-parameters">Path Parameters</h1>
  <p>You can declare path parameters with the same syntax used by Python format strings.</p>
  <h2 id="example">Example</h2>
  <p>Here is a simple route with a path parameter:</p>
  <pre><code>@app.get("/items/{item_id}")
async def read_item(item_id: int):
    return {"item_id": item_id}</code></pre>
  <h2 id="validation">Data Validation</h2>
  <p>FastAPI validates the path parameter automatically using pydantic.</p>
  <h3 id="types">Supported Types</h3>
  <p>You can use int, float, str, bool, UUID, and many more types.</p>
</article></body></html>
"""


@pytest.fixture()
def indexed_db(db: sqlite3.Connection) -> sqlite3.Connection:
    index_html(db, "fastapi", URL, HTML, "article")
    return db


def test_search_returns_results(indexed_db):
    results = _search_docs(indexed_db, "path parameter")
    assert results
    text = results[0].text
    assert "path" in text.lower() or "parameter" in text.lower()


def test_search_result_contains_source_url(indexed_db):
    results = _search_docs(indexed_db, "item_id")
    assert results
    assert "fastapi.tiangolo.com" in results[0].text


def test_search_result_contains_indexed_at(indexed_db):
    results = _search_docs(indexed_db, "path parameter")
    assert results
    text = results[0].text
    assert "Indexed:" in text or "ago" in text or "today" in text


def test_search_framework_filter(indexed_db):
    # fastapi should find results, react should not (no react docs indexed)
    results_fa = _search_docs(indexed_db, "path parameter", framework="fastapi")
    results_re = _search_docs(indexed_db, "path parameter", framework="react")
    assert results_fa[0].text != "No results found for that query."
    assert "react" in results_re[0].text.lower()
    assert "docswarden index react" in results_re[0].text


def test_search_no_docs_indexed_at_all_hints_index_command(db):
    results = _search_docs(db, "anything")
    assert "docswarden index" in results[0].text


def test_search_no_docs_for_framework_hints_index_command(indexed_db):
    results = _search_docs(indexed_db, "path parameter", framework="nextjs")
    assert "docswarden index nextjs" in results[0].text


def test_search_no_results_for_indexed_framework_is_generic(indexed_db):
    # fastapi IS indexed, but the query matches nothing — should be the plain message
    results = _search_docs(indexed_db, "zzzznonexistentqueryzzzz", framework="fastapi")
    assert results[0].text == "No results found for that query."


def test_search_limit_respected(indexed_db):
    results = _search_docs(indexed_db, "the", limit=1)
    # Should be 1 result block (split by ---)
    assert results
    assert results[0].text.count("---") == 0  # only one result = no separator


def test_get_page_returns_section_list_not_body(indexed_db):
    results = _get_page(indexed_db, URL)
    assert results
    text = results[0].text
    assert "Example" in text or "Validation" in text
    # Must NOT dump the full prose body
    assert "pydantic" not in text  # that's body content, not a section title


def test_get_page_not_found(indexed_db):
    results = _get_page(indexed_db, "https://notindexed.example.com/page")
    assert "not found" in results[0].text.lower()


def test_get_section_returns_content(indexed_db):
    results = _get_section(indexed_db, URL, "Example")
    assert results
    text = results[0].text
    assert "item_id" in text
    assert "```" in text  # code block preserved


def test_get_section_includes_source_url(indexed_db):
    results = _get_section(indexed_db, URL, "Data Validation")
    assert URL in results[0].text


def test_get_section_not_found(indexed_db):
    results = _get_section(indexed_db, URL, "Nonexistent Section")
    assert "not found" in results[0].text.lower()
