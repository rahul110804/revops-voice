import json
import time

import httpx

MODEL = "qwen2.5:7b"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "stalled_deals",
            "description": "List deals with no activity for at least this many days. Use when the user asks which deals are stuck, stalled or going cold.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Minimum idle days, default 7"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pipeline_summary",
            "description": "Short spoken summary of the sales pipeline: deals and total value per stage.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


def ask(question: str) -> None:
    start = time.time()
    r = httpx.post(
        "http://127.0.0.1:11434/api/chat",
        json={
            "model": MODEL,
            "stream": False,
            "keep_alive": "30m",
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": "You route sales questions to tools. Always call a tool."},
                {"role": "user", "content": question},
            ],
            "tools": TOOLS,
        },
        timeout=300,
    )
    r.raise_for_status()
    msg = r.json()["message"]
    print(f"\nQ: {question}")
    print(f"  time: {time.time() - start:.1f}s")
    if msg.get("tool_calls"):
        print("  tool_calls:", json.dumps(msg["tool_calls"], indent=2))
    else:
        print("  no tool call. text:", msg.get("content"))


ask("Which deals have been stuck for more than 10 days?")
ask("How is my pipeline looking?")
ask("Which deals have been stuck for more than 10 days?")