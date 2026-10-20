import csv
import datetime as dt
import io
import json
import re
import threading
import time
import uuid
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

import brain
from mcp_http import MCPHttpClient
from router import route

BASE = Path(__file__).parent
client = MCPHttpClient()

HELP = (
    "Sorry, I can help with your pipeline summary, stalled deals, "
    "logging a call, drafting a follow up, or showing the pipeline board."
)

CARD_TOOLS = {"pipeline_summary", "stalled_deals", "list_deals", "log_activity"}

UI_TOOLS = {}
_tools = []
_ui_loaded = False

MAX_UPLOAD_CHARS = 5 * 1024 * 1024
MAX_ROWS = 5000
MAX_COLUMNS = 60
UPLOADS = {}  # token -> {"table": dict, "filename": str, "ts": float}

SYNONYMS = {
    "company": ["account name", "company name", "company", "account", "customer",
                "client", "organization", "organisation", "deal name",
                "opportunity name", "lead name", "name"],
    "contact": ["primary contact", "contact name", "contact person", "contact",
                "person", "lead contact"],
    "stage": ["pipeline stage", "deal stage", "sales stage", "stage", "status", "phase"],
    "value": ["amount (inr)", "deal value", "deal amount", "opportunity amount",
              "expected revenue", "amount", "value", "revenue", "arr", "price"],
    "last_activity": ["last contacted", "last activity date", "last activity",
                      "last contact date", "last contact", "last touch",
                      "last modified", "last updated", "updated", "modified", "date"],
}
ALLOWED_MULTIPLIERS = {1, 1000, 100000, 10000000}

DATE_FORMATS = [
    "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y",
    "%b %d, %Y", "%B %d, %Y", "%Y/%m/%d", "%d/%m/%y", "%d-%m-%y",
    "%m/%d/%Y", "%m-%d-%Y",
]

# ---------------------------------------------------------------------------
# Conversation helpers: clarification memory and a guard against made-up notes
# ---------------------------------------------------------------------------
PENDING = {}
LOG_CUES = ("call", "spoke", "talked", "met ", "meeting", "email", "phone",
            "log ", "note", "discuss", "demo", "chat")


def note_supported(text: str, note: str) -> bool:
    """A note may only be logged if the user actually said it."""
    t = text.lower()
    if not any(cue in t for cue in LOG_CUES):
        return False
    words = re.findall(r"[a-z]{4,}", (note or "").lower())
    if not words:
        return False
    hits = sum(1 for w in words if w in t)
    return hits / len(words) >= 0.5


def resolve_pending(text: str, companies: list):
    """If the last answer asked 'Which one do you mean?', use this message as the answer."""
    p = PENDING.get("p")
    if not p or time.time() - p["ts"] > 120:
        return None
    t = text.lower()
    hits = [c for c in companies if c.lower() in t]
    if len(hits) == 1:
        args = dict(p["args"])
        args["company"] = hits[0]
        return p["tool"], args
    return None


def load_ui_map():
    """Cache the tool list and find which tools carry an MCP Apps UI."""
    global _ui_loaded, _tools
    _tools = client.list_tools()
    UI_TOOLS.clear()
    for t in _tools:
        meta = t.get("_meta") or {}
        ui = meta.get("ui") or {}
        uri = ui.get("resourceUri") or meta.get("ui/resourceUri")
        if uri:
            UI_TOOLS[t["name"]] = uri
    _ui_loaded = True


def choose_tool(text: str, companies: list):
    """Let the local model choose the tool; fall back to keyword rules."""
    if brain.status()["mode"] == "ollama":
        try:
            res = brain.plan(text, _tools)
        except Exception:
            res = None
        if res:
            name, args, cached = res
            if name == "log_activity" and not note_supported(text, str(args.get("note", ""))):
                res = None  # the model made up a note: log nothing
            else:
                label = f"{brain.MODEL} (Ollama, local{', cached' if cached else ''})"
                return (name, args), label
        fallback = route(text, companies)
        if fallback:
            return fallback, "keyword rules (model gave no usable tool)"
        return None, "no match"
    return route(text, companies), "keyword rules"


