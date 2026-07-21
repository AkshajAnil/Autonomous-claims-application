import asyncio
import json
import sys
from pathlib import Path
from typing import Any


class McpClient:
    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0

    async def __aenter__(self) -> "McpClient":
        backend_dir = Path(__file__).resolve().parents[1]
        self._process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.mcp_server",
            cwd=str(backend_dir),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await self._send("initialize", {"protocolVersion": "2024-11-05", "clientInfo": {"name": "claims-agent-fastapi", "version": "0.1.0"}})
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._process:
            self._process.terminate()
            await self._process.wait()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        response = await self._send("tools/call", {"name": name, "arguments": arguments})
        content = response["result"]["content"][0]["text"]
        return json.loads(content)

    async def _send(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        if not self._process or not self._process.stdin or not self._process.stdout:
            raise RuntimeError("MCP process is not running")
        self._request_id += 1
        payload = {"jsonrpc": "2.0", "id": self._request_id, "method": method, "params": params}
        self._process.stdin.write((json.dumps(payload) + "\n").encode("utf-8"))
        await self._process.stdin.drain()
        raw = await self._process.stdout.readline()
        if not raw:
            err = b""
            if self._process.stderr:
                err = await self._process.stderr.read()
            raise RuntimeError(f"MCP server stopped unexpectedly: {err.decode('utf-8', errors='ignore')}")
        response = json.loads(raw.decode("utf-8"))
        if "error" in response:
            raise RuntimeError(response["error"])
        return response
