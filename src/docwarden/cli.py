"""CLI entry point: docwarden list / index / install / run."""

import asyncio
import sys

from .store import get_connection, init_schema


def main() -> None:
    args = sys.argv[1:]
    cmd = args[0] if args else "run"

    if cmd == "run":
        _cmd_run()
    elif cmd == "list":
        _cmd_list()
    elif cmd == "index":
        _cmd_index(args[1:])
    elif cmd == "install":
        _cmd_install(args[1:])
    elif cmd in ("--help", "-h", "help"):
        _print_help()
    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        _print_help()
        sys.exit(1)


def _cmd_run() -> None:
    from .server import serve

    asyncio.run(serve())


def _cmd_list() -> None:
    from .recipes import load_recipes

    recipes = load_recipes()
    conn = get_connection()
    init_schema(conn)
    print(f"{'Framework':<20} {'Status':<15} {'Indexed at'}")
    print("-" * 55)
    for r in recipes:
        row = conn.execute(
            "SELECT MAX(indexed_at) as last FROM pages WHERE framework = ?",
            (r.id,),
        ).fetchone()
        last = row["last"] if row and row["last"] else "not indexed"
        print(f"{r.name:<20} {'indexed' if row and row['last'] else 'pending':<15} {last}")
    conn.close()


def _cmd_index(names: list[str]) -> None:
    from .indexer import index_recipe
    from .recipes import load_recipes

    recipes = load_recipes()
    recipe_map = {r.id: r for r in recipes}

    if not names:
        print("Available frameworks:")
        for r in recipes:
            print(f"  {r.id:<20} {r.name}")
        print("\nUsage: docwarden index <framework> [<framework> ...]")
        print("Example: docwarden index fastapi react")
        return

    for name in names:
        if name not in recipe_map:
            print(
                f"Unknown framework: {name}. Run 'docwarden list' to see options.", file=sys.stderr
            )
            continue
        recipe = recipe_map[name]
        print(f"Indexing {recipe.name}...")
        asyncio.run(index_recipe(recipe))
        print(f"Done: {recipe.name}")


def _cmd_install(args: list[str]) -> None:
    from .clients import SUPPORTED_CLIENTS, install_all, install_client

    client = None
    for i, a in enumerate(args):
        if a in ("--client", "-c") and i + 1 < len(args):
            client = args[i + 1]

    if client:
        if client not in SUPPORTED_CLIENTS:
            print(
                f"Unknown client: {client}. Supported: {', '.join(SUPPORTED_CLIENTS)}",
                file=sys.stderr,
            )
            sys.exit(1)
        install_client(client)
    else:
        install_all()


def _print_help() -> None:
    print("""docwarden — local framework docs for your AI

Commands:
  run                  Start the MCP server (default)
  list                 Show catalog and index status
  index <name> ...     Crawl and index one or more frameworks
  install [--client <name>]
                       Write MCP config (claude|cursor|vscode) or print snippet

Examples:
  docwarden index fastapi react
  docwarden install --client claude
  docwarden run
""")