def handle(text: str) -> dict:
    t0 = time.time()
    if not _ui_loaded:
        load_ui_map()
    companies = json.loads(client.call_tool("company_names"))

    pending = resolve_pending(text, companies)
    if pending:
        intent, routed_by = pending, "context (your clarification)"
    else:
        intent, routed_by = choose_tool(text, companies)

    def ms():
        return int((time.time() - t0) * 1000)

    if intent is None:
        PENDING.pop("p", None)
        return {"reply": HELP, "tool": None, "args": {}, "card": None,
                "routed_by": routed_by, "ms": ms()}
    tool, args = intent

    if tool in UI_TOOLS:
        PENDING.pop("p", None)
        result = client.call_tool_full(tool, args)
        html = client.read_resource(UI_TOOLS[tool])
        return {
            "reply": "Here is your pipeline board.",
            "tool": tool,
            "args": args,
            "card": None,
            "app": {"uri": UI_TOOLS[tool], "html": html, "result": result},
            "routed_by": routed_by,
            "ms": ms(),
        }

    reply = client.call_tool(tool, args)
    if "Which one do you mean?" in reply:
        PENDING["p"] = {"tool": tool, "args": args, "ts": time.time()}
    else:
        PENDING.pop("p", None)
    card = None
    if tool in CARD_TOOLS:
        try:
            card = json.loads(client.call_tool("pipeline_data"))
        except Exception:
            card = None
    return {"reply": reply, "tool": tool, "args": args, "card": card,
            "routed_by": routed_by, "ms": ms()}


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
    # call_tool starts the session if needed and repairs it if the server restarted
    deals = len(json.loads(client.call_tool("company_names")))
    load_ui_map()
    return {
        "ok": True,
        "protocol": client.protocol_version,
        "tools": [t["name"] for t in _tools],
        "deals": deals,
        "brain": brain.status(),
    }


async def status(request):
    try:
        return JSONResponse(await run_in_threadpool(_status))
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)})


# ---------------------------------------------------------------------------
# CSV upload: preview, column guessing, commit through the import_deals tool
# ---------------------------------------------------------------------------
def norm(s) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(s).lower()).strip()


def guess_mapping(columns: list) -> dict:
    normed = {c: norm(c) for c in columns}
    mapping, used = {}, set()
    for field, syns in SYNONYMS.items():
        pick = None
        for syn in syns:  # exact header match first
            for c, n in normed.items():
                if c not in used and n == norm(syn):
                    pick = c
                    break
            if pick:
                break
        if not pick:
            for syn in syns:  # then "header contains the phrase"
                if len(syn) < 5:
                    continue
                for c, n in normed.items():
                    if c not in used and norm(syn) in n:
                        pick = c
                        break
                if pick:
                    break
        if pick:
            mapping[field] = pick
            used.add(pick)
    return mapping


def _dedupe_headers(headers: list) -> list:
    seen, out = {}, []
    for i, h in enumerate(headers):
        h = (h or "").strip() or f"Column {i + 1}"
        if h in seen:
            seen[h] += 1
            h = f"{h} ({seen[h]})"
        else:
            seen[h] = 1
        out.append(h)
    return out


def parse_table(text: str) -> dict:
    text = text.lstrip("\ufeff")
    if not text.strip():
        raise ValueError("The file is empty.")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ValueError("The file needs a header row and at least one data row.")
    headers = _dedupe_headers(rows[0])
    width = len(headers)
    if width < 2:
        raise ValueError("The file needs at least two columns.")
    if width > MAX_COLUMNS:
        raise ValueError(f"Too many columns ({width}). The limit is {MAX_COLUMNS}.")
    data = [[c.strip() for c in (r + [""] * width)[:width]] for r in rows[1:]]
    if len(data) > MAX_ROWS:
        raise ValueError(f"Too many rows ({len(data)}). The limit is {MAX_ROWS}.")
    return {"columns": headers, "rows": data}


def to_number(v):
    s = str(v).strip()
    if not s:
        return 0.0
    s = re.sub(r"[^0-9.\-]", "", s.replace(",", ""))
    try:
        return float(s)
    except ValueError:
        return None


def parse_date(v) -> str:
    s = str(v).strip().replace("Z", "")
    if not s:
        return ""
    for cand in (s, s.split("T")[0], s.split(" ")[0]):
        for fmt in DATE_FORMATS:
            try:
                d = dt.datetime.strptime(cand, fmt).date()
            except ValueError:
                continue
            return min(d, dt.date.today()).isoformat()
    return ""


