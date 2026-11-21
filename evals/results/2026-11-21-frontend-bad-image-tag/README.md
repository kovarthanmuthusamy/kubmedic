# KubMedic — Live Demo (Azure VM, 2026-11-21)

One real incident, handled end to end by the KubMedic agent with Claude.

## What happened

- **Platform:** kind cluster (3 nodes, K8s v1.37) on an Azure VM (Standard_D4ms
  in UK South, 4 vCPU / 16 GB), running the Online Boutique (11 services),
  Prometheus, Loki + Promtail, ArgoCD, Chaos Mesh and Kyverno.
- **Fault injected (live):** the `frontend` deployment's image tag was changed
  from `v0.10.1` to the non-existent `v0.10.99`. The new frontend pod went
  `ImagePullBackOff` (`ErrImagePull`); the rollout stalled.
- **Alert given to the agent:** `KubePodNotReady` for `frontend`
  (`ImagePullBackOff`), Alertmanager-style JSON.

## What the agent did (37 seconds, 10,724 tokens, $0.04)

Model: `anthropic/claude-sonnet-4-6` (the user's chosen `claude-sonnet-4-5`
is not available via the API; 4-6 is the current Sonnet 4.x). Spend guardrail
`$0.50`/incident was in place; actual spend was `$0.0415`.

The agent's diagnosis (verbatim from its result):

> "A faulty commit changed frontend.tag from "v0.10.1" to the non-existent
> "v0.10.99". Kubernetes cannot pull the image
> gcr.io/google-samples/microservices-demo/frontend:v0.10.99 (not found in
> GCR), causing the new frontend pod to stay in ImagePullBackOff. The old
> replica (v0.10.1) is still serving traffic, but the rollout is broken."

Its fix: restore `frontend.tag` to `v0.10.1`. It committed that fix to the
local branch `kubmedic/fix-frontend-1795286763` (commit `fd644d8`).
No GitHub PR was created in this run (no push credentials in the demo);
the commit is the fix artefact.

## Recovery

The fix was applied to the live cluster (frontend image back to `v0.10.1`).
The bad pod terminated and the frontend returned to `1/1 Running`. All 11
Boutique services were `1/1 Running` at the end of the demo.

## Artefacts

- `agent-run.log` — full agent run output (result JSON).
- `trajectory.json` — the agent's 8-step trajectory
  (triage → model → tool → tool → model → tool → tool → model).
- `alert.json` — the alert that started the incident.
- `run-agent.sh` — the runner (surrogate key, tunnel, port-forwards).

## Cost

- Azure VM (Standard_D4s_v6, ~1.5 h): a few dollars at most; the VM and its
  resource group were deleted right after the demo to stop billing.
- Claude API (one incident): **$0.0415**.

## Notes / honest caveats

- The agent ran on the Muse VM (not the Azure VM) and reached the cluster
  through an SSH tunnel + kubectl port-forwards, because the Anthropic
  credential is held in the secure vault and only works from there (via a
  surrogate that the egress swaps for the real key). The cluster itself ran
  on Azure.
- The fault was injected into the live cluster with `kubectl`, not through
  the GitOps values file, so the agent's values.yaml fix is a no-op against
  the repo (the repo already said `v0.10.1`). The diagnosis and the fix it
  proposed are still exactly right, and applying that fix to the cluster is
  what recovered the frontend.
- The platform needed several repairs before the demo (kind version,
  Docker/inotify limits, Boutique env vars, ArgoCD self-heal) — see the
  run notes. The deployed `kubmedic-agent` pod itself never started (its
  GHCR image is private); the demo used the agent CLI, which is the
  supported demo path.
