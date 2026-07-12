# docwarden

Local-first MCP server that indexes framework documentation (React, Next.js, FastAPI) into a searchable SQLite index and exposes it to AI clients via MCP.

## Install

```bash
uvx docwarden install
```

## Usage

```bash
docwarden index fastapi react nextjs   # crawl & index
docwarden install --client claude      # write Claude Desktop config
docwarden run                          # start MCP server
```

## MCP tools

- `search_docs(query, framework?, limit?)` — ranked search with source URL + index date
- `get_page(url)` — section list for a page
- `get_section(url, section_title)` — full content of one section
