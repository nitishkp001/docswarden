"""Test indexer: upsert, content_hash skip, FTS sync."""

from docwarden.indexer import index_html

SAMPLE_HTML = """
<html><body><article>
  <h1 id="guide">Path Parameters</h1>
  <p>Declare path parameters with type annotations.</p>
  <h2 id="example">Example</h2>
  <p>Use curly braces in the route.</p>
  <pre><code>@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id": item_id}</code></pre>
</article></body></html>
"""


def test_index_creates_page_and_chunks(db):
    n = index_html(db, "fastapi", "https://example.com/path-params", SAMPLE_HTML, "article")
    assert n > 0
    row = db.execute("SELECT COUNT(*) as c FROM pages").fetchone()
    assert row["c"] == 1
    chunks = db.execute("SELECT COUNT(*) as c FROM chunks").fetchone()
    assert chunks["c"] == n


def test_unchanged_content_skipped(db):
    url = "https://example.com/path-params"
    n1 = index_html(db, "fastapi", url, SAMPLE_HTML, "article")
    n2 = index_html(db, "fastapi", url, SAMPLE_HTML, "article")
    assert n1 > 0
    assert n2 == 0  # same hash → skipped
    assert db.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1


def test_changed_content_reindexed(db):
    url = "https://example.com/path-params"
    index_html(db, "fastapi", url, SAMPLE_HTML, "article")
    updated = SAMPLE_HTML.replace("type annotations", "Python type hints UPDATED")
    n2 = index_html(db, "fastapi", url, updated, "article")
    assert n2 > 0
    assert db.execute("SELECT COUNT(*) FROM pages").fetchone()[0] == 1  # still 1 page


def test_fts_in_sync(db):
    index_html(db, "fastapi", "https://example.com/path-params", SAMPLE_HTML, "article")
    rows = db.execute(
        "SELECT c.content FROM chunks_fts f JOIN chunks c ON c.id = f.rowid"
        " WHERE chunks_fts MATCH 'item_id'",
    ).fetchall()
    assert len(rows) > 0


def test_delete_page_cascades_chunks(db):
    url = "https://example.com/path-params"
    index_html(db, "fastapi", url, SAMPLE_HTML, "article")
    db.execute("DELETE FROM pages WHERE url = ?", (url,))
    db.commit()
    assert db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] == 0


def test_multiple_frameworks_isolated(db):
    index_html(db, "fastapi", "https://fastapi.example.com/a", SAMPLE_HTML, "article")
    index_html(db, "react", "https://react.example.com/a", SAMPLE_HTML, "article")
    fa = db.execute("SELECT COUNT(*) FROM chunks WHERE framework='fastapi'").fetchone()[0]
    re = db.execute("SELECT COUNT(*) FROM chunks WHERE framework='react'").fetchone()[0]
    assert fa > 0 and re > 0
