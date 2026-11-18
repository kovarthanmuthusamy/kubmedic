# KubeMedic architecture

## Data flow

```
Chaos (faulty values commit) ──► ArgoCD syncs ──► boutique breaks
                                                        │
Prometheus/Loki observe ──► Alertmanager ──webhook──► agent
                                                        │
        triage ──► investigate (read-only tools) ──► plan (values diff)
                                                        │
                                    pull request ──► human merges ──► ArgoCD heals
                                                        │
                                    evals score the run against ground truth
```

## Components

- **Target system** (`gitops/app/`): Google Online Boutique as one Helm
  chart whose per-service configuration is a flat key/value map in
  `values.yaml`. Flat keys are the key design choice: a fault is a list
  of key edits, a fix is a list of key edits, scoring compares keys.
- **Platform** (`gitops/argocd/apps/`): app-of-apps — boutique,
  kube-prometheus-stack (Prometheus/Grafana/Alertmanager), Loki +
  Promtail, Kyverno + policies, Chaos Mesh, and the agent itself.
- **Agent** (`agent/`): a LangGraph graph — triage, an investigator
  loop over read-only tools (kubectl, PromQL, LogQL, git history), a
  planner that turns the diagnosis into a values diff, and a PR writer.
  Models plug in through LiteLLM; `heuristic` is a deterministic
  built-in investigator used by tests and the replay gate.
- **Evals** (`evals/`): one scoring module used two ways — the replay
  gate (recorded evidence + heuristic investigator, runs in CI at zero
  cost) and the live harness (real cluster, real models, results JSON).

## Safety model

Safety is architectural, not prompt-based:

- the agent's Kubernetes service account has only get/list/watch;
- kubectl verbs are allowlisted in code as well (defence in depth);
- the only write path is a git branch + pull request a human merges;
- per-incident step/token/cost budgets stop runaway loops;
- tool output is truncated and treated as untrusted input;
- Kyverno policies (resource limits required, no `:latest`) bound what
  even a merged fix may create.

## What is verified, and what is not (yet)

Verified in CI on every push: unit tests, the 12/12 replay gate, Helm
rendering + schema validation of every manifest, Terraform validate,
and the agent Docker image build.

Not yet run anywhere: the live benchmark. It needs a machine with
Docker and a GPU (the original workstation is gone). `make up` +
`make benchmark` on such a machine produce the first
`evals/results/*.json`, and only then do the README's headline numbers
stop being `TBD`.
