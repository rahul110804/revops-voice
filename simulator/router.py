import json

from mcp_http import MCPHttpClient
from router import route

client = MCPHttpClient()
companies = json.loads(client.call_tool("company_names"))
print("Companies loaded:", len(companies))

tests = [
    "Which deals are stuck?",
    "Give me the pipeline summary",
    "How many deals are in Demo?",
    "Total value of proposals above 10 lakh",
    "Show me the pipeline board",
    "What data do I have",
    "Tell me a joke",
]

for sentence in tests:
    print("\nYou:", sentence)
    intent = route(sentence, companies)
    if intent is None:
        print("  -> no match")
        continue
    tool, args = intent
    print("  ->", tool, args)
    if tool != "show_pipeline":
        print("  Alexa:", client.call_tool(tool, args))