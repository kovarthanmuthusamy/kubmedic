"""Live benchmark harness — needs a real cluster. NOT run in CI.

    make up                       # cluster + ArgoCD + boutique (once)
    make port-forward             # Prometheus/Loki URLs for the agent
    python -m evals.harness --model ollama/qwen2.5:7b-instruct-q4_K_M --runs 3

For each scenario, per run:
  1. commit the fault to the GitOps repo and push (ArgoCD deploys it)
  2. wait for the symptom in the cluster (poll kubectl)
  3. run the agent with live backends and the chosen model
  4. score the run with evals/scoring.py
  5. restore the good values with a revert commit and push

Results land in evals/results/<timestamp>-<model>.json — the file the
README's headline table is filled from. Nothing in the README claims a
number that is not in a committed results file.

The harness refuses to run on a dirty checkout: it commits to main.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "agent"))

from kubmedic_agent.config import Config
from kubmedic_agent.graph import run_incident
from kubmedic_agent.values import apply_edits, dump_values

from evals.scenarios import load_good_values, load_scenarios
from evals.scoring import score_run

RESULTS_DIR = REPO_ROOT / "evals" / "results"


def _run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, check=False, cwd=cwd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {proc.stderr.strip()}")
    return proc.stdout


def _git(repo: Path, *args: str) -> str:
    return _run(["git", "-C", str(repo), *args])


def _write_values(repo: Path, values: dict) -> None:
    path = repo / "gitops" / "app" / "values.yaml"
    path.write_text(dump_values(values), encoding="utf-8")


def _commit_push(repo: Path, message: str) -> None:
    _git(repo, "add", "gitops/app/values.yaml")
    _git(repo, "commit", "-m", message)
    _git(repo, "push", "origin", "main")


def _wait_for_symptom(config: Config, scenario: dict, timeout_s: int) -> float:
    """Poll until the affected service looks broken; return wait seconds."""
    service = scenario["service"]
    started = time.time()
    while time.time() - started < timeout_s:
        out = _run(
            ["kubectl", "get", "pods", "-n", config.namespace, "--no-headers"]
        )
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[0].startswith(service):
                status, ready = parts[2], parts[1]
                if status != "Running" or ready.split("/")[0] == "0":
                    return time.time() - started
        # Replicas-zero / selector faults: no sick pod exists; the ArgoCD
        # sync plus a fixed grace period is the observable signal.
        if scenario["evidence"].get("pod") is None and time.time() - started > 45:
            return time.time() - started
        time.sleep(10)
    return time.time() - started


def run_benchmark(args) -> dict:
    repo = Path(args.repo).resolve()
    if _git(repo, "status", "--porcelain").strip():
        raise SystemExit("checkout is dirty — the harness commits to main; aborting")
    good_values = load_good_values()
    scenarios = load_scenarios()
    if args.only:
        scenarios = [s for s in scenarios if s["id"] == args.only]
    config = Config.from_env()
    config = Config(**{**config.__dict__, "model": args.model, "gitops_path": str(repo)})

    runs: list[dict] = []
    for scenario in scenarios:
        for index in range(args.runs):
            print(f"== {scenario['id']} run {index + 1}/{args.runs}: injecting fault")
            _write_values(repo, apply_edits(good_values, scenario["fault"]))
            _commit_push(repo, f"chaos: {scenario['id']}")
            try:
                wait_s = _wait_for_symptom(config, scenario, args.wait_seconds)
                alert = {
                    "alertname": scenario["alert"]["name"],
                    "labels": scenario["alert"]["labels"],
                    "annotations": scenario["alert"]["annotations"],
                }
                state = run_incident(config, alert)
                scored = score_run(
                    scenario,
                    good_values,
                    status=state.get("status", "failed"),
                    diagnosis=state.get("diagnosis"),
                )
                runs.append(
                    {
                        **scored,
                        "run": index + 1,
                        "symptom_wait_s": round(wait_s, 1),
                        "agent_duration_s": state.get("duration_s"),
                        "tokens": state.get("tokens"),
                        "cost_usd": state.get("cost_usd"),
                        "pr_branch": (state.get("pr") or {}).get("branch"),
                        "error": state.get("error"),
                    }
                )
                print(f"   resolved={scored['resolved']} agent={state.get('duration_s')}s")
            finally:
                # The writer leaves us back on the pre-fix branch; make
                # sure we are on main, restore the good values, and push
                # the revert so ArgoCD heals the cluster.
                _git(repo, "checkout", "main")
                _write_values(repo, good_values)
                if _git(repo, "status", "--porcelain").strip():
                    _commit_push(repo, f"restore: {scenario['id']}")
    resolved = sum(1 for r in runs if r["resolved"])
    durations = [r["agent_duration_s"] for r in runs if r["agent_duration_s"]]
    summary = {
        "model": args.model,
        "started_at": datetime.now(UTC).isoformat(),
        "resolved": resolved,
        "total": len(runs),
        "median_agent_s": statistics.median(durations) if durations else None,
        "total_cost_usd": round(sum(r["cost_usd"] or 0 for r in runs), 4),
        "runs": runs,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    slug = args.model.replace("/", "-").replace(":", "-")
    out_path = RESULTS_DIR / f"{datetime.now(UTC):%Y%m%dT%H%M%S}-{slug}.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nbenchmark: {resolved}/{len(runs)} resolved -> {out_path}")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(prog="evals.harness")
    parser.add_argument("--model", default="ollama/qwen2.5:7b-instruct-q4_K_M")
    parser.add_argument("--repo", default=str(REPO_ROOT))
    parser.add_argument("--only", default=None, help="run a single scenario id")
    parser.add_argument("--runs", type=int, default=1)
    parser.add_argument("--wait-seconds", type=int, default=240)
    args = parser.parse_args()
    run_benchmark(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
