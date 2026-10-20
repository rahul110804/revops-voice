# Friction Log: RevOps Voice (Alexa+ track)

Builder: <your name>. Environment: Windows 11, Python 3.12, MCP Python SDK 2.3.0.
Entries from Oct 18-19, 2026.

## 1. Alexa AI CLI install returns 404 (High)
- **Task:** Install the Alexa AI CLI from the Alexa+ MCP Quickstart.
- **Steps:** Opened the quickstart, which says to install the CLI and run
  `alexa-ai configure`. Ran `npm install -g @alexa-ai/cli`.
- **Expected:** The CLI installs.
- **Actual:** `E404 ... '@alexa-ai/cli' is not in this registry`.
- **Workaround:** None. Built my own web simulator with a protocol-level MCP client.
- **Suggestion:** Say on the quickstart page that the toolkit needs a separate
  private-registry setup and is limited to select partners.

## 2. AssumeRole AccessDenied on the registry role (High)
- **Task:** Follow "Set Up Your Development Environment" to reach the private registry.
- **Steps:** Created an IAM user with the documented `sts:AssumeRole` policy for
  `AddOn3PDeveloperToolsRead`, configured two AWS CLI profiles, ran
  `aws sts get-caller-identity --profile alexa-ai`.
- **Expected:** The role is assumed.
- **Actual:** `AccessDenied ... not authorized to perform sts:AssumeRole`.
  The guide assumes the AWS account ID was shared with an Alexa Solutions Architect.
  Hackathon entrants have none.
- **Workaround:** Built the simulator the rules allow.
- **Suggestion:** State on the hackathon Resources page and the docs that toolkit
  access is not available to entrants. I found this only in a Developer Community thread.

## 3. Docs search returns unrelated products (Low)
- **Task:** Find the Alexa+ CLI install step.
- **Actual:** Searching the exact heading returned Vega, Luna and ASK CLI pages first.
- **Suggestion:** Scope search results to the product area of the page I came from.

## 4. "Get Support from Amazon" only covers assigned Solutions Architects (Medium)
- **Task:** Ask for help with the access error.
- **Actual:** The page tells me to contact my assigned Solutions Architect. Individual
  developers have no such contact.
- **Workaround:** Posted in the community forum; read existing threads.
- **Suggestion:** Add a route for individual and hackathon developers.

## 5. New AWS account has zero Bedrock quota, and the error is misleading (High)
- **Task:** Draft follow-up emails with Amazon Nova Micro on Bedrock.
- **Steps:** Opened the playground in us-east-1 and ran one short prompt, then ran
  the same through the Converse API with a Bedrock API key.
- **Expected:** A short reply.
- **Actual:** `ThrottlingException: Too many tokens per day`. The Quotas page showed
  0 TPM and 0 RPM for every Nova model, so this was a missing quota, not heavy use.
- **Workaround:** The server falls back to a template email when Bedrock fails.
- **Suggestion:** Show "quota is 0 for this account" in the error, and give new
  accounts non-zero defaults for small models.

## 6. Bedrock API key setup shows Linux syntax (Low)
- **Task:** Use a short-term Bedrock API key from Windows PowerShell.
- **Actual:** The console's `export VAR=...` line fails in PowerShell, and the key
  is displayed in plain text in the terminal.
- **Suggestion:** Show PowerShell and cmd tabs, and warn about terminal history.

## 7. `pip install "mcp[cli]"` installs v2, but most guides show v1 (Medium)
- **Task:** Create an MCP server in Python.
- **Actual:** Installed 2.3.0. Tutorials and search results use the v1 style
  (`from mcp.server.fastmcp import FastMCP`), which fails on v2 (`MCPServer`).
- **Workaround:** Read the v2 docs and migrated my code.
- **Suggestion:** Add a v1-versus-v2 note to the PyPI page and quickstart.

## 8. MCP Apps tool silently missing if registered after the server is created (Medium)
- **Task:** Serve a UI with `@apps.tool` and `apps.add_html_resource`.
- **Actual:** The tool was absent from `tools/list` with no error or warning.
  Defining the tool and resource before `MCPServer(extensions=[apps])` fixed it.
- **Suggestion:** Raise a warning or document the ordering.

## Feature requests
1. **A hosted Alexa+ test sandbox for hackathon entrants** (Critical): lets entrants
   show the real assistant calling their MCP server.
2. **A self-service way to request toolkit access** (Important).
3. **A clearer Bedrock quota error** (Nice-to-have).