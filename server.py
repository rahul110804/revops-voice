import json
import os
import sys
from datetime import date

import boto3
from botocore.config import Config
from mcp.server import MCPServer
from mcp.server.apps import Apps

import db

db.init()

MODEL_ID = os.environ.get("BEDROCK_MODEL_ID", "amazon.nova-micro-v1:0")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def inr(v: int) -> str:
    lakh = v / 100000
    return f"{lakh:.1f} lakh rupees"


# ---------------------------------------------------------------------------
# MCP Apps: the pipeline board. This block must come BEFORE MCPServer(...)
# is created, so the server picks up the UI tool and resource.
# ---------------------------------------------------------------------------
apps = Apps()

PIPELINE_UI_URI = "ui://revops/pipeline.html"

PIPELINE_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body{margin:0;padding:10px;font-family:system-ui,Segoe UI,sans-serif;background:#0f1720;color:#e8eef5}
  h1{font-size:14px;margin:0 0 8px}
  .board{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}
  .col{background:#17212d;border:1px solid #263444;border-radius:10px;padding:8px}
  .head{font-size:12px;color:#8fa3b8;margin-bottom:6px;display:flex;justify-content:space-between}
  .deal{background:#223244;border-radius:8px;padding:6px 8px;margin-bottom:6px;font-size:12px}
  .deal.stale{border-left:3px solid #ff6b6b}
  .n{font-weight:600}
  .m{color:#8fa3b8}
</style></head>
<body>
<h1>Pipeline board</h1>
<div id="app" class="m">Waiting for data...</div>
<script>
  var nextId = 1;
  var initId = null;
  function send(m){ window.parent.postMessage(m, "*"); }
  function el(tag, cls, text){
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }
  function extract(p){
    try {
      if (p && p.structuredContent && p.structuredContent.stages) return p.structuredContent;
      var items = (p && p.content) || [];
      for (var i = 0; i < items.length; i++) {
        if (items[i].type === "text") {
          var j = JSON.parse(items[i].text);
          if (j.stages) return j;
        }
      }
    } catch (e) {}
    return null;
  }
  function render(data){
    var root = document.getElementById("app");
    root.textContent = "";
    root.className = "board";
    data.stages.forEach(function(s){
      var col = el("div", "col");
      var head = el("div", "head");
      head.appendChild(el("span", "", s.stage));
      head.appendChild(el("span", "", s.total_lakh + " lakh"));
      col.appendChild(head);
      s.deals.forEach(function(d){
        var deal = el("div", "deal" + (d.idle_days >= 7 ? " stale" : ""));
        deal.appendChild(el("div", "n", d.company));
        deal.appendChild(el("div", "m", d.value_lakh + " lakh | " + d.idle_days + "d idle"));
        col.appendChild(deal);
      });
      root.appendChild(col);
    });
    send({jsonrpc:"2.0", method:"ui/notifications/size-changed",
          params:{width: document.documentElement.scrollWidth,
                  height: document.documentElement.scrollHeight}});
  }
  window.addEventListener("message", function(ev){
    var m = ev.data;
    if (!m || m.jsonrpc !== "2.0") return;
    if (m.id === initId && (m.result || m.error)) {
      send({jsonrpc:"2.0", method:"ui/notifications/initialized", params:{}});
      return;
    }
    if (m.method === "ui/notifications/tool-result") {
      var d = extract(m.params);
      if (d) render(d);
    }
  });
  initId = nextId++;
  send({jsonrpc:"2.0", id:initId, method:"ui/initialize",
        params:{protocolVersion:"2026-01-26",
                appInfo:{name:"revops-pipeline", version:"1.0.0"},
                appCapabilities:{}}});
</script>
</body></html>"""

STAGE_ORDER = ["Qualified", "Demo", "Proposal", "Negotiation"]


def build_pipeline_json() -> str:
    c = db.conn()
    rows = c.execute("SELECT * FROM deals").fetchall()
    c.close()
    stages = {s: [] for s in STAGE_ORDER}
    for r in rows:
        idle = (date.today() - date.fromisoformat(r["last_activity"])).days
        stages.setdefault(r["stage"], []).append(
            {
                "company": r["company"],
                "contact": r["contact"],
                "value_lakh": round(r["value"] / 100000, 1),
                "idle_days": idle,
            }
        )
    out = []
    for name, deals in stages.items():
        deals.sort(key=lambda d: -d["value_lakh"])
        out.append(
            {
                "stage": name,
                "total_lakh": round(sum(d["value_lakh"] for d in deals), 1),
                "deals": deals,
            }
        )
    return json.dumps({"stages": out})


@apps.tool(
    resource_uri=PIPELINE_UI_URI,
    description="Show the sales pipeline as a visual board grouped by stage. Use when the user wants to see, view or show the pipeline.",
)
def show_pipeline() -> str:
    return build_pipeline_json()


apps.add_html_resource(PIPELINE_UI_URI, PIPELINE_HTML, title="Pipeline board")

# ---------------------------------------------------------------------------
# The server is created AFTER the Apps tool and resource are defined.
# ---------------------------------------------------------------------------
mcp = MCPServer("revops-voice", extensions=[apps])


def ai_draft(company: str, contact: str, stage: str, tone: str) -> str:
    """Ask Amazon Bedrock to write a short follow-up email."""
    client = boto3.client(
        "bedrock-runtime",
        region_name=REGION,
        config=Config(
            retries={"max_attempts": 1},
            connect_timeout=3,
            read_timeout=8,
        ),
    )
    prompt = (
        f"Write a {tone} follow-up email of at most three sentences to {contact} "
        f"at {company}. The deal is in the {stage} stage. "
        "Do not include a subject line or placeholders."
    )
    resp = client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 200, "temperature": 0.5},
    )
    return resp["output"]["message"]["content"][0]["text"].strip()


@mcp.tool()
def pipeline_summary() -> str:
    """Give a short spoken summary of the sales pipeline: number of deals and total value in each stage."""
    c = db.conn()
    rows = c.execute(
        "SELECT stage, COUNT(*) AS n, SUM(value) AS total FROM deals GROUP BY stage"
    ).fetchall()
    c.close()
    parts = [f"{r['n']} in {r['stage']}, worth {inr(r['total'])}" for r in rows]
    return "Your pipeline: " + "; ".join(parts) + "."


@mcp.tool()
def stalled_deals(days: int = 7) -> str:
    """List deals with no activity for at least this many days. Use this when the user asks which deals are stuck, stalled or going cold."""
    c = db.conn()
    rows = c.execute("SELECT * FROM deals ORDER BY last_activity").fetchall()
    c.close()
    out = []
    for r in rows:
        idle = (date.today() - date.fromisoformat(r["last_activity"])).days
        if idle >= days:
            out.append(f"{r['company']}, idle {idle} days, {inr(r['value'])}")
    if not out:
        return f"No deals have been idle for {days} days or more."
    return f"{len(out)} stalled deals. " + ". ".join(out) + "."


@mcp.tool()
def log_activity(company: str, note: str) -> str:
    """Log a call or meeting note against a deal and mark that deal as active today."""
    c = db.conn()
    d = c.execute(
        "SELECT id, company FROM deals WHERE company LIKE ?", (f"%{company}%",)
    ).fetchone()
    if not d:
        c.close()
        return f"I couldn't find a deal matching {company}."
    today = date.today().isoformat()
    c.execute(
        "INSERT INTO activities(deal_id, note, on_date) VALUES(?,?,?)",
        (d["id"], note, today),
    )
    c.execute("UPDATE deals SET last_activity=? WHERE id=?", (today, d["id"]))
    c.commit()
    c.close()
    return f"Logged. {d['company']} is now marked active today."


@mcp.tool()
def draft_followup(company: str, tone: str = "friendly") -> str:
    """Draft a short follow-up email for a deal, in the requested tone."""
    c = db.conn()
    d = c.execute(
        "SELECT * FROM deals WHERE company LIKE ?", (f"%{company}%",)
    ).fetchone()
    c.close()
    if not d:
        return f"I couldn't find a deal matching {company}."
    try:
        return ai_draft(d["company"], d["contact"], d["stage"], tone)
    except Exception as e:
        print(f"Bedrock unavailable, using template: {e}", file=sys.stderr)
        return (
            f"Hi {d['contact']}, just checking in on the {d['stage']} stage "
            f"for {d['company']}. Happy to answer any questions."
        )


@mcp.tool()
def list_deals() -> str:
    """List every deal with its company, stage and value. Use when the user asks what deals they have."""
    c = db.conn()
    rows = c.execute(
        "SELECT company, stage, value FROM deals ORDER BY value DESC"
    ).fetchall()
    c.close()
    parts = [f"{r['company']}, {r['stage']}, {inr(r['value'])}" for r in rows]
    return f"You have {len(rows)} deals: " + "; ".join(parts) + "."


@mcp.tool()
def pipeline_data() -> str:
    """Return the whole pipeline as JSON, grouped by stage. For programs, not meant to be read aloud."""
    return build_pipeline_json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)