"""mcp_client.py - minimal MCP client over stdio (launches a server subprocess)."""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import time


class McpError(Exception):
    """Raised when the MCP server fails, hangs or closes."""


class McpClient:
    def __init__(self, command: list[str], env: dict | None = None, timeout: float = 10.0):
        self.command = list(command)
        self.env = env
        self.timeout = timeout
        self._proc: subprocess.Popen | None = None
        self._lines: queue.Queue = queue.Queue()
        self._next_id = 0

    def __enter__(self) -> "McpClient":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- lifecycle -------------------------------------------------------
    def start(self) -> None:
        env = dict(os.environ)
        if self.env:
            env.update(self.env)
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        threading.Thread(target=self._read_loop, args=(self._proc,), daemon=True).start()
        try:
            self._request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "gamecode", "version": "0.1.0"},
                },
            )
            self._notify("notifications/initialized")
        except McpError:
            self.close()
            raise

    def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()

    # ---- public API ------------------------------------------------------
    def list_tools(self) -> list[dict]:
        return self._request("tools/list").get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None) -> tuple[str, bool]:
        result = self._request("tools/call", {"name": name, "arguments": arguments or {}})
        text = "\n".join(
            c.get("text", "") for c in result.get("content", []) if c.get("type") == "text"
        )
        return text, bool(result.get("isError", False))

    # ---- internals -------------------------------------------------------
    def _read_loop(self, proc: subprocess.Popen) -> None:
        try:
            for line in proc.stdout:
                self._lines.put(line)
        except (OSError, ValueError):
            pass
        finally:
            self._lines.put(None)

    def _send(self, obj: dict) -> None:
        if self._proc is None or self._proc.stdin is None:
            raise McpError("MCP server is not running")
        try:
            self._proc.stdin.write(json.dumps(obj) + "\n")
            self._proc.stdin.flush()
        except (OSError, ValueError) as e:
            raise McpError(f"Could not talk to MCP server: {e}") from e

    def _notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def _request(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        req_id = self._next_id
        msg: dict = {"jsonrpc": "2.0", "id": req_id, "method": method}
        if params is not None:
            msg["params"] = params
        self._send(msg)

        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise McpError(f"Timed out waiting for {method}")
            try:
                line = self._lines.get(timeout=remaining)
            except queue.Empty:
                raise McpError(f"Timed out waiting for {method}") from None
            if line is None:
                raise McpError("MCP server closed unexpectedly")
            try:
                reply = json.loads(line)
            except json.JSONDecodeError:
                continue
            if reply.get("id") != req_id:
                continue
            if "error" in reply:
                err = reply["error"]
                raise McpError(str(err.get("message", err)) if isinstance(err, dict) else str(err))
            return reply.get("result") or {}