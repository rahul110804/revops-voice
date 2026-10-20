import json
import os
import re

import httpx

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
TIMEOUT = float(os.environ.get("BRAIN_TIMEOUT", "90"))

# Tools meant for programs or admins are never offered to the model.
HIDDEN_TOOLS = {"company_names", "pipeline_data", "import_deals", "reset_demo_data"}
# Arguments the model does not need to choose (the tools have good defaults).
HIDDEN_ARGS = {"limit"}

SYSTEM_PROMPT = (
    "You are the language understanding layer of a voice assistant for a sales "
    "pipeline. Pick exactly one tool that answers the user's request and fill in "
    "its arguments only from what the user actually said. Convert spoken numbers "
    "and periods to numbers (for example 'two weeks' is 14 days). Use company "
    "names exactly as the user said them. Never invent notes or details. "
    "Do not answer in text. If no tool fits, call no tool."
)

OPTIONS = {"temperature": 0, "num_ctx": 4096, "num_predict": 120}

_CACHE = {}


def status() -> dict:
    """Is the local model available? Used for the badge on the page."""
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=1.5)
        names = [m.get("name", "") for m in r.json().get("models", [])]
        if MODEL in names or f"{MODEL}:latest" in names:
            return {"mode": "ollama", "label": f"{MODEL} (Ollama, local)"}
    except Exception:
        pass
    return {"mode": "keyword", "label": "keyword rules (Ollama not found)"}


def warm() -> None:
    """Load the model into memory so the first real question is not slow."""
    try:
        httpx.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL, "prompt": "", "keep_alive": "30m", "options": OPTIONS},
            timeout=TIMEOUT,
        )
    except Exception:
        pass


def _short(desc: str) -> str:
    """Keep the first two sentences: enough to choose the tool, cheaper to read."""
    desc = (desc or "").strip().replace("\n", " ")
    parts = re.split(r"(?<=[.!?])\s+", desc)
    return " ".join(parts[:2])[:220]


def _slim_schema(schema: dict) -> dict:
    props = {}
    for key, value in ((schema or {}).get("properties") or {}).items():
        if key in HIDDEN_ARGS:
            continue
        props[key] = {k: v for k, v in value.items() if k not in ("title", "default")}
    required = [r for r in ((schema or {}).get("required") or []) if r in props]
    out = {"type": "object", "properties": props}
    if required:
        out["required"] = required
    return out


def _to_ollama_tools(mcp_tools: list) -> list:
    out = []
    for t in mcp_tools:
        if t["name"] in HIDDEN_TOOLS:
            continue
        out.append(
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": _short(t.get("description")),
                    "parameters": _slim_schema(t.get("inputSchema") or {}),
                },
            }
        )
    return out


def _coerce_args(schema: dict, args: dict):
    """Keep only known arguments, fix their types, and check required ones."""
    props = (schema or {}).get("properties") or {}
    required = (schema or {}).get("required") or []
    clean = {}
    for key, value in (args or {}).items():
        if key not in props:
            continue
        typ = props[key].get("type")
        try:
            if typ == "integer":
                value = int(float(value))
            elif typ == "number":
                value = float(value)
            elif typ == "boolean":
                value = value if isinstance(value, bool) else str(value).lower() in ("true", "1", "yes")
            elif typ == "string":
                value = str(value)
        except (TypeError, ValueError):
            continue
        clean[key] = value
    for key in required:
        if key not in clean:
            return None
    return clean


def plan(text: str, mcp_tools: list):
    """Ask the local model which tool to call.

    Returns (tool, args, cached) or None. A repeated sentence is answered from
    a small cache of the model's own earlier decision, so it is instant.
    """
    key = re.sub(r"\s+", " ", text.lower().strip())
    if key in _CACHE:
        name, args = _CACHE[key]
        return name, dict(args), True

    schemas = {t["name"]: (t.get("inputSchema") or {}) for t in mcp_tools}
    r = httpx.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": MODEL,
            "stream": False,
            "keep_alive": "30m",
            "options": OPTIONS,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            "tools": _to_ollama_tools(mcp_tools),
        },
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    message = r.json().get("message", {})
    for call in message.get("tool_calls") or []:
        fn = call.get("function", {})
        name = fn.get("name")
        if name not in schemas or name in HIDDEN_TOOLS:
            continue
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except ValueError:
                args = {}
        clean = _coerce_args(schemas[name], args)
        if clean is None:
            continue
        _CACHE[key] = (name, clean)
        return name, dict(clean), False
    return None