# FrameworkDocs MCP — Implementation Plan

A local-first MCP server that indexes framework documentation into a local SQLite
FTS5 index and exposes it to MCP clients (Claude Desktop, Cursor, VS Code).

This document is the source of truth for **what to build and in what order**. It is
written for autonomous agents: work top-to-bottom, check boxes as you complete
them, and do not start a milestone until the previous one's exit criteria are met.

> Companion docs: [`CLAUDE.md`](./CLAUDE.md) (how to work in this repo) and
> [`AGENTS.md`](./AGENTS.md) (conventions + testing contract). Read both before
> writing code.

---

## Locked decisions

| Area          | Decision                                                             |
| ------------- | -------------------------------------------------------------------- |
| Search        | SQLite **FTS5 + BM25 only**. No embeddings, no model download in v1. |
| Catalog v1    | **React, Next.js, FastAPI** — curated recipes we dogfood.            |
| Packaging     | `pyproject.toml`, runnable via **`uvx frameworkdocs-mcp`**.          |
| Clients       | Install writes config for **Claude Desktop, Cursor, VS Code**; prints snippet otherwise. |
| MCP tools v1  | `search_docs`, `get_page`, `get_section`.                            |
| Deferred → P2 | Embeddings/semantic search, versioning (`list_versions`), incremental recrawl, `summarize_topic`. |
| Runtime data  | XDG dir `~/.local/share/frameworkdocs-mcp/`, **never** inside the repo. |

---

## Architecture at a glance

```text
recipe (YAML)  ->  crawler  ->  parser  ->  chunker  ->  indexer (SQLite FTS5)
                                                              |
                                            MCP server (stdio) -> AI client
```

The **recipes are the product.** Each is ~15 lines of YAML capturing the per-site
knowledge (sitemap location, content selector, version scheme) needed to produce
clean chunks. Everything else is generic machinery.

---

## Target project layout

```text
frameworkdocs-mcp/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── AGENTS.md
├── IMPLEMENTATION_PLAN.md
├── .gitignore
├── src/frameworkdocs_mcp/
│   ├── __init__.py
│   ├── server.py          # MCP server + tool defs (entrypoint)
│   ├── cli.py             # install / index / list / run
│   ├── recipes.py         # load + validate YAML recipes (pydantic)
│   ├── crawler.py         # fetch URLs per recipe (httpx + sitemap)
│   ├── parser.py          # HTML -> clean ordered sections
│   ├── chunker.py         # sections -> chunks w/ heading breadcrumb
│   ├── indexer.py         # SQLite FTS5 write/read
│   ├── store.py           # DB connection, schema, XDG paths
│   ├── clients.py         # write MCP config for the 3 targets
│   └── recipes/
│       ├── react.yaml
│       ├── nextjs.yaml
│       └── fastapi.yaml
├── tests/
│   ├── conftest.py
│   ├── fixtures/          # saved HTML pages for offline parser/chunker tests
│   ├── test_recipes.py
│   ├── test_parser.py
│   ├── test_chunker.py
│   ├── test_indexer.py
│   ├── test_search.py
│   ├── test_clients.py
│   └── canary/
│       └── test_recipes_live.py   # network-gated CI canary
└── data/                  # gitignored; created at runtime (usually XDG dir)
```

---

## Data model (SQLite)

```sql
CREATE TABLE pages (
  id           INTEGER PRIMARY KEY,
  framework    TEXT NOT NULL,
  url          TEXT NOT NULL,
  title        TEXT,
  indexed_at   TEXT NOT NULL,        -- ISO8601, drives "indexed N days ago"
  content_hash TEXT NOT NULL,        -- for future incremental recrawl
  UNIQUE(framework, url)
);

CREATE TABLE chunks (
  id            INTEGER PRIMARY KEY,
  page_id       INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
  framework     TEXT NOT NULL,       -- denormalized for filtering w/o join
  breadcrumb    TEXT NOT NULL,       -- "Guide > Routing > Dynamic Segments"
  section_title TEXT,
  anchor        TEXT,                -- #dynamic-segments for deep links
  content       TEXT NOT NULL,       -- prose + fenced code kept intact
  ord           INTEGER NOT NULL     -- order within page
);

CREATE VIRTUAL TABLE chunks_fts USING fts5(
  breadcrumb, section_title, content,
  content='chunks', content_rowid='id',
  tokenize='porter unicode61'
);
-- + triggers to keep chunks_fts in sync on insert/update/delete
```

---

## MCP tool contract (v1)

- **`search_docs(query: str, framework: str | None = None, limit: int = 8)`**
  → list of results, each: `breadcrumb`, `snippet`, `source_url` (with `#anchor`),
  `framework`, `indexed_at`. Ranked by BM25. **Every result MUST cite source URL +
  index date.** This is the core trust feature — do not drop it.
- **`get_page(url: str)`** → page `title` + ordered section list
  (`section_title`, `breadcrumb`, `anchor`). Does **NOT** return the full page body
  (avoids blowing the client context window).
- **`get_section(url: str, section_title: str)`** → full content of one section.

---

## Milestones & checklists

Each milestone has an **exit criterion**. Do not proceed until it is green.
Run the full quality gate (`ruff check . && ruff format --check . && pytest`)
before checking a milestone's final box.

