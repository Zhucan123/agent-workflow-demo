# Agent Workflow Demo

> A production-grade multi-agent workflow built with FastAPI — planner,
> tool executor, HITL review — streamed over SSE. Includes a Spring Boot
> integration client.

This repository is a self-contained reference implementation of the agent
architecture used in production at AI product companies: a **Planner
agent** decomposes a task, a **Tool Executor** calls real tools with
typed results, and a **Reviewer** gates risky actions through
**human-in-the-loop (HITL) approval** — all delivered over **SSE
streaming events**, with **token/cost tracking** and **lightweight RAG**
that requires no vector-database operations.

- Language-agnostic agent design: the core API contract is SSE events —
  the Java client in `integration/java-client` consumes the same streams.
- Zero external services required: works with any OpenAI-compatible
  endpoint (OpenAI / DeepSeek / Qwen / Ollama), or even without an API
  key at all (stub mode).

## Architecture

```
 Client (curl / REST / Spring Boot)
        │  POST /v1/agents/workflow/run {task}
        ▼
 FastAPI server  ─────────────────────────────────────────────┐
   ├─ Planner     : decompose task → steps (tool, args)        │
   ├─ Executor    : run tools, stream tool.call/tool.result    │
   ├─ Reviewer    : HITL approval for risky actions            │
   ├─ RAG         : hybrid retrieval (vector + keyword)        │
   └─ Memory      : session state, summary compression         │
        │  SSE events: agent.start → plan → tool.call →
        │  approval.request → tool.result → ... → agent.done
        ▼
 Clients render tool cards, approval sheets, cost counters
```

See [docs/architecture.md](docs/architecture.md) for the full design.

## Quick start

Prerequisites: Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd server
uv sync
cp .env.example .env  # fill in OPENAI_API_KEY, model, MCP mode
uv run uvicorn app.main:app --port 8000
```

`server/.env` is loaded automatically (gitignored); environment variables
override it. Or set options by env (stub mode works with no key at all):

```bash
export OPENAI_BASE_URL=https://api.deepseek.com/v1   # OpenAI / DeepSeek / Qwen / Ollama all work
export OPENAI_API_KEY=sk-xxx
export AGENT_MODEL=deepseek-chat
# optional: real semantic embeddings (skip → deterministic hash vectors, zero-key)
export AGENT_EMBED_BACKEND=openai
export AGENT_EMBED_MODEL=text-embedding-3-small
```

### Run a task

```bash
curl -N -X POST http://localhost:8000/v1/agents/workflow/run \
  -H 'Content-Type: application/json' \
  -d '{"task": "Calculate 3 items at 129.9 each plus 15% tax, then write a receipt file"}'
```

You will see the full event stream: plan, tool calls, an
`approval.request` (the write-file action gated by HITL), and the final
result. Approve from a second terminal:

```bash
# approve from a second terminal (action_id comes from the approval.request event)
curl -X POST http://localhost:8000/v1/agents/<session_id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"action_id": "<from approval.request event>", "decision": "allow"}'
```

Or open `http://localhost:8000/playground` in a browser for a visual
demo page (tool cards + approval buttons).

### RAG

```bash
uv run python ../scripts/seed.py        # ingest sample docs
curl 'http://localhost:8000/v1/rag/search?q=refund%20policy&k=3'
```

### Java client

```bash
cd integration/java-client
mvn -q spring-boot:run -Dspring-boot.run.arguments="Calculate 3 items at 129.9 each plus 15% tax"
```

### MCP (Model Context Protocol)

The agent consumes tools from any MCP server (read-only tools pass
through, mutating tools hit the HITL approval gate):

```bash
# bundled zero-key demo server (external workspace: read + append)
export AGENT_MCP_MODE=demo

# or point at any real MCP server
export AGENT_MCP_MODE='stdio:npx -y @modelcontextprotocol/server-filesystem /tmp/ws'
```

Remote tools appear to the planner as `mcp_<name>` with their real input
schemas; e.g. a task like "use the external workspace to read notes.txt
then append a line" runs entirely through the MCP bridge. See
`docs/architecture.md` → *MCP* for details.

## What's inside

| Path | Responsibility |
|---|---|
| `server/app/main.py` | FastAPI app, SSE endpoints, playground |
| `server/app/agents/` | planner / executor / reviewer pipeline |
| `server/app/tools/registry.py` | tool registry + typed tool contracts |
| `server/app/tools/` | `calculator`, `file_store` (HITL-gated), `web_search`, `time` |
| `server/app/rag/` | ingest, embed, hybrid retrieval (vector + keyword) |
| `server/app/llm/client.py` | OpenAI-compatible client + deterministic stub |
| `server/app/mcp_bridge.py` | MCP client: consume tools from any MCP server |
| `server/app/state.py` | session memory & approval state |
| `integration/java-client/` | Spring Boot 3 SSE consumer (30 lines of core logic) |
| `scripts/seed.py` | sample document ingestion |
| `scripts/mcp_demo_server.py` | bundled zero-key external MCP server (demo) |
| `scripts/mcp_expose_server.py` | expose built-in tools as a standard MCP server |
| `tests/` | pytest suite (runs with zero API keys) |

## Why this design

- **HITL as a first-class event** — `approval.request` is part of the
  protocol, not an afterthought. Clients render a native approval sheet;
  the executor pauses until the decision arrives.
- **Deterministic tools first** — `calculator` and `time` prove stable
  tool-calling; risky actions (file writes) intentionally require
  human review, which is exactly the pattern enterprise teams need.
- **No-ops RAG** — hybrid retrieval over a plain JSON store with a
  pluggable embedder. Swap in pgvector or sqlite-vss by replacing one
  class.
- **Streaming by default** — every tool call is an observable event.
  Latency, cost (token.usage) and failure (`agent.error`) are visible.

## License

MIT