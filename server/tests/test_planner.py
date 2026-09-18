from app.agents.planner import Plan, _stub_plan


def test_plan_contains_calculator_for_number_tasks():
    plan = _stub_plan("Calculate 3 items at 129.9 each plus 15% tax")
    tools = [s.tool for s in plan.steps]
    assert "calculator" in tools


def test_write_step_requires_approval():
    plan = _stub_plan("Calculate total then write a receipt file")
    write_steps = [s for s in plan.steps if s.tool == "file_store"]
    assert write_steps
    assert write_steps[0].requires_approval is True


def test_plan_model_validates():
    plan = Plan(
        reason="demo",
        steps=[{"id": "step-1", "tool": "file_store", "args": {"action": "write"}, "requires_approval": True}],
    )
    assert plan.steps[0].requires_approval is True