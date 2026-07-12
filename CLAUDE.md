# CLAUDE.md

Guidance for Claude Code (and other agents) working in this repository.

## What this project is

**FrameworkDocs MCP** — a local-first Model Context Protocol server that indexes a
curated set of framework docs (React, Next.js, FastAPI in v1) into a local SQLite
FTS5 index and exposes search/retrieval tools to MCP clients.

**The recipes are the product.** Generic crawl/parse/chunk machinery + a curated,
tested set of per-framework YAML recipes. When in doubt, invest effort in recipe
quality and chunking, not features.

Read [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) for the roadmap and
milestone checklists, and [`AGENTS.md`](./AGENTS.md) for conventions and the
testing contract. Work milestones in order; honor their exit criteria.

## Locked decisions (do not relitigate without being asked)

- FTS5 + BM25 only — **no embeddings / no ML model** in v1.
- v1 catalog: React, Next.js, FastAPI.
- Packaging: `uv` / `uvx`, entrypoint `frameworkdocs-mcp`.
- MCP tools: `search_docs`, `get_page`, `get_section` — only these three.
- Runtime data lives in the XDG dir, **never** committed to the repo.
- Deferred to Phase 2: semantic search, versioning, incremental recrawl, `summarize_topic`.

## Environment & commands

- Python **3.12**, package/deps via **`uv`**.
- `uv sync` — install deps.
- `uv run frameworkdocs-mcp <cmd>` — run the CLI (`list`, `index`, `install`, `run`).
- `uv run pytest` — tests.
- `uv run ruff check . && uv run ruff format --check .` — lint + format.

**Quality gate (must pass before marking any milestone done):**
```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

## Conventions

- Source under `src/frameworkdocs_mcp/`. One responsibility per module (see the
  layout in the plan). Don't merge crawler/parser/chunker concerns.
- Use `pathlib`, type hints everywhere, `pydantic` for external data (recipes).
- Network access lives **only** in `crawler.py`. Parser/chunker/indexer are pure
  and offline-testable against saved HTML fixtures.
- All runtime paths go through `store.py`; honor `$FRAMEWORKDOCS_DATA_DIR` so tests
  never touch the real user data dir.
- **Every `search_docs` result must carry its source URL and `indexed_at`.** This
  is the product's trust guarantee — never strip it.
- Be a polite crawler: rate-limit, respect `robots.txt`, set a real User-Agent.

## Guardrails

- Don't add dependencies beyond those in the plan without flagging it first.
- Don't commit anything under `data/` or any `*.db`.
- Don't expand the tool surface or the catalog beyond the locked list without being
  asked — scope creep is the main risk here.
- `get_page` must never return full page bodies (context-window bloat).

## Definition of done for a change

1. Code + tests written; new logic has offline tests (fixtures, not live network).
2. Quality gate green.
3. Relevant checkbox(es) in `IMPLEMENTATION_PLAN.md` ticked.
4. If behavior changed, the change is verified end-to-end (see `AGENTS.md` →
   Testing), not just via unit tests.
