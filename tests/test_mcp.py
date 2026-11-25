"""Tests for the MCP config loader."""
import json
from pathlib import Path

from gamecode.mcp import load_mcp_servers


def test_missing_file_returns_empty(tmp_path):
    assert load_mcp_servers(tmp_path / "nope.json") == []


def test_parses_servers(tmp_path):
    f = tmp_path / "mcp.json"
    f.write_text(json.dumps({"mcpServers": {"demo": {"command": "npx", "args": ["-y", "pkg"]}}}))
    servers = load_mcp_servers(f)
    assert len(servers) == 1
    assert servers[0].name == "demo"
    assert servers[0].command == "npx"
    assert servers[0].args == ("-y", "pkg")
    assert servers[0].enabled is True


def test_skips_bad_entries_and_bad_json(tmp_path):
    f = tmp_path / "mcp.json"
    f.write_text(json.dumps({"mcpServers": {"bad": {"args": []}, "worse": 5}}))
    assert load_mcp_servers(f) == []
    f.write_text("not json")
    assert load_mcp_servers(f) == []


def test_real_project_config_loads():
    root = Path(__file__).resolve().parent.parent
    assert len(load_mcp_servers(root / "mcp.json")) >= 1