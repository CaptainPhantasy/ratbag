"""Talk to the SDLC factory over its stdio MCP protocol.

RATBAG is the front end; the factory holds the lifecycle. This module is the
seam: one request at a time, one session at a time, and every call returns the
factory's own answer rather than a paraphrase.
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import threading
import time
from typing import Any


DEFAULT_COMMAND = "/srv/organized/services/MCP_SERVER_ROOM/.mcp-runtime/sdlc-core-cloud-factory-mcp/bin/sdlc-core-cloud-factory-mcp"


class SdlcError(RuntimeError):
    """The factory refused, failed, or could not be reached."""


class SdlcClient:
    """A minimal MCP client: initialize, then call tools by name."""

    def __init__(self, command: str | None = None, timeout: float = 120.0):
        self.command = command or os.getenv("RATBAG_SDLC_COMMAND", DEFAULT_COMMAND)
        self.timeout = timeout
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._next_id = 0

    def __enter__(self) -> "SdlcClient":
        self.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def start(self) -> None:
        if self._process is not None:
            return
        try:
            argv = shlex.split(self.command)
        except ValueError as exc:
            raise SdlcError(f"The factory command is not valid: {exc}") from exc
        try:
            self._process = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise SdlcError(
                f"The SDLC factory could not be started from {self.command}: {exc}. "
                "Set RATBAG_SDLC_COMMAND to the factory's executable."
            ) from exc
        self._request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ratbag", "version": "0.2.0"},
            },
        )
        self._notify("notifications/initialized", {})

    def close(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            process.kill()

    # ---------------------------------------------------------------- transport

    def _send(self, payload: dict[str, Any]) -> None:
        if self._process is None or self._process.stdin is None:
            raise SdlcError("The SDLC factory is not running.")
        self._process.stdin.write(json.dumps(payload) + "\n")
        self._process.stdin.flush()

    def _notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def _request(self, method: str, params: dict[str, Any]) -> Any:
        if self._process is None or self._process.stdout is None:
            raise SdlcError("The SDLC factory is not running.")
        with self._lock:
            self._next_id += 1
            request_id = self._next_id
            self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            deadline = time.monotonic() + self.timeout
            while True:
                if time.monotonic() > deadline:
                    raise SdlcError(f"The SDLC factory did not answer {method} within {self.timeout:.0f} seconds.")
                line = self._process.stdout.readline()
                if line == "":
                    raise SdlcError("The SDLC factory stopped answering; it may have exited.")
                line = line.strip()
                if not line.startswith("{"):
                    continue
                try:
                    message = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    error = message["error"]
                    raise SdlcError(str(error.get("message") or error))
                return message.get("result")

    # ------------------------------------------------------------------- calls

    def call(self, tool: str, **arguments: Any) -> dict[str, Any]:
        result = self._request("tools/call", {"name": tool, "arguments": arguments})
        if not isinstance(result, dict):
            raise SdlcError(f"The factory returned an unexpected answer for {tool}.")
        if result.get("isError"):
            raise SdlcError(self._text(result) or f"The factory reported an error for {tool}.")
        payload = result.get("structuredContent")
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise SdlcError(str(payload.get("message") or f"The factory refused {tool}."))
        content = result.get("content") or []
        for item in content:
            if item.get("type") == "text":
                text = item.get("text") or ""
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    return {"text": text}
                if isinstance(parsed, dict):
                    return parsed
        return result

    @staticmethod
    def _text(result: dict[str, Any]) -> str:
        for item in result.get("content") or []:
            if item.get("type") == "text":
                return str(item.get("text") or "")
        return ""

    def status(self) -> dict[str, Any]:
        """Report reachability without changing anything."""
        try:
            self.start()
            return {"reachable": True, "command": self.command}
        except SdlcError as exc:
            return {"reachable": False, "command": self.command, "reason": str(exc)}
