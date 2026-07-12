# AGENTS.md

Conventions and the **testing contract** for agents contributing to FrameworkDocs
MCP. This is the file agent tooling auto-discovers; it also serves as the
"agent.md" contributor guide. Pair it with [`CLAUDE.md`](./CLAUDE.md) (how to work
here) and [`IMPLEMENTATION_PLAN.md`](./IMPLEMENTATION_PLAN.md) (what to build).

---

## Roles this repo expects of an agent

1. **Implementer** — build a milestone from the plan, in order, honoring exit criteria.
2. **Recipe author** — add/repair a framework recipe (see "Adding a recipe").
3. **Reviewer/verifier** — run the quality gate and the end-to-end check before done.

Pick up the lowest unchecked milestone in `IMPLEMENTATION_PLAN.md` unless told
otherwise. Do not start a milestone whose predecessor's exit criterion is unmet.

---

## Project shape (quick reference)

```
crawler.py  -> parser.py -> chunker.py -> indexer.py -> server.py (MCP tools)
   ^ only module allowed to do network I/O
recipes.py  -> loads/validates recipes/*.yaml   (the product)
store.py    -> XDG paths + SQLite schema         (all paths go through here)
cli.py      -> list / index / install / run
clients.py  -> writes MCP config for Claude Desktop / Cursor / VS Code
```

Purity rule: **parser, chunker, indexer are pure and offline.** They must be
testable without the network, using saved HTML fixtures. Keep it that way — it is
what makes this codebase fast and reliable to test.

---

## Coding conventions

- Python 3.12, `uv` for everything. Type hints on all public functions.
- `pydantic` for anything parsed from disk/network (recipes).
- `pathlib` over `os.path`. No hard-coded paths — go through `store.py`.
- Keep modules single-purpose; do not blur pipeline stages.
- Lint/format with `ruff`. No warnings in the gate.

---

## Testing contract

Testing is a first-class deliverable, **not** an afterthought. A milestone is not
"done" until its tests exist and pass.

### Test layout

```
tests/
├── conftest.py                  # shared fixtures: temp data dir, in-memory DB, sample recipes
├── fixtures/                    # saved HTML pages + expected chunk snapshots
├── test_recipes.py              # recipe schema validation
├── test_parser.py               # HTML -> sections (offline, fixture-driven)
├── test_chunker.py              # sections -> chunks (the critical suite)
├── test_indexer.py              # SQLite/FTS write + query
├── test_search.py               # end-to-end: index a fixture, assert search results
├── test_clients.py              # MCP config writing/merging into a temp dir
└── canary/
    └── test_recipes_live.py     # network-gated; RUN_CANARY=1 to enable
```

### The layered strategy

1. **Unit (offline, default)** — parser, chunker, indexer, recipes, clients. Fast,
   deterministic, no network. This is the bulk of the suite and must always run.
2. **Integration (offline)** — `test_search.py`: feed a saved HTML fixture through
   the full pipeline into an in-memory SQLite DB and assert `search_docs` /
   `get_page` / `get_section` return the right chunk with source URL + `indexed_at`.
3. **Canary (live, gated)** — `test_recipes_live.py`: only runs when `RUN_CANARY=1`.
   For each shipped recipe, crawl **one** known page and assert extracted content
   contains an expected marker string (e.g. React's `useState` page contains
   "Returns"). This catches site redesigns before users do. Runs on a schedule in
   CI, never in the normal PR gate.

### What MUST be tested per stage

- **recipes** — every shipped recipe loads + validates; unknown `source.type` rejected; bad YAML fails clearly.
- **parser** — nav/footer/script stripped; heading hierarchy preserved; fenced code blocks preserved intact; anchors captured.
- **chunker** (highest priority — retrieval quality lives here):
  - a code block stays attached to its introducing paragraph;
  - every chunk carries the full heading breadcrumb;
  - oversized sections split on paragraph boundaries, breadcrumb repeated;
  - nested headings produce correct breadcrumbs;
  - empty/whitespace-only sections are dropped.
  Include ≥3 adversarial fixtures (deep nesting, huge code block, tables).
- **indexer** — upsert skips unchanged `content_hash`; re-index replaces a page's chunks; FTS stays in sync; BM25 ordering sane.
- **search/tools** — known query returns expected chunk; results include source URL + index date; `get_page` returns section list only (never full body); `get_section` handles not-found gracefully.
- **clients** — config written to a temp dir matches expected JSON; existing MCP servers preserved on merge (never clobbered).

### Fixtures

- Save real HTML snapshots under `tests/fixtures/<framework>/<page>.html` so parser
  and chunker tests are deterministic and offline.
- When a chunker behavior is subtle, snapshot the expected chunks and assert
  against the snapshot; update deliberately when logic changes.
- Never hit the live network in unit/integration tests. Live access is canary-only.

### Determinism & isolation

- Tests must not touch the real user data dir — `conftest.py` sets
  `$FRAMEWORKDOCS_DATA_DIR` to a `tmp_path` and/or uses an in-memory SQLite DB.
- No test depends on wall-clock time except via injected/frozen `indexed_at`.
- Async crawler tested with `pytest-asyncio`; mock HTTP (e.g. httpx transport) —
  no real requests outside the canary.

---

## Commands

```bash
uv sync                                   # install
uv run pytest                             # unit + integration (offline)
RUN_CANARY=1 uv run pytest tests/canary   # live recipe canary (network)
uv run ruff check . && uv run ruff format --check .

# Full quality gate — must pass before marking a milestone done:
uv run ruff check . && uv run ruff format --check . && uv run pytest
```

---

## End-to-end verification (before calling a feature done)

Unit tests are necessary but not sufficient. For any change touching the pipeline
or tools, drive it for real:

1. `uv run frameworkdocs-mcp index fastapi` — pipeline populates the DB.
2. `uv run frameworkdocs-mcp install --client claude` (or print the stdio snippet).
3. In the client, ask a real question (e.g. "FastAPI path parameters") and confirm
   a **grounded answer with a working source link and index date**.

If the answer isn't grounded or the link is wrong, the chunker/recipe needs work —
that is the real signal, above green unit tests.

---

## Adding a recipe (contribution path)

1. Create `src/frameworkdocs_mcp/recipes/<name>.yaml` (copy an existing one).
2. Set `source` (sitemap/crawl/github/local), `include`/`exclude`, and the
   `parser.content_selector` that isolates the main content from site chrome.
3. Add a fixture page under `tests/fixtures/<name>/` and a parser/chunker assertion.
4. Add a canary marker in `test_recipes_live.py` (a known page + expected string).
5. Run the gate; index it; spot-check 10 chunks for coherence.

Keep the official catalog small and battle-tested. 3 recipes that always work beat
10 where a third return junk.

---

## Definition of done

- [ ] Code + offline tests written; critical logic covered per the contract above.
- [ ] Quality gate green.
- [ ] End-to-end verification performed for pipeline/tool changes.
- [ ] Milestone checkbox(es) ticked in `IMPLEMENTATION_PLAN.md`.
- [ ] No new deps, tools, or catalog entries beyond the plan (unless asked).
- [ ] Nothing under `data/` or any `*.db` committed.
