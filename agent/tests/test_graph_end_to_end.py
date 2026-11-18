"""End-to-end: a real git repo with a faulty commit, fake cluster
backends, the deterministic heuristic investigator. The agent must
diagnose the OOM fault and open a fix branch restoring the memory
limit. This is the same path the replay eval gate exercises.
"""

import subprocess

import yaml

from kubmedic_agent.config import Config
from kubmedic_agent.graph import run_incident
from kubmedic_agent.tools.git_tools import SubprocessGit
from kubmedic_agent.tools.kubectl_tools import FakeKubectl
from kubmedic_agent.tools.loki_tools import FakeLoki
from kubmedic_agent.tools.prom_tools import FakeProm
from kubmedic_agent.wiring import build_registry

GOOD_VALUES = {
    "services": {
        "checkoutservice": {
            "image": "gcr.io/example/checkoutservice",
            "tag": "v0.10.1",
            "replicas": 1,
            "resources_limits_memory": "512Mi",
            "resources_limits_cpu": "500m",
        },
        "frontend": {
            "image": "gcr.io/example/frontend",
            "tag": "v0.10.1",
            "replicas": 1,
            "resources_limits_memory": "256Mi",
            "resources_limits_cpu": "250m",
        },
    }
}

PODS = (
    "checkoutservice-7d9f6b5c4-x2abc   0/1   CrashLoopBackOff   6   4m\n"
    "frontend-5c8d7f9b6-y1def          1/1   Running            0   4m"
)
DESCRIBE = (
    "Name: checkoutservice-7d9f6b5c4-x2abc\n"
    "State:          Waiting\n"
    "  Reason:       CrashLoopBackOff\n"
    "Last State:     Terminated\n"
    "  Reason:       OOMKilled\n"
    "  Exit Code:    137\n"
    "Warning  Failed     4m   kubelet  Error: OOMKilled"
)
LOGS = "2026-01-01T00:00:00Z starting checkoutservice\n2026-01-01T00:01:00Z fatal: out of memory"


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _make_repo(tmp_path):
    values_path = tmp_path / "gitops" / "app"
    values_path.mkdir(parents=True)
    _git(tmp_path, "init", "-b", "main")
    _git(tmp_path, "config", "user.email", "test@example.com")
    _git(tmp_path, "config", "user.name", "Test")
    (values_path / "values.yaml").write_text(yaml.safe_dump(GOOD_VALUES, sort_keys=False))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "baseline values")
    faulted = yaml.safe_load(yaml.safe_dump(GOOD_VALUES))
    faulted["services"]["checkoutservice"]["resources_limits_memory"] = "64Mi"
    (values_path / "values.yaml").write_text(yaml.safe_dump(faulted, sort_keys=False))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-m", "tune checkoutservice memory")
    return tmp_path


def test_agent_diagnoses_oom_and_opens_fix_branch(tmp_path):
    repo = _make_repo(tmp_path)
    config = Config(model="heuristic", gitops_path=str(repo), namespace="boutique")
    registry = build_registry(
        config,
        kubectl_backend=FakeKubectl(
            {"get pods": PODS, "describe pod": DESCRIBE, "logs": LOGS}
        ),
        prom_backend=FakeProm(),
        loki_backend=FakeLoki(),
        git_backend=SubprocessGit(repo),
    )
    alert = {
        "alertname": "KubePodCrashLooping",
        "labels": {"namespace": "boutique", "pod": "checkoutservice-7d9f6b5c4-x2abc"},
        "annotations": {"summary": "Pod boutique/checkoutservice is crash looping"},
    }
    state = run_incident(config, alert, registry=registry)

    assert state["status"] == "pr_opened"
    diagnosis = state["diagnosis"]
    assert diagnosis["service"] == "checkoutservice"
    assert "resources_limits_memory" in diagnosis["root_cause"]
    fix = {(e["service"], e["key"]): e["value"] for e in diagnosis["fix"]}
    assert fix[("checkoutservice", "resources_limits_memory")] == "512Mi"
    assert "64Mi" in state["diff"] and "512Mi" in state["diff"]
    branches = subprocess.run(
        ["git", "-C", str(repo), "branch", "--list", "kubmedic/*"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout
    assert "kubmedic/fix-checkoutservice" in branches
    # The trajectory is complete and ordered.
    events = [e["event"] for e in state["trajectory"]]
    assert events[0] == "triage" and "tool" in events and "model" in events
