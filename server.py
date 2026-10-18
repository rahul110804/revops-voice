from datetime import date

from mcp.server import MCPServer

import db

db.init()

mcp = MCPServer("revops-voice")


def inr(v: int) -> str:
    lakh = v / 100000
    return f"{lakh:.1f} lakh rupees"


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
    # Placeholder. We replace this with Amazon Bedrock later.
    return (
        f"Hi {d['contact']}, just checking in on the {d['stage']} stage "
        f"for {d['company']}. Happy to answer any questions. ({tone})"
    )


if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="127.0.0.1", port=8000)