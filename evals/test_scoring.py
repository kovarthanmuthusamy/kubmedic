"""Unit tests for the shared scoring rules (no cluster, no agent)."""

from evals.scenarios import load_good_values, load_scenarios
from evals.scoring import score_run

GOOD = load_good_values()
SCENARIO = next(s for s in load_scenarios() if s["id"] == "01-oom-memory-limit")


def test_correct_fix_and_root_cause_resolves():
    diagnosis = {
        "service": "checkoutservice",
        "root_cause": "memory limit too low, pod OOMKilled",
        "fix": SCENARIO["fix"],
    }
    result = score_run(SCENARIO, GOOD, status="pr_opened", diagnosis=diagnosis)
    assert result["resolved"] is True
    assert result["extra_edits"] == []


def test_wrong_fix_does_not_resolve():
    diagnosis = {
        "service": "checkoutservice",
        "root_cause": "memory limit too low",
        "fix": [{"service": "checkoutservice", "key": "resources_limits_memory", "value": "128Mi"}],
    }
    result = score_run(SCENARIO, GOOD, status="pr_opened", diagnosis=diagnosis)
    assert result["resolved"] is False
    assert result["keys_restored"] is False


def test_missing_root_cause_match_does_not_resolve():
    diagnosis = {"service": "checkoutservice", "root_cause": "the pod is sad", "fix": SCENARIO["fix"]}
    result = score_run(SCENARIO, GOOD, status="pr_opened", diagnosis=diagnosis)
    assert result["resolved"] is False
    assert result["root_cause_match"] is False


def test_failed_status_never_resolves():
    diagnosis = {"root_cause": "memory limit", "fix": SCENARIO["fix"]}
    result = score_run(SCENARIO, GOOD, status="failed", diagnosis=diagnosis)
    assert result["resolved"] is False
