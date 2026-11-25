"""End-to-end tests: real MCP client talking to the real MCP server process."""
import sys
from pathlib import Path

import pytest

from gamecode.mcp_client import McpClient, McpError

SRC = Path(__file__).resolve().parent.parent / "src"


def _client(tmp_path) -> McpClient:
    return McpClient(
        [sys.executable, "-m", "gamecode.mcp_server"],
        env={"PYTHONPATH": str(SRC), "GAMECODE_WORKSPACE": str(tmp_path)},
        timeout=15,
    )


def test_list_tools_and_roundtrip(tmp_path):
    with _client(tmp_path) as c:
        names = {t["name"] for t in c.list_tools()}
        assert names == {"list_outputs", "read_output", "write_markdown"}
        text, err = c.call_tool("write_markdown", {"name": "plan.md", "content": "# Plan"})
        assert not err and "plan.md" in text
        assert "plan.md" in c.call_tool("list_outputs")[0]
        assert c.call_tool("read_output", {"name": "plan.md"}) == ("# Plan", False)
    assert (tmp_path / "plan.md").read_text(encoding="utf-8") == "# Plan"


def test_bad_name_reports_error(tmp_path):
    with _client(tmp_path) as c:
        _, err = c.call_tool("write_markdown", {"name": "../evil.md", "content": "x"})
        assert err is True
    assert not list(tmp_path.glob("*"))


def test_dead_server_raises_mcp_error():
    client = McpClient([sys.executable, "-c", "pass"], timeout=5)
    with pytest.raises(McpError):
        client.start()