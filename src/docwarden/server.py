"""MCP server exposing search_docs, get_page, get_section tools."""

import sqlite3
from datetime import UTC, datetime

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .store import get_connection, init_schema

app = Server("docwarden")


def _conn() -> sqlite3.Connection:
    conn = get_connection()
    init_schema(conn)
    return conn


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_docs",
            description=(
                "Search indexed framework documentation. Returns ranked chunks "
                "with source URL and index date. Always cite the source_url. "
                "Optionally filter by framework name."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "framework": {
                        "type": "string",
                        "description": (
                            "Filter to a specific framework "
                            "(e.g. 'fastapi', 'react', 'nextjs'). Omit to search all."
                        ),
                    },
                    "limit": {
                        "type": "integer",
                        "default": 8,
                        "description": "Max results to return (default 8)",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="get_page",
            description=(
                "Get the section list for a documentation page URL. "
                "Returns sections (title + anchor) — NOT the full body. "
                "Use get_section to read a specific section."
            ),
            inputSchema={
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Documentation page URL"}},
                "required": ["url"],
            },
        ),
        Tool(
            name="get_section",
            description="Get the full content of one section from a documentation page.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Documentation page URL"},
                    "section_title": {
                        "type": "string",
                        "description": "Section title as returned by get_page",
                    },
                },
                "required": ["url", "section_title"],
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    conn = _conn()
    try:
        if name == "search_docs":
            return _search_docs(conn, **arguments)
        if name == "get_page":
            return _get_page(conn, **arguments)
        if name == "get_section":
            return _get_section(conn, **arguments)
        raise ValueError(f"Unknown tool: {name}")
    finally:
        conn.close()


def _search_docs(
    conn: sqlite3.Connection,
    query: str,
    framework: str | None = None,
    limit: int = 8,
) -> list[TextContent]:
    if framework:
        rows = conn.execute(
            """
            SELECT c.framework, c.breadcrumb, c.section_title, c.anchor, c.content,
                   p.url, p.indexed_at
            FROM chunks_fts f
            JOIN chunks c ON c.id = f.rowid
            JOIN pages p ON p.id = c.page_id
            WHERE chunks_fts MATCH ? AND c.framework = ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, framework, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT c.framework, c.breadcrumb, c.section_title, c.anchor, c.content,
                   p.url, p.indexed_at
            FROM chunks_fts f
            JOIN chunks c ON c.id = f.rowid
            JOIN pages p ON p.id = c.page_id
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        ).fetchall()

    if not rows:
        return [TextContent(type="text", text=_empty_result_hint(conn, framework))]

    results = []
    for r in rows:
        anchor = f"#{r['anchor']}" if r["anchor"] else ""
        source_url = f"{r['url']}{anchor}"
        indexed = _human_age(r["indexed_at"])
        snippet = r["content"][:400].rstrip() + ("…" if len(r["content"]) > 400 else "")
        results.append(
            f"**{r['breadcrumb']}**\n{snippet}\n"
            f"Source: {source_url} | Framework: {r['framework']} | Indexed: {indexed}"
        )

    return [TextContent(type="text", text="\n\n---\n\n".join(results))]


def _get_page(conn: sqlite3.Connection, url: str) -> list[TextContent]:
    page = conn.execute(
        "SELECT id, title, framework, indexed_at FROM pages WHERE url = ?", (url,)
    ).fetchone()
    if not page:
        return [TextContent(type="text", text=f"Page not found in index: {url}")]

    sections = conn.execute(
        "SELECT section_title, anchor, breadcrumb FROM chunks WHERE page_id = ? ORDER BY ord",
        (page["id"],),
    ).fetchall()

    lines = [
        f"# {page['title'] or url}",
        f"Framework: {page['framework']} | Indexed: {_human_age(page['indexed_at'])}",
        "",
    ]
    for s in sections:
        anchor = f" (#{s['anchor']})" if s["anchor"] else ""
        lines.append(f"- {s['breadcrumb']}{anchor}")

    return [TextContent(type="text", text="\n".join(lines))]


def _get_section(conn: sqlite3.Connection, url: str, section_title: str) -> list[TextContent]:
    page = conn.execute("SELECT id, url FROM pages WHERE url = ?", (url,)).fetchone()
    if not page:
        return [TextContent(type="text", text=f"Page not found in index: {url}")]

    chunk = conn.execute(
        "SELECT content, breadcrumb, anchor FROM chunks"
        " WHERE page_id = ? AND section_title = ? ORDER BY ord LIMIT 1",
        (page["id"], section_title),
    ).fetchone()
    if not chunk:
        return [TextContent(type="text", text=f"Section '{section_title}' not found on {url}")]

    anchor = f"#{chunk['anchor']}" if chunk["anchor"] else ""
    return [
        TextContent(
            type="text",
            text=f"**{chunk['breadcrumb']}**\nSource: {url}{anchor}\n\n{chunk['content']}",
        )
    ]


def _empty_result_hint(conn: sqlite3.Connection, framework: str | None) -> str:
    if framework:
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM pages WHERE framework = ?", (framework,)
        ).fetchone()["n"]
        if count == 0:
            return (
                f"No docs indexed yet for '{framework}'. "
                f"Run `docswarden index {framework}` to crawl it, then search again."
            )
    else:
        count = conn.execute("SELECT COUNT(*) AS n FROM pages").fetchone()["n"]
        if count == 0:
            return (
                "No docs indexed yet. Run `docswarden index <framework>` "
                "(e.g. `docswarden index fastapi react nextjs`) to crawl and index docs, "
                "then search again."
            )
    return "No results found for that query."


def _human_age(iso: str) -> str:
    try:
        then = datetime.fromisoformat(iso).replace(tzinfo=UTC)
        delta = datetime.now(UTC) - then
        days = delta.days
        if days == 0:
            return "today"
        if days == 1:
            return "1 day ago"
        return f"{days} days ago"
    except Exception:
        return iso


async def serve() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
