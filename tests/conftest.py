"""Shared fixtures for all tests.

Key rule: tests NEVER touch the real user data dir.
All DB access goes through a tmp_path-scoped DOCWARDEN_DATA_DIR.
"""

import sqlite3

import pytest

from docwarden.store import get_connection, init_schema


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Redirect all DB/data access to a temp dir for the duration of each test."""
    monkeypatch.setenv("DOCWARDEN_DATA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture()
def db(isolated_data_dir) -> sqlite3.Connection:
    """In-memory-equivalent: a fresh schema in the test's tmp dir."""
    conn = get_connection()
    init_schema(conn)
    return conn


@pytest.fixture()
def sample_html() -> str:
    return """
    <html><body>
    <article>
      <h1 id="guide">Path Parameters</h1>
      <p>You can declare path parameters with Python type annotations.</p>
      <h2 id="example">Example</h2>
      <p>Here is a simple example:</p>
      <pre><code>@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id": item_id}</code></pre>
      <h2 id="validation">Data Validation</h2>
      <p>FastAPI validates the path parameter automatically.</p>
      <h3 id="types">Supported Types</h3>
      <p>You can use int, float, str, bool, and more.</p>
    </article>
    </body></html>
    """
