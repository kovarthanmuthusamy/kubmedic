"""Replay eval gate — the zero-cost CI check.

For every chaos scenario this builds the world the agent would see if
the fault were live: a git repo whose latest commit is the faulty
values change, and fake cluster backends serving the scenario's
recorded evidence. The deterministic heuristic investigator then works
the incident end to end (real graph, real tools, real git parsing,
real PR branch), and the run is scored with evals/scoring.py.

This proves parsing, tool wiring, patching, guardrails and scoring.
It does NOT prove a real model is any good — the heuristic follows the
evidence mechanically. Live model quality is measured only by the
benchmark harness (evals/harness.py) on a real cluster.

Run:  python -m evals.replay        (from the repo root)
Exit code is non-zero if any scenario is unresolved.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "agent"))


from kubmedic_agent.config import Config
from kubmedic_agent.graph import run_incident
from kubmedic_agent.tools.git_tools import SubprocessGit
from kubmedic_agent.tools.kubectl_tools import FakeKubectl
from kubmedic_agent.tools.loki_tools import FakeLoki
from kubmedic_agent.tools.prom_tools import FakeProm
from kubmedic_agent.values import apply_edits, dump_values
from kubmedic_agent.wiring import build_registry

from evals.scenarios import load_good_values, load_scenarios
from evals.scoring import score_run


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _make_repo(tmp: Path, good_values: dict, scenario: dict) -> Path:
    values_dir = tmp / "gitops" / "app"
    values_dir.mkdir(parents=True)
    _git(tmp, "init", "-b", "main")
    _git(tmp, "config", "user.email", "replay@example.com")
    _git(tmp, "config", "user.name", "Replay")
    (values_dir / "values.yaml").write_text(dump_values(good_values), encoding="utf-8")
    _git(tmp, "add", ".")
    _git(tmp, "commit", "-m", "baseline values")
    faulted = apply_edits(good_values, scenario["fault"])
    (values_dir / "values.yaml").write_text(dump_values(faulted), encoding="utf-8")
    _git(tmp, "add", ".")
    _git(tmp, "commit", "-m", f"tune {scenario['service']} ({scenario['id']})")
    return tmp


def _pods_output(good_values: dict, scenario: dict) -> str:
    lines = []
    evidence_pod = scenario["evidence"].get("pod")
    if evidence_pod:
        lines.append(
            f"{evidence_pod['name']}   {evidence_pod['ready']}   "
            f"{evidence_pod['status']}   {evidence_pod['restarts']}   4m"
        )
    for name, svc in good_values["services"].items():
        if name == scenario["service"] or svc.get("replicas", 1) == 0:
            continue
        lines.append(f"{name}-5c8d7f9b6-y1def   1/1   Running   0   4m")
    return "\n".join(lines)


def replay_scenario(scenario: dict, good_values: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        repo = _make_repo(Path(tmp), good_values, scenario)
        evidence = scenario["evidence"]
        config = Config(model="heuristic", gitops_path=str(repo), namespace="boutique")
        registry = build_registry(
            config,
            kubectl_backend=FakeKubectl(
                {
                    "get pods": _pods_output(good_values, scenario),
                    "describe pod": "\n".join(evidence.get("describe_lines", [])),
                    "logs": "\n".join(evidence.get("logs", [])),
                    "get events": "\n".join(evidence.get("events", [])),
                }
            ),
            prom_backend=FakeProm(),
            loki_backend=FakeLoki(),
            git_backend=SubprocessGit(repo),
        )
        alert = {
            "alertname": scenario["alert"]["name"],
            "labels": scenario["alert"]["labels"],
            "annotations": scenario["alert"]["annotations"],
        }
        state = run_incident(config, alert, registry=registry)
        result = score_run(
            scenario,
            good_values,
            status=state.get("status", "failed"),
            diagnosis=state.get("diagnosis"),
        )
        result["error"] = state.get("error")
        return result


def main() -> int:
    good_values = load_good_values()
    scenarios = load_scenarios()
    results = []
    for scenario in scenarios:
        result = replay_scenario(scenario, good_values)
        results.append(result)
        mark = "PASS" if result["resolved"] else "FAIL"
        print(f"[{mark}] {result['scenario']:<28} status={result['status']}")
        if not result["resolved"]:
            print(f"       keys_restored={result['keys_restored']} "
                  f"root_cause_match={result['root_cause_match']} "
                  f"error={result['error'] or result['fix_error']}")
    resolved = sum(1 for r in results if r["resolved"])
    print(f"\nreplay: {resolved}/{len(results)} scenarios resolved")
    return 0 if resolved == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
