import asyncio
import json
import time
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import config
from .agents.executor import Executor
from .agents.planner import Planner
from .agents.reviewer import Reviewer
from .llm.client import LLMClient
from .rag.ingest import chunk_text, read_docs
from .rag.retrieve import Retriever
from .rag.store import VectorStore
from .state import StateStore
from .tools.registry import ToolContext, build_default_registry

_PLAYGROUND_HTML = (Path(__file__).parent / "playground.html").read_text(encoding="utf-8")


class JobRequest(BaseModel):
    task: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None


class ApproveRequest(BaseModel):
    action_id: str
    decision: str = Field(pattern="^(allow|deny)$")


def _sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    app.state.llm = LLMClient()
    app.state.state_store = StateStore()

    store = VectorStore()
    store.load(config.VSTORE_PATH)
    retriever = Retriever(store)
    ctx = ToolContext(retrieval=retriever, llm=app.state.llm, sandbox=config.SANDBOX_DIR)
    app.state.vector_store = store
    app.state.retriever = retriever
    app.state.tool_ctx = ctx
    app.state.registry = build_default_registry(ctx)

    app.state.planner = Planner(app.state.llm, app.state.registry)
    app.state.executor = Executor(
        app.state.registry, app.state.state_store, app.state.llm, ctx
    )
    app.state.reviewer = Reviewer(app.state.llm)

    mcp_spec = None
    from . import mcp_bridge  # deferred: pulls in mcp SDK only when used

    mcp_spec = mcp_bridge.resolve_spec()
    if mcp_spec:
        app.state.mcp_bridge = await mcp_bridge.install(app.state.registry, mcp_spec)
    yield
    if mcp_spec:
        await app.state.mcp_bridge.close()


app = FastAPI(title="Agent Workflow Demo", version="0.1.0", lifespan=lifespan)


@app.get("/healthz")
async def healthz() -> dict:
    return {"status": "ok", "llm_provider": getattr(app.state.llm, "provider", "n/a")}


async def _run_pipeline(session_id: str, task: str, emit):
    started = time.time()
    planner = app.state.planner
    executor = app.state.executor
    reviewer = app.state.reviewer
    state = app.state.state_store

    await emit(
        "agent.start",
        {
            "session_id": session_id,
            "task": task,
            "model": config.MODEL,
            "llm_provider": planner.llm.provider,
        },
    )

    plan, usage = await planner.plan(task)
    await emit("agent.plan", {"reason": plan.reason, "steps": [s.model_dump() for s in plan.steps]})
    if usage:
        usage.pop("prompt_tokens", None)
        usage.pop("completion_tokens", None)

    outcomes = await executor.run(session_id, plan, emit)
    summary = await reviewer.review(task, outcomes)

    duration_ms = int((time.time() - started) * 1000)
    state.remember(
        session_id,
        f"task={task[:60]} steps={len(outcomes)} ok={sum(1 for o in outcomes if o.ok)}",
    )
    await emit(
        "agent.done",
        {
            "session_id": session_id,
            "summary": summary,
            "duration_ms": duration_ms,
            "tool_stats": {
                "total": len(outcomes),
                "ok": sum(1 for o in outcomes if o.ok),
                "denied": sum(1 for o in outcomes if o.approved is False),
            },
            "memory": state.recall(session_id)[-5:],
        },
    )


async def _event_stream(session_id: str, task: str):
    queue: asyncio.Queue = asyncio.Queue()
    state = app.state.state_store.get(session_id)

    async def emit(event: str, payload: dict) -> None:
        if state is not None:
            state.record(event, payload)
        await queue.put(_sse(event, payload))

    async def run():
        try:
            await _run_pipeline(session_id, task, emit)
        except Exception as exc:  # noqa: BLE001 - errors are streamed to the client
            await queue.put(_sse("agent.error", {"message": f"{type(exc).__name__}: {exc}"}))
        finally:
            await queue.put(None)

    runner = asyncio.create_task(run())
    while True:
        item = await queue.get()
        if item is None:
            break
        yield item
        await asyncio.sleep(0.05)
    await runner


@app.post("/v1/agents/workflow/run")
async def run_workflow(job: JobRequest):
    session = app.state.state_store.get_or_create(job.session_id)
    return StreamingResponse(
        _event_stream(session.session_id, job.task),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/v1/agents/{session_id}/events")
async def replay_events(session_id: str) -> dict:
    """Replay the recorded event stream of a finished session (auditability)."""
    state = app.state.state_store.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail=f"unknown session: {session_id}")
    return {"session_id": session_id, "events": state.events}


@app.post("/v1/agents/{session_id}/approve")
async def approve(session_id: str, body: ApproveRequest):
    try:
        resolved = app.state.state_store.resolve(session_id, body.action_id, body.decision)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not resolved:
        raise HTTPException(status_code=404, detail=f"unknown action_id: {body.action_id}")
    return {"status": "resolved", "action_id": body.action_id, "decision": body.decision}


@app.get("/v1/rag/search")
async def rag_search(q: str, k: int = 3) -> dict:
    hits = app.state.retriever.search(q, k=max(1, min(k, 10)))
    return {"query": q, "hits": hits}


@app.post("/v1/rag/ingest")
async def rag_ingest() -> dict:
    added = 0
    for source, content in read_docs(config.DOCS_DIR):
        added += app.state.vector_store.add(chunk_text(content), source)
    app.state.vector_store.save(config.VSTORE_PATH)
    return {"chunks_added": added, "docs_ingested": len(app.state.vector_store.docs)}


@app.get("/playground", response_class=HTMLResponse)
async def playground() -> str:
    return _PLAYGROUND_HTML