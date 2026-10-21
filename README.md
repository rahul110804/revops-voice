# RevOps Voice: a voice-first sales pipeline assistant for Alexa+

Built for the **Amazon App Dev Hackathon 2026**, **Alexa+ track**.

RevOps Voice is an **MCP server** (Model Context Protocol, spec 2025-11-25, Streamable HTTP) that lets a voice assistant answer questions about a sales pipeline, log calls, draft follow-ups, show a visual pipeline board, and answer number questions about any deals CSV you upload.

## Why a simulator?

Amazon's Alexa+ MCP toolkit and CLI are in preview with select partners, and Amazon staff confirmed on the hackathon discussion board that entrants do not get access. The rules allow simulating the Alexa+ experience in a web app, so this repo includes one. **Alexa+ itself is simulated. The MCP server is real**: it is a standard MCP server that any MCP client can call.

```
 You (voice / text)
        |
        v
 +--------------------------+   language model picks the tool
 | Alexa+ simulator (web)   |   (local Ollama model, keyword rules as fallback)
 | simulator/app.py :8001   |
 +------------+-------------+
              |  MCP over Streamable HTTP (tools/call, resources/read)
              v
 +--------------------------+
 | RevOps Voice MCP server  |   12 tools + an MCP App (ui://revops/pipeline.html)
 | server.py        :8000   |
 +------------+-------------+
              v
        SQLite (crm.db)

        ![Pipeline board](docs/screenshots/board.png).
```

## What it does

| Tool | Use |
|---|---|
| `pipeline_summary` | Deals and value per stage |
| `stalled_deals` | Open deals with no activity for N days (won and lost are ignored) |
| `list_deals` | The largest deals |
| `log_activity` | Log a call or note (asks "which one?" if a name is ambiguous) |
| `draft_followup` | Draft a follow-up email (Amazon Bedrock if available, template fallback) |
| `show_pipeline` | **MCP App**: the pipeline board served as `ui://` HTML by the server |
| `query_deals` | Counts, totals, averages, filters, group by any uploaded column |
| `describe_data` | What the loaded data looks like |
| `company_names`, `pipeline_data`, `import_deals`, `reset_demo_data` | Helper and admin tools for the web page |

The simulator also lets you **upload your own CSV**: it guesses which column is which, you confirm, and the rows go into SQLite through the `import_deals` tool. Columns it does not recognise (region, owner and so on) are kept and can be used in questions.

## Run it

Tested on Windows 11, Python 3.12, Chrome. It should also work elsewhere, but I have not tried.

```
git clone <YOUR-REPO-URL>
cd revops-voice
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

Terminal 1, the MCP server (it creates `crm.db` with 6 demo deals on first run):
```
python server.py
```
Terminal 2, the simulator:
```
python simulator/app.py
```
Open **http://127.0.0.1:8001 in Chrome** (voice input needs Chrome or Edge).

### Optional: the local language model

Without it, the simulator uses keyword rules. With it, free-form questions work ("anything I'm neglecting?").

1. Install [Ollama](https://ollama.com/download).
2. `ollama pull qwen2.5:7b`
3. Restart `simulator/app.py`. The header badge shows **Brain: qwen2.5:7b (Ollama, local)**.

On a CPU-only 16 GB laptop a new question takes about 6 to 10 seconds, and repeats are cached.

### Optional: Amazon Bedrock for email drafts

Set `AWS_BEARER_TOKEN_BEDROCK` (a Bedrock API key) and `BEDROCK_MODEL_ID` (default `amazon.nova-micro-v1:0`) before starting `server.py`. **Status in my account:** the key authenticates, but a new AWS account had Bedrock quotas of 0, so every call returned `ThrottlingException`. The AI-drafted path is written but has not produced output, so `draft_followup` currently returns its template email. Nothing else depends on Bedrock.

## Try it

1. "Give me the pipeline summary"
2. "Which accounts have gone quiet for over two weeks?"
3. "Show me the pipeline board"
4. Click **Upload CSV**, choose `data/sample_deals.csv`, confirm the columns, then ask: "How many deals are in Demo?", "Which region has the most value?", "What data do I have?"
5. `data/messy_test.csv` is a differently shaped file (other column names, ₹ amounts, dd/mm/yyyy dates).

**Reset demo data** in the header restores the 6 original deals.

Checks without the web page: `python simulator/test_client.py`, `python simulator/test_router.py`, `python simulator/test_import.py`.

## Safety notes

- `query_deals` takes **structured parameters only**. The model never writes SQL or code that gets run.
- A call note is only logged if the words appear in what the user said, so the model cannot invent notes.
- Uploads are parsed in memory, capped at 5 MB and 5,000 rows, and nothing is executed from them.
- No keys or credentials are stored in this repo.

## Built with

| Component | License |
|---|---|
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) v2.3.0, including the MCP Apps extension | MIT |
| boto3 (Amazon Bedrock client), httpx | Apache-2.0, BSD |
| Starlette, Uvicorn (installed with the SDK) | BSD |
| [Ollama](https://ollama.com) (optional) | MIT |
| qwen2.5:7b model (optional) | <LICENSE SHOWN ON ITS OLLAMA PAGE> |
| Browser Web Speech API for voice | n/a |

## Hackathon notes

- **New project**, started during the submission period (see the commit history).
- A friction log of the problems I hit is in [`docs/FRICTION-LOG.md`](docs/FRICTION-LOG.md).
- An Agent Skill description is in [`skills/revops-voice/SKILL.md`](skills/revops-voice/SKILL.md).

## License

MIT, see `LICENSE`.