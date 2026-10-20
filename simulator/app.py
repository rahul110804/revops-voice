import json
import re
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from mcp_http import MCPHttpClient
from router import parse_companies, route

BASE = Path(__file__).parent
client = MCPHttpClient()

HELP = (
    "Sorry, I can help with your pipeline summary, stalled deals, "
    "logging a call, drafting a follow up, or showing the pipeline board."
)

CARD_TOOLS = {"pipeline_summary", "stalled_deals", "list_deals", "log_activity"}

UI_TOOLS = {}
_ui_loaded = False


def load_ui_map():
    """Find which tools carry an MCP Apps UI (_meta.ui.resourceUri)."""
    global _ui_loaded
    UI_TOOLS.clear()
    for t in client.list_tools():
        meta = t.get("_meta") or {}
        ui = meta.get("ui") or {}
        uri = ui.get("resourceUri") or meta.get("ui/resourceUri")
        if uri:
            UI_TOOLS[t["name"]] = uri
    _ui_loaded = True


def handle(text: str) -> dict:
    companies = parse_companies(client.call_tool("list_deals"))
    intent = route(text, companies)
    if intent is None:
        return {"reply": HELP, "tool": None, "args": {}, "card": None}
    tool, args = intent

    if not _ui_loaded:
        load_ui_map()
    if tool in UI_TOOLS:
        result = client.call_tool_full(tool, args)
        html = client.read_resource(UI_TOOLS[tool])
        return {
            "reply": "Here is your pipeline board.",
            "tool": tool,
            "args": args,
            "card": None,
            "app": {"uri": UI_TOOLS[tool], "html": html, "result": result},
        }

    reply = client.call_tool(tool, args)
    card = None
    if tool in CARD_TOOLS:
        try:
            card = json.loads(client.call_tool("pipeline_data"))
        except Exception:
            card = None
    return {"reply": reply, "tool": tool, "args": args, "card": card}


async def ask(request):
    data = await request.json()
    text = (data.get("text") or "").strip()
    text = re.sub(r"^\s*(hey\s+|ok\s+)?alexa[,.!]?\s*", "", text, flags=re.I)
    if not text:
        return JSONResponse(
            {"reply": "I didn't catch that.", "tool": None, "args": {}, "card": None}
        )
    try:
        return JSONResponse(await run_in_threadpool(handle, text))
    except Exception as e:
        return JSONResponse(
            {
                "reply": "I couldn't reach the RevOps service. Is the server running?",
                "tool": None,
                "args": {},
                "card": None,
                "error": str(e),
            }
        )


def _status() -> dict:
    info = client.initialize()
    tools = [t["name"] for t in client.list_tools()]
    load_ui_map()
    return {"ok": True, "protocol": info.get("protocolVersion"), "tools": tools}


async def status(request):
    try:
        return JSONResponse(await run_in_threadpool(_status))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


async def index(request):
    return FileResponse(BASE / "index.html")


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/ask", ask, methods=["POST"]),
        Route("/api/status", status),
    ]
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)