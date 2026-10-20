import csv
import json
import sys

from mcp_http import MCPHttpClient

client = MCPHttpClient()

if len(sys.argv) > 1 and sys.argv[1] == "reset":
    print(client.call_tool("reset_demo_data"))
    raise SystemExit

rows = []
with open("data/sample_deals.csv", newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        rows.append(
            {
                "company": r["Account Name"],
                "contact": r["Primary Contact"],
                "stage": r["Pipeline Stage"],
                "value": r["Amount (INR)"],
                "last_activity": r["Last Contacted"],
                "extra": {"owner": r["Owner"], "region": r["Region"]},
            }
        )
print("Read", len(rows), "rows from the CSV")

result = client.call_tool(
    "import_deals",
    {"rows_json": json.dumps(rows), "mode": "replace", "filename": "sample_deals.csv"},
)
print("Import result:", result)
print("Summary:", client.call_tool("pipeline_summary"))
print("Stalled:", client.call_tool("stalled_deals", {"days": 21, "limit": 3}))