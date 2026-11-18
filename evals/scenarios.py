from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SCENARIOS_DIR = REPO_ROOT / "chaos" / "scenarios"
VALUES_PATH = REPO_ROOT / "gitops" / "app" / "values.yaml"


def load_scenarios() -> list[dict]:
    scenarios = []
    for path in sorted(SCENARIOS_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as fh:
            scenarios.append(yaml.safe_load(fh))
    return scenarios


def load_good_values() -> dict:
    with VALUES_PATH.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)
