"""Tests for the tiny MCP server (called directly, no subprocess)."""
from gamecode.mcp_server import READ_ONLY_TOOLS, TOOLS, handle_message


def _call(root, method, params=None, msg_id=1):
    msg = {"jsonrpc": "2.0", "id": msg_id, "method": method}
    if params is not None:
        msg["params"] = params
    return handle_message(msg, root)


def _tool(root, tool, **args):
    r = _call(root, "tools/call", {"name": tool, "arguments": args})
    return r["result"]["content"][0]["text"], r["result"]["isError"]


def test_initialize(tmp_path):
    r = _call(tmp_path, "initialize", {})
    assert r["result"]["serverInfo"]["name"] == "gamecode-workspace"
    assert "tools" in r["result"]["capabilities"]


def test_notification_gets_no_reply(tmp_path):
    msg = {"jsonrpc": "2.0", "method": "notifications/initialized"}
    assert handle_message(msg, tmp_path) is None


def test_tools_list(tmp_path):
    names = {t["name"] for t in _call(tmp_path, "tools/list")["result"]["tools"]}
    assert names == {"list_outputs", "read_output", "write_markdown"}
    assert READ_ONLY_TOOLS <= names
    assert len(TOOLS) == 3


def test_write_list_read_roundtrip(tmp_path):
    text, err = _tool(tmp_path, "write_markdown", name="plan.md", content="# Plan")
    assert not err and "plan.md" in text
    assert "plan.md" in _tool(tmp_path, "list_outputs")[0]
    assert _tool(tmp_path, "read_output", name="plan.md") == ("# Plan", False)


def test_bad_names_rejected(tmp_path):
    for bad in ["../x.md", "a/b.md", "x.txt", "..\\x.md", ""]:
        _, err = _tool(tmp_path, "write_markdown", name=bad, content="x")
        assert err, bad
    assert not list(tmp_path.glob("*"))


def test_unknown_method_and_tool(tmp_path):
    assert _call(tmp_path, "nope")["error"]["code"] == -32601
    assert _tool(tmp_path, "rm_rf")[1] is True