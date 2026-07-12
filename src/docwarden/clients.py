"""Write MCP server config for Claude Desktop, Cursor, and VS Code."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SUPPORTED_CLIENTS = ("claude", "cursor", "vscode")

_SERVER_ENTRY = {
    "command": "uvx",
    "args": ["docwarden", "run"],
}


def _claude_config_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Claude/claude_desktop_config.json"
    if sys.platform == "win32":
        import os

        return Path(os.environ["APPDATA"]) / "Claude/claude_desktop_config.json"
    return Path.home() / ".config/claude/claude_desktop_config.json"


def _cursor_config_path() -> Path:
    _cursor_rel = "Cursor/User/globalStorage/anysphere.cursor-mcp/mcp.json"
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support" / _cursor_rel
    if sys.platform == "win32":
        import os

        return Path(os.environ["APPDATA"]) / _cursor_rel
    return Path.home() / ".config/cursor/mcp.json"


def _vscode_config_path() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/Code/User/settings.json"
    if sys.platform == "win32":
        import os

        return Path(os.environ["APPDATA"]) / "Code/User/settings.json"
    return Path.home() / ".config/Code/User/settings.json"


def _merge_claude(path: Path) -> None:
    config: dict = {}
    if path.exists():
        try:
            config = json.loads(path.read_text())
        except Exception:
            pass
    servers = config.setdefault("mcpServers", {})
    servers["docwarden"] = _SERVER_ENTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
    print(f"  Claude Desktop config updated: {path}")


def _merge_cursor(path: Path) -> None:
    config: dict = {}
    if path.exists():
        try:
            config = json.loads(path.read_text())
        except Exception:
            pass
    servers = config.setdefault("mcpServers", {})
    servers["docwarden"] = _SERVER_ENTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
    print(f"  Cursor config updated: {path}")


def _merge_vscode(path: Path) -> None:
    config: dict = {}
    if path.exists():
        try:
            config = json.loads(path.read_text())
        except Exception:
            pass
    servers = config.setdefault("mcp", {}).setdefault("servers", {})
    servers["docwarden"] = _SERVER_ENTRY
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2))
    print(f"  VS Code config updated: {path}")


def install_client(client: str) -> None:
    if client == "claude":
        _merge_claude(_claude_config_path())
    elif client == "cursor":
        _merge_cursor(_cursor_config_path())
    elif client == "vscode":
        _merge_vscode(_vscode_config_path())
    else:
        raise ValueError(f"Unknown client: {client}")


def install_all() -> None:
    print("Installing docwarden into all supported MCP clients...\n")
    for client in SUPPORTED_CLIENTS:
        try:
            install_client(client)
        except Exception as exc:
            print(f"  [{client}] skipped: {exc}")

    print("\nAlternatively, add this to any MCP client config manually:")
    print(json.dumps({"mcpServers": {"docwarden": _SERVER_ENTRY}}, indent=2))
