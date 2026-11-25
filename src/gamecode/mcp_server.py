"""mcp_server.py - tiny MCP server over stdio (JSON-RPC 2.0, one JSON per line)."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

PROTOCOL_VERSION = "2024-11-05"
SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+\.md$")

READ_ONLY_TOOLS = {"list_outputs", "read_output"}

TOOLS = [
    {
        "name": "list_outputs",
        "description": "List the .md files saved in the workspace.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read_output",
        "description": "Read one .md file from the workspace by name.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
    {
        "name": "write_markdown",
        "description": "Write a .md file into the workspace (name must end in .md).",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}, "content": {"type": "string"}},
            "required": ["name", "content"],
        },
    },
]


def call_tool(name: str, args: dict, root: Path) -> tuple[str, bool]:
    """Returns (text, is_error)."""
    root.mkdir(parents=True, exist_ok=True)
    if name == "list_outputs":
        files = sorted(p.name for p in root.glob("*.md"))
        return ("\n".join(files) if files else "(no files yet)"), False
    if name in ("read_output", "write_markdown"):
        fname = str(args.get("name", ""))
        if not SAFE_NAME.match(fname):
            return "Invalid name: use a flat file name ending in .md", True
        path = root / fname
        if name == "read_output":
            if not path.is_file():
                return f"Not found: {fname}", True
            return path.read_text(encoding="utf-8"), False
        content = str(args.get("content", ""))
        path.write_text(content, encoding="utf-8")
        return f"Wrote {fname} ({len(content)} characters)", False
    return f"Unknown tool: {name}", True


def handle_message(msg: dict, root: Path) -> dict | None:
    method = msg.get("method")
    msg_id = msg.get("id")
    if msg_id is None:  # notification: no reply
        return None

    def ok(result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    if method == "initialize":
        return ok({
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "gamecode-workspace", "version": "0.1.0"},
        })
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        text, is_error = call_tool(
            str(params.get("name", "")), params.get("arguments") or {}, root
        )
        return ok({"content": [{"type": "text", "text": text}], "isError": is_error})
    return {
        "jsonrpc": "2.0",
        "id": msg_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def default_workspace() -> Path:
    env = os.getenv("GAMECODE_WORKSPACE")
    if env:
        return Path(env)
    return Path(os.getenv("GAMECODE_HOME") or ".") / "workspace"


def main() -> None:
    root = default_workspace()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        reply = handle_message(msg, root)
        if reply is not None:
            sys.stdout.write(json.dumps(reply) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()