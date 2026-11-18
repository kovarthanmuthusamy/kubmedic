"""Command line: run one incident from an alert JSON file.

    python -m kubmedic_agent.cli run --alert alert.json \
        [--model heuristic] [--trajectory-out run.json]

The alert file holds one Alertmanager-style alert:
{"alertname": "...", "labels": {...}, "annotations": {...}}
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from kubmedic_agent.config import Config
from kubmedic_agent.graph import run_incident


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="kubmedic")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one incident")
    run.add_argument("--alert", required=True, help="path to an alert JSON file")
    run.add_argument("--model", default=None, help="override the configured model")
    run.add_argument("--trajectory-out", default=None, help="write the trajectory JSON here")
    args = parser.parse_args(argv)

    config = Config.from_env()
    if args.model:
        config = Config(**{**config.__dict__, "model": args.model})
    alert = json.loads(Path(args.alert).read_text(encoding="utf-8"))
    state = run_incident(config, alert)

    if args.trajectory_out:
        Path(args.trajectory_out).write_text(
            json.dumps(state.get("trajectory", []), indent=2, default=str), encoding="utf-8"
        )
    result = {
        "status": state.get("status"),
        "diagnosis": state.get("diagnosis"),
        "diff": state.get("diff"),
        "pr": state.get("pr"),
        "tokens": state.get("tokens"),
        "cost_usd": state.get("cost_usd"),
        "duration_s": state.get("duration_s"),
        "error": state.get("error"),
    }
    print(json.dumps(result, indent=2, default=str))
    return 0 if state.get("status") == "pr_opened" else 1


if __name__ == "__main__":
    sys.exit(main())
