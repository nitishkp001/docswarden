"""Test MCP config writing — always into temp dirs, never real paths."""

import json

from docwarden.clients import _merge_claude, _merge_cursor, _merge_vscode


def test_claude_config_written(tmp_path):
    config_path = tmp_path / "claude_desktop_config.json"
    _merge_claude(config_path)
    data = json.loads(config_path.read_text())
    assert "docwarden" in data["mcpServers"]
    assert data["mcpServers"]["docwarden"]["command"] == "uvx"


def test_claude_config_preserves_existing_servers(tmp_path):
    config_path = tmp_path / "claude_desktop_config.json"
    existing = {"mcpServers": {"other-tool": {"command": "npx", "args": ["other"]}}}
    config_path.write_text(json.dumps(existing))
    _merge_claude(config_path)
    data = json.loads(config_path.read_text())
    assert "other-tool" in data["mcpServers"]
    assert "docwarden" in data["mcpServers"]


def test_cursor_config_written(tmp_path):
    config_path = tmp_path / "mcp.json"
    _merge_cursor(config_path)
    data = json.loads(config_path.read_text())
    assert "docwarden" in data["mcpServers"]


def test_cursor_config_preserves_existing(tmp_path):
    config_path = tmp_path / "mcp.json"
    existing = {"mcpServers": {"existing": {"command": "node", "args": []}}}
    config_path.write_text(json.dumps(existing))
    _merge_cursor(config_path)
    data = json.loads(config_path.read_text())
    assert "existing" in data["mcpServers"]
    assert "docwarden" in data["mcpServers"]


def test_vscode_config_written(tmp_path):
    config_path = tmp_path / "settings.json"
    _merge_vscode(config_path)
    data = json.loads(config_path.read_text())
    assert "docwarden" in data["mcp"]["servers"]


def test_vscode_config_preserves_other_settings(tmp_path):
    config_path = tmp_path / "settings.json"
    existing = {"editor.fontSize": 14, "mcp": {"servers": {"existing": {"command": "node"}}}}
    config_path.write_text(json.dumps(existing))
    _merge_vscode(config_path)
    data = json.loads(config_path.read_text())
    assert data["editor.fontSize"] == 14
    assert "existing" in data["mcp"]["servers"]
    assert "docwarden" in data["mcp"]["servers"]


def test_parent_dirs_created(tmp_path):
    config_path = tmp_path / "nested" / "dir" / "claude_desktop_config.json"
    _merge_claude(config_path)
    assert config_path.exists()
