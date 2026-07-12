"""Index pipeline: crawl -> parse -> chunk -> write to SQLite."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .chunker import chunk_sections
from .crawler import crawl_recipe
from .parser import parse_page
from .recipes import Recipe
from .store import get_connection, init_schema


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _content_hash(html: str) -> str:
    return hashlib.sha256(html.encode()).hexdigest()


def index_html(
    conn,
    framework: str,
    url: str,
    html: str,
    content_selector: str = "article",
) -> int:
    """Parse and index a single page. Returns number of chunks written."""
    chash = _content_hash(html)
    existing = conn.execute(
        "SELECT id, content_hash FROM pages WHERE framework = ? AND url = ?",
        (framework, url),
    ).fetchone()

    if existing and existing["content_hash"] == chash:
        return 0  # unchanged, skip

    sections = parse_page(html, content_selector=content_selector, url=url)
    page_title = sections[0].section_title if sections else url
    chunks = chunk_sections(sections)

    if not chunks:
        return 0

    now = _now_iso()

    if existing:
        conn.execute(
            "UPDATE pages SET title=?, indexed_at=?, content_hash=? WHERE id=?",
            (page_title, now, chash, existing["id"]),
        )
        page_id = existing["id"]
        conn.execute("DELETE FROM chunks WHERE page_id = ?", (page_id,))
    else:
        cur = conn.execute(
            "INSERT INTO pages (framework, url, title, indexed_at, content_hash)"
            " VALUES (?,?,?,?,?)",
            (framework, url, page_title, now, chash),
        )
        page_id = cur.lastrowid

    conn.executemany(
        "INSERT INTO chunks (page_id, framework, breadcrumb, section_title, anchor, content, ord) "
        "VALUES (?,?,?,?,?,?,?)",
        [
            (page_id, framework, c.breadcrumb, c.section_title, c.anchor, c.content, c.ord)
            for c in chunks
        ],
    )
    conn.commit()
    return len(chunks)


async def index_recipe(recipe: Recipe) -> None:
    """Full pipeline: crawl recipe source, parse, chunk, index all pages."""
    pages = await crawl_recipe(recipe)
    if not pages:
        print(f"  No pages found for {recipe.name}")
        return

    conn = get_connection()
    init_schema(conn)
    total_chunks = 0
    skipped = 0
    for i, (url, html) in enumerate(pages, 1):
        n = index_html(
            conn,
            framework=recipe.id,
            url=url,
            html=html,
            content_selector=recipe.parser.content_selector,
        )
        if n:
            total_chunks += n
        else:
            skipped += 1
        if i % 10 == 0 or i == len(pages):
            print(f"  [{i}/{len(pages)}] {total_chunks} chunks | {skipped} skipped (unchanged)")
    conn.close()
    print(f"  Finished: {len(pages)} pages, {total_chunks} new/updated chunks, {skipped} unchanged")