def build_rows(table: dict, mapping: dict, multiplier: int) -> list:
    cols = table["columns"]
    idx = {c: i for i, c in enumerate(cols)}
    mapped = set(mapping.values())
    extra_cols = [c for c in cols if c not in mapped][:10]
    out = []
    for r in table["rows"]:
        row = {"company": r[idx[mapping["company"]]].strip()}
        row["contact"] = r[idx[mapping["contact"]]] if mapping.get("contact") else ""
        row["stage"] = r[idx[mapping["stage"]]] if mapping.get("stage") else ""
        if mapping.get("value"):
            raw = r[idx[mapping["value"]]]
            num = to_number(raw)
            row["value"] = (num * multiplier) if num is not None else raw
        else:
            row["value"] = 0
        row["last_activity"] = (
            parse_date(r[idx[mapping["last_activity"]]]) if mapping.get("last_activity") else ""
        )
        extra = {}
        for c in extra_cols:
            val = r[idx[c]].strip()
            if val:
                extra[c] = val[:100]
        row["extra"] = extra
        out.append(row)
    return out


async def upload_preview(request):
    try:
        data = await request.json()
        filename = Path(str(data.get("filename") or "upload.csv")).name[:80]
        text = data.get("text") or ""
        if not filename.lower().endswith(".csv"):
            return JSONResponse({"error": "Please choose a .csv file."})
        if len(text) > MAX_UPLOAD_CHARS:
            return JSONResponse({"error": "That file is over 5 MB."})
        table = parse_table(text)
    except Exception as e:
        return JSONResponse({"error": f"Could not read that CSV: {e}"})

    token = uuid.uuid4().hex
    UPLOADS[token] = {"table": table, "filename": filename, "ts": time.time()}
    for old in sorted(UPLOADS, key=lambda k: UPLOADS[k]["ts"])[:-5]:
        UPLOADS.pop(old, None)

    return JSONResponse(
        {
            "token": token,
            "filename": filename,
            "rows": len(table["rows"]),
            "columns": table["columns"],
            "mapping": guess_mapping(table["columns"]),
            "sample": table["rows"][:5],
        }
    )


def _commit(data: dict) -> dict:
    entry = UPLOADS.get(data.get("token"))
    if not entry:
        return {"error": "That upload expired. Please choose the file again."}
    table = entry["table"]
    mapping = {
        k: v
        for k, v in (data.get("mapping") or {}).items()
        if k in SYNONYMS and v in table["columns"]
    }
    if "company" not in mapping:
        return {"error": "Choose which column holds the company name."}
    mode = data.get("mode")
    if mode not in ("replace", "append"):
        return {"error": "Mode must be replace or append."}
    try:
        multiplier = int(data.get("multiplier") or 1)
    except (TypeError, ValueError):
        multiplier = 1
    if multiplier not in ALLOWED_MULTIPLIERS:
        multiplier = 1

    rows = build_rows(table, mapping, multiplier)
    raw = client.call_tool(
        "import_deals",
        {"rows_json": json.dumps(rows), "mode": mode, "filename": entry["filename"]},
    )
    result = json.loads(raw)
    summary = client.call_tool("pipeline_summary")
    observed = client.call_tool("describe_data")
    UPLOADS.pop(data.get("token"), None)
    PENDING.pop("p", None)
    return {"result": result, "summary": summary, "observed": observed,
            "filename": entry["filename"]}


async def upload_commit(request):
    try:
        data = await request.json()
        return JSONResponse(await run_in_threadpool(_commit, data))
    except Exception as e:
        return JSONResponse({"error": f"Import failed: {e}"})


async def reset(request):
    try:
        msg = await run_in_threadpool(client.call_tool, "reset_demo_data")
        PENDING.pop("p", None)
        return JSONResponse({"message": msg})
    except Exception as e:
        return JSONResponse({"error": str(e)})


async def index(request):
    return FileResponse(BASE / "index.html")


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/ask", ask, methods=["POST"]),
        Route("/api/status", status),
        Route("/api/upload/preview", upload_preview, methods=["POST"]),
        Route("/api/upload/commit", upload_commit, methods=["POST"]),
        Route("/api/reset", reset, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    print("Brain:", brain.status()["label"])
    threading.Thread(target=brain.warm, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8001)