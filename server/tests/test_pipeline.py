import json

from fastapi.testclient import TestClient

from app.main import app


def _collect_body(resp):
    """Parses SSE blocks into {event_type: [payloads]}."""
    by_type: dict[str, list[dict]] = {}
    current = None
    for line in resp.iter_lines():
        if not line:
            continue
        if line.startswith("event:"):
            current = line[len("event:"):].strip()
        elif line.startswith("data:"):
            payload = json.loads(line[len("data:"):].strip())
            by_type.setdefault(current, []).append(payload)
    return by_type


def test_pipeline_streams_events_end_to_end():
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/v1/agents/workflow/run",
            json={"task": "Calculate 3 items at 129.9 each plus 15% tax"},
        ) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            events = _collect_body(resp)

    assert "agent.start" in events and events["agent.start"][0]["task"].startswith("Calculate")
    assert "agent.plan" in events
    assert "tool.call" in events and events["tool.call"][0]["tool"] == "calculator"
    assert "tool.result" in events and events["tool.result"][0]["ok"] is True
    assert "agent.done" in events
    assert events["agent.done"][0]["tool_stats"]["total"] == 1
    assert "approval.request" not in events


def test_failure_path_surfaces_error_and_continues():
    """A failing tool must be visible as an error event, then the pipeline
    still completes with a truthful summary (resilience, not crash)."""
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/v1/agents/workflow/run",
            json={"task": "Read the file named missing.txt please"},
        ) as resp:
            events = _collect_body(resp)

    assert events["tool.call"][0]["tool"] == "file_store"
    result = events["tool.result"][0]
    assert result["ok"] is False
    assert "missing.txt" in result["error"]
    assert "agent.done" in events
    assert events["agent.done"][0]["tool_stats"]["ok"] == 0


def test_session_events_can_be_replayed():
    """Auditability: every session records its event stream for replay."""
    with TestClient(app) as client:
        with client.stream(
            "POST",
            "/v1/agents/workflow/run",
            json={"task": "Calculate 2 + 2"},
        ) as resp:
            events = _collect_body(resp)
        session_id = events["agent.start"][0]["session_id"]

        replay = client.get(f"/v1/agents/{session_id}/events")
        assert replay.status_code == 200
        body = replay.json()
        assert body["session_id"] == session_id
        types = [e["event"] for e in body["events"]]
        assert types[0] == "agent.start"
        assert "agent.done" in types
        assert len(body["events"]) == len(events)


def test_replay_unknown_session_404():
    with TestClient(app) as client:
        resp = client.get("/v1/agents/sess_does_not_exist/events")
    assert resp.status_code == 404


def test_step_results_flow_into_later_step_args():
    """Plans may chain steps: {{step-1.result}} is substituted with the
    previous tool's output before the next tool runs."""
    from app.agents.executor import _render_args, StepOutcome

    args = {
        "content": "Refund: {{step-1.result}}, raw: {{ step-2 .output }}",
        "plain": "static",
    }
    filled = _render_args(
        args,
        {
            "step-1": StepOutcome("step-1", "rag_search", ok=True, output={"window": "14 days"}),
            "step-2": StepOutcome("step-2", "calculator", ok=True, output="448.155"),
        },
    )
    assert filled["content"] == 'Refund: {"window": "14 days"}, raw: 448.155'
    assert filled["plain"] == "static"
    unknown = _render_args(
        {"x": "{{step-9.result}}"},
        {"step-1": StepOutcome("step-1", "t", ok=True, output={})},
    )
    assert unknown["x"] == "{{step-9.result}}"


def test_healthz():
    with TestClient(app) as client:
        resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["llm_provider"] == "stub"  # test env has no key
    assert body["model"]


def test_playground_product_shell():
    """The dual-pane product shell (chat left / business panels right)
    is served and carries its interaction anchors."""
    with TestClient(app) as client:
        resp = client.get("/playground")
    assert resp.status_code == 200
    html = resp.text
    assert "id=\"chat\"" in html and "id=\"composer\"" in html
    assert "id=\"kb\"" in html and "id=\"queue\"" in html and "id=\"trail\"" in html
    assert "data-action" in html  # approval buttons carry their action id