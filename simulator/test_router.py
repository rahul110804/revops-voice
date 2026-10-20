from mcp_http import MCPHttpClient
from router import parse_companies, route

client = MCPHttpClient()
companies = parse_companies(client.call_tool("list_deals"))
print("Companies:", companies)

tests = [
    "Which deals are stuck?",
    "Give me the pipeline summary",
    "Which deals have been idle for 10 days",
    "Log a call with Acme, sent the pricing sheet",
    "Draft a formal follow up for Orbit",
    "What deals do I have",
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
    print("  Alexa:", client.call_tool(tool, args))