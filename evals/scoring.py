"""Scoring, shared by the replay gate and the live benchmark harness.

A run is RESOLVED when both hold (the README's definition, fixed before
any run existed):

1. Applying the agent's fix to the faulted values restores every
   fault-affected key to its known-good value.
2. The agent's stated root cause matches the ground truth (any one of
   the scenario's keywords appears in it, case-insensitive).

Extra edits beyond the fault-affected keys are reported, not fatal:
they do not by themselves break health, but a reviewer should see them.
"""

from __future__ import annotations

import copy


def _apply(values: dict, edits: list[dict]) -> dict:
    out = copy.deepcopy(values)
    for edit in edits:
        out["services"][edit["service"]][edit["key"]] = edit["value"]
    return out


def score_run(
    scenario: dict,
    good_values: dict,
    *,
    status: str,
    diagnosis: dict | None,
) -> dict:
    diagnosis = diagnosis or {}
    fix = diagnosis.get("fix") or []
    faulted = _apply(good_values, scenario["fault"])
    try:
        restored = _apply(faulted, fix)
        fix_error = None
    except KeyError as exc:
        restored, fix_error = faulted, f"fix references unknown key: {exc}"

    affected = {(e["service"], e["key"]) for e in scenario["fault"]}
    keys_restored = all(
        restored["services"][svc][key] == good_values["services"][svc][key]
        for svc, key in affected
    )
    extra_edits = [
        {"service": e["service"], "key": e["key"]}
        for e in fix
        if (e["service"], e["key"]) not in affected
    ]
    root_cause = (diagnosis.get("root_cause") or "").lower()
    keyword_hit = next(
        (kw for kw in scenario["root_cause_keywords"] if kw.lower() in root_cause),
        None,
    )
    resolved = (
        status == "pr_opened" and keys_restored and keyword_hit is not None and not fix_error
    )
    return {
        "scenario": scenario["id"],
        "status": status,
        "resolved": resolved,
        "keys_restored": keys_restored,
        "root_cause_match": keyword_hit is not None,
        "matched_keyword": keyword_hit,
        "extra_edits": extra_edits,
        "fix_error": fix_error,
    }
