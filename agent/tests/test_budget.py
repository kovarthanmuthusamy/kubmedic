"""A model that never reaches a diagnosis must be stopped by the
step budget, not loop forever."""

from kubmedic_agent.config import Config
from kubmedic_agent.graph import run_incident
from kubmedic_agent.llm import ModelResponse, ToolCall
from kubmedic_agent.tools.git_tools import FakeGit
from kubmedic_agent.tools.kubectl_tools import FakeKubectl
from kubmedic_agent.tools.loki_tools import FakeLoki
from kubmedic_agent.tools.prom_tools import FakeProm
from kubmedic_agent.wiring import build_registry

PODS = "frontend-abc   1/1   Running   0   1m"


class StubbornModel:
    def complete(self, messages, tools):
        return ModelResponse(
            tool_calls=[ToolCall(id="s1", name="get_pods", arguments={})], tokens=10
        )


def test_step_budget_stops_runaway_agent(tmp_path):
    config = Config(model="heuristic", gitops_path=str(tmp_path), max_steps=3)
    registry = build_registry(
        config,
        kubectl_backend=FakeKubectl({"get pods": PODS}),
        prom_backend=FakeProm(),
        loki_backend=FakeLoki(),
        git_backend=FakeGit([]),
    )
    state = run_incident(
        config,
        {"alertname": "Test", "labels": {}, "annotations": {}},
        model=StubbornModel(),
        registry=registry,
    )
    assert state["status"] == "failed"
    assert "budget" in state["error"]
