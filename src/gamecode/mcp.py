"""mcp.py - reads MCP server definitions from mcp.json (config only)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class McpServer:
    name: str
    command: str
    args: tuple[str, ...] = ()
    enabled: bool = True


def load_mcp_servers(path: Path | str) -> list[McpServer]:
    p = Path(path)
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw = data.get("mcpServers") if isinstance(data, dict) else None
    if not isinstance(raw, dict):
        return []
    servers: list[McpServer] = []
    for name, cfg in raw.items():
        if not isinstance(cfg, dict) or not isinstance(cfg.get("command"), str):
            continue
        args = cfg.get("args", [])
        if not isinstance(args, list):
            args = []
        servers.append(
            McpServer(
                name=str(name),
                command=cfg["command"],
                args=tuple(str(a) for a in args),
                enabled=bool(cfg.get("enabled", True)),
            )
        )
    return servers