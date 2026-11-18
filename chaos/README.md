# Chaos scenarios

The benchmark's faults are **faulty commits to `gitops/app/values.yaml`** —
not runtime chaos. That is deliberate: every scenario is exactly
reproducible, has a known root cause and a known correct fix, and the
agent's remedy (a values pull request) is the inverse of the fault.

Chaos Mesh is also installed (see `gitops/argocd/apps/chaos-mesh.yaml`)
for optional network/latency experiments, but the scored benchmark does
not depend on it.

## Scenario format (`scenarios/*.yaml`)

| Field | Meaning |
|---|---|
| `id`, `title`, `service`, `category` | Identity and grouping |
| `symptom` | What a human on-call would observe |
| `alert` | The Alertmanager alert that starts the incident |
| `fault` | Values edits that inject the fault: `{service, key, value}` |
| `fix` | The known correct fix (the good values, kept in sync with `values.yaml`) |
| `root_cause` | Ground-truth root cause, in words |
| `root_cause_keywords` | Any one keyword in the agent's stated root cause counts as a match |
| `evidence` | What the read-only tools would observe: the affected pod, describe lines, logs, events. Used by the replay eval gate |

Scoring is defined in `evals/scoring.py`: a run is *resolved* when the
agent's fix restores every fault-affected key to its good value and its
stated root cause matches the ground truth.
