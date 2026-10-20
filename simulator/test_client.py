from mcp_http import MCPHttpClient

client = MCPHttpClient()
info = client.initialize()
print("Server:", info.get("serverInfo"))
print("Protocol version:", info.get("protocolVersion"))
print("Tools:", [t["name"] for t in client.list_tools()])
print("Summary:", client.call_tool("pipeline_summary"))
print("Stalled:", client.call_tool("stalled_deals", {"days": 7}))