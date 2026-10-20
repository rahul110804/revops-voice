import json

from mcp_http import MCPHttpClient

c = MCPHttpClient()
c.initialize()
tools = c.list_tools()
print("Tools:", [t["name"] for t in tools])
for t in tools:
    if t["name"] == "show_pipeline":
        print("show_pipeline _meta:", json.dumps(t.get("_meta"), indent=2))
        break
else:
    print("show_pipeline is NOT in the tool list")