import json

import httpx

PROTOCOL_VERSION = "2025-11-25"


class MCPHttpClient:
    """Minimal MCP client over Streamable HTTP, written at the protocol level."""

    def __init__(self, url: str = "http://127.0.0.1:8000/mcp"):
        self.url = url
        self.http = httpx.Client(timeout=30.0)
        self.session_id = None
        self.protocol_version = PROTOCOL_VERSION
        self.initialized = False
        self._next_id = 1

    def _headers(self) -> dict:
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.initialized:
            h["MCP-Protocol-Version"] = self.protocol_version
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    @staticmethod
    def _parse(resp: httpx.Response) -> dict:
        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            last = None
            for line in resp.text.splitlines():
                if line.startswith("data:"):
                    payload = line[5:].strip()
                    if not payload:
                        continue
                    try:
                        msg = json.loads(payload)
                    except ValueError:
                        continue
                    if "result" in msg or "error" in msg:
                        last = msg
            if last is None:
                raise RuntimeError("No JSON-RPC response found in event stream")
            return last
        return resp.json()

    def _request(self, method: str, params: dict | None = None):
        body = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        self._next_id += 1
        if params is not None:
            body["params"] = params
        resp = self.http.post(self.url, json=body, headers=self._headers())
        resp.raise_for_status()
        return resp, self._parse(resp)

    def initialize(self) -> dict:
        self.initialized = False
        self.session_id = None
        resp, msg = self._request(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "extensions": {
                        "io.modelcontextprotocol/ui": {
                            "mimeTypes": ["text/html;profile=mcp-app"]
                        }
                    }
                },
                "clientInfo": {"name": "alexa-plus-simulator", "version": "0.1.0"},
            },
        )
        if "error" in msg:
            raise RuntimeError(f"initialize failed: {msg['error']}")
        result = msg["result"]
        self.protocol_version = result.get("protocolVersion", PROTOCOL_VERSION)
        self.session_id = resp.headers.get("mcp-session-id")
        self.initialized = True
        self.http.post(
            self.url,
            json={"jsonrpc": "2.0", "method": "notifications/initialized"},
            headers=self._headers(),
        )
        return result

    def _ensure(self) -> None:
        if not self.initialized:
            self.initialize()

    def list_tools(self) -> list:
        self._ensure()
        _, msg = self._request("tools/list")
        if "error" in msg:
            raise RuntimeError(f"tools/list failed: {msg['error']}")
        return msg["result"]["tools"]

    def read_resource(self, uri: str) -> str:
        self._ensure()
        _, msg = self._request("resources/read", {"uri": uri})
        if "error" in msg:
            raise RuntimeError(f"resources/read failed: {msg['error']}")
        contents = msg["result"].get("contents", [])
        return contents[0].get("text", "") if contents else ""

    def call_tool_full(self, name: str, arguments: dict | None = None) -> dict:
        self._ensure()
        _, msg = self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )
        if "error" in msg:
            raise RuntimeError(f"tools/call failed: {msg['error']}")
        return msg["result"]

    def _call(self, name: str, arguments: dict) -> str:
        self._ensure()
        _, msg = self._request("tools/call", {"name": name, "arguments": arguments})
        if "error" in msg:
            raise RuntimeError(f"tools/call failed: {msg['error']}")
        result = msg["result"]
        text = " ".join(
            c.get("text", "")
            for c in result.get("content", [])
            if c.get("type") == "text"
        ).strip()
        if result.get("isError"):
            raise RuntimeError(text or "Tool returned an error")
        return text

    def call_tool(self, name: str, arguments: dict | None = None) -> str:
        arguments = arguments or {}
        try:
            return self._call(name, arguments)
        except (httpx.HTTPError, RuntimeError, KeyError, ValueError):
            # The session may have expired: start a new one and try once more.
            self.initialized = False
            return self._call(name, arguments)