### M0 — Repo scaffold ✅
- [x] `pyproject.toml` with project metadata, `docwarden` script entrypoint → `docwarden.cli:main`, and deps.
- [x] `.gitignore` (ignore `data/`, `.venv/`, `__pycache__/`, `*.db`).
- [x] `src/docwarden/__init__.py` with `__version__`.
- [x] `store.py`: XDG path resolution (`~/.local/share/docwarden/`, honor `$DOCWARDEN_DATA_DIR` override for tests), `get_connection()`, `init_schema()`.
- [x] Confirm bundled SQLite has FTS5; fail loudly with a clear message if not.
- [x] `server.py`: stdio MCP server with all three tools wired.
- [x] `uv run docwarden --help` works.
- **Exit:** ✅ `uv sync` succeeds; CLI starts; `pytest` collects and passes.

### M1 — Recipe layer ✅
- [x] `recipes/__init__.py`: pydantic `Recipe` model with full validation.
- [x] Loader reads all `recipes/*.yaml`, validates, returns them; clear error on malformed recipe.
- [x] `fastapi.yaml`, `react.yaml`, `nextjs.yaml` authored and validated.
- [x] `test_recipes.py`: all recipes load; unknown type rejected; missing url/path caught.
- **Exit:** ✅ `load_recipes()` returns all 3 recipes; tests green.

### M2 — Vertical slice on FastAPI (the "does it work" proof) ⭐ ✅
This is the highest-priority milestone. Get one framework fully working end-to-end
before adding breadth.
- [x] `crawler.py`: sitemap fetch (httpx), glob filtering, dedupe, concurrency cap, rate limit, `robots.txt`, User-Agent. `type: local` walks markdown.
- [x] `parser.py`: select `content_selector`, strip noise, walk DOM preserving headings + fenced code, emit ordered sections.
- [x] `chunker.py`: split on headings; code stays with intro prose; breadcrumb on all chunks; overflow splits on paragraphs.
- [x] `indexer.py`: upsert page (skip unchanged hash), replace chunks, FTS stays in sync via triggers.
- [x] All three MCP tools wired into `server.py`.
- [x] `cli.py`: `index` command runs the pipeline.
- [x] Offline tests for parser, chunker, indexer, and all three tools via `test_search.py`.
- **Exit:** ✅ `docwarden index fastapi` populates the DB; tests confirm search + get_page + get_section work with source URL + indexed_at. Real-client checkpoint pending M6.

### M3 — Chunker hardening (quality pass) ✅
- [x] `test_chunker.py`: 12 tests covering all cases — code+intro stays together, oversized splits sanely, breadcrumb on all chunks, nested headings, empty/whitespace dropped.
- [x] Adversarial fixtures: deep nesting, huge code block (200 lines), tables, multiple code blocks.
- **Exit:** ✅ All 12 chunker tests pass. Real-corpus spot-check pending first live index run.

### M4 — Remaining tools ✅
- [x] `get_page(url)` → section list only (no full body); verified in tests.
- [x] `get_section(url, section_title)` → single section content; graceful "not found".
- [x] All three tools registered with clear schemas and descriptions.
- [x] `test_search.py`: 10 tests cover all three tools including edge cases.
- **Exit:** ✅ All tools tested and passing.

### M5 — Catalog breadth ✅
- [x] `nextjs.yaml` and `react.yaml` authored and validated.
- [x] All three recipes load and validate via `test_recipes.py`.
- [x] Parser/chunker are generic — zero per-framework code branches.
- **Exit:** ✅ All 3 recipes pass validation. Live indexing pending (requires network).

### M6 — CLI & install flow ✅
- [x] `clients.py`: write/merge MCP config for Claude Desktop, Cursor, VS Code (per-OS paths; merge, never clobber existing servers).
- [x] `cli.py`: `list`, `index`, `install [--client ...]`, `run` all implemented.
- [x] `test_clients.py`: 7 tests — config written correctly, existing servers preserved, parent dirs created.
- [ ] **Real-client checkpoint:** install into Claude Desktop, index fastapi, ask a FastAPI question → grounded answer with working source link. ← **TODO: do this manually.**
- **Exit:** ⏳ CLI and config writing tested. Real-client checkpoint needs manual verification.

### M7 — Recipe rot protection & release
- [x] `tests/canary/test_recipes_live.py`: network-gated (skipped unless `RUN_CANARY=1`); per-recipe canary with marker assertion and clear failure message.
- [ ] CI workflow: quality gate on PRs; scheduled canary run (daily/weekly).
- [x] `README.md`: install, usage, tools documented.
- [ ] Verify `uvx docwarden` works from a clean environment (requires PyPI publish).
- **Exit:** ⏳ Canary code written; CI workflow and PyPI publish remaining.

---

## Dependencies

Runtime: `mcp`, `httpx`, `selectolax` (fallback `beautifulsoup4` if a recipe needs
it), `pydantic`, `pyyaml`. (`sqlite3` is stdlib.)
Dev: `pytest`, `pytest-asyncio`, `ruff`.

---

## Non-goals (do not build in v1)
General web search · browser automation · cloud hosting · multi-version indexing ·
embeddings/semantic search · `summarize_topic` (the client's model summarizes).

---

## Risk register
- **Chunking quality** — the make-or-break. Over-invest in M2/M3 tests. Bad chunks = untrusted tool = uninstalled.
- **Recipe rot** — sites redesign silently. M7 canaries are the safety net; keep the catalog small (3) until they exist.
- **Context bloat** — never let `get_page` dump full bodies; keep tool count at 3.
- **First-run crawl latency** — index only selected frameworks; show progress.
- **Politeness** — rate-limit + robots.txt are non-negotiable; we crawl others' sites.
