# HANDOFF: KubeMedic (self-healing Kubernetes incident-response agent)

Read this fully before doing anything. It carries the decisions from the planning session so you don't re-derive them. Copy it into the new project folder inside WSL and treat it as the starting brief.

## 1. Who and why
- The user holds a Master's degree from TU Dortmund and is building portfolio projects for CV visibility.
- Target roles: **AI agentic engineer, MLOps, DevOps**.
- The project must show all three areas in one public GitHub repo, with numbers a recruiter can quote.

## 2. The project
**KubeMedic**: an AI SRE agent that detects a failure in a running microservice system on Kubernetes, investigates it, and opens a fix as a pull request. A human approves, and GitOps (ArgoCD) deploys it. An evaluation pipeline measures how well the agent does.

Why this one: it is not a RAG chatbot demo. It shows production concerns (guardrails, evals as a CI gate, observability, cost tracking, IaC, GitOps).

Target CV line: *"Resolved X/12 injected faults autonomously, median time-to-fix N s, $0 per incident on local models vs $Y on a frontier API."*

## 3. Hard constraints (decided, do not re-litigate)
| Constraint | Value |
|---|---|
| Deadline | **14 days**. The user's current machine is taken away after 2 weeks. |
| Budget | **Under $20 total**. Plan is $0 to $5. |
| LLMs | **Local models via Ollama on the 2 GPUs** for development and the main benchmark. One optional small paid-API baseline run (about $3 to $5) with a hard spend limit set in the API console. |
| Cloud | **None.** Everything runs on local kind. Keep Terraform in the repo and validate it in CI only (`terraform validate`, `tflint`, `checkov`). |
| Time per day | The user can give about 5 to 6 hours a day. |
| Learning level | Medium. The user wants to understand what is built, not just receive it. |

## 4. Environment facts (checked on the source machine, 2026-10-30)
- OS: Windows Server 2022. **Docker Desktop is not supported there**, so Docker Engine goes inside WSL2.
- Hardware: very large workstation (hundreds of GB RAM, 72 logical CPUs, 600 GB free disk), so local resources are not a concern. Do not design around a small laptop.
- GPUs: **2x NVIDIA Quadro GV100, 32 GB VRAM each** (Volta). Do not assume vLLM works on Volta. **Use Ollama or llama.cpp.**
- Ollama is already installed on **Windows**: `C:\Program Files\Ollama\ollama.exe`.
- WSL is present (distro and WSL version not yet verified).
- Installed: git, python 3.13. **Missing**: docker, kubectl, kind, helm, terraform.
- The user will create the new project folder inside WSL. Work there, not under `/mnt/c`.

## 5. Architecture
```
Chaos Mesh injects fault -> Prometheus/Loki alert -> Alertmanager webhook
    -> Agent (LangGraph or Claude Agent SDK)
         Triage -> Investigator -> Remediation planner
         tools via MCP servers: kubectl (read-only), PromQL, Loki logs, git history
    -> opens PR to the GitOps repo
    -> human approves (GitHub PR) -> ArgoCD syncs -> cluster heals
```
Stack: Google "Online Boutique" demo app as the target, kind, Helm, ArgoCD, GitHub Actions, Prometheus + Grafana + Loki, OpenTelemetry, Langfuse **Cloud free tier** for tracing (do not self-host Langfuse, it is heavy), Kyverno or OPA for policy, LiteLLM as the model-agnostic layer.

## 6. Design rules
1. **Model-agnostic agent** via LiteLLM. Swapping models is a config change; this gives the comparison table nearly for free.
2. **Safety by design:** the agent uses a read-only RBAC service account, changes the cluster only through PRs, has a token and cost budget per incident, and every action is traced and auditable.
3. **Chaos-driven benchmark:** 10 to 12 reproducible faults (OOMKill, bad image tag, broken ConfigMap, crash loop, latency injection, exhausted connection pool, and so on). Each has a known root cause and a known correct fix.
4. **Eval gate in CI** that runs on **recorded and replayed** LLM trajectories, so PR checks cost nothing. Live evals run manually and rarely.
5. **Keep tool schemas simple.** Local models are weaker at multi-step tool calling, so use few tools, tight outputs, and truncated logs and metrics.
6. A lower local-model success rate versus a frontier model is a **finding to report honestly**, not a failure of the project.

## 7. Reproducibility (the machine disappears)
- A `Makefile` with a one-command bootstrap (`make up` / `make down`) from day 1.
- Push to GitHub from day 1 and often. Nothing may exist only on this machine.
- Keep a `models.txt` listing the Ollama models pulled, plus a script to re-pull them.
- Before day 14 ends, commit: benchmark results, recorded trajectories, the demo video, the architecture diagram and the README.

## 8. 14-day plan
| Days | Work |
|---|---|
| 1-2 | Verify WSL2 (`wsl -l -v`), enable systemd, install Docker Engine, kind, kubectl, helm, terraform. Repo + Makefile. Online Boutique + monitoring stack. Push to GitHub. Confirm WSL can reach Windows Ollama (see section 9). Pull candidate models. LiteLLM layer. |
| 3-5 | First 3 chaos scenarios. Read-only tools (kubectl, PromQL, logs). Diagnosing agent. Langfuse Cloud tracing. |
| 6-8 | PR-based remediation, ArgoCD, human approval gate. Grow to 10-12 scenarios. |
| 9-11 | Benchmark harness and scoring. Run 2 to 3 local models. Record trajectories. CI eval gate on replay. |
| 12-13 | Optional paid-API baseline run. Comparison table (success rate, latency, cost). Grafana dashboard for MTTR and cost. |
| 14 | Demo video, README, architecture diagram, push everything. The blog post happens after the machine is gone, from the saved results. |

## 9. Known risks to check early
- **WSL to Windows Ollama networking.** Ollama listens on localhost on Windows. From WSL2 it may need `OLLAMA_HOST=0.0.0.0` on the Windows side or mirrored networking in `.wslconfig`. Verify with a curl to `http://<host>:11434/api/tags` before building on it. An alternative is installing Ollama inside WSL with GPU passthrough, but verify GPU visibility first (`nvidia-smi` in WSL).
- **Pods reaching the host's Ollama** from inside kind needs a reachable host address. Prefer running the agent outside the cluster, or as a container with a configured host route.
- **Docker in WSL2** needs systemd enabled in `/etc/wsl.conf`.
- **Model tool-calling support.** Pick models that Ollama lists as supporting tools, and re-check what is current. Model rankings change quickly, so do not rely on old assumptions.
- Volta lacks native bf16, so prefer quantized GGUF models.

## 10. Working agreements with the user
- **Ask before installing software or changing system settings.**
- **Explain each component before building it.** The user wants to learn.
- The user should **write the agent's tool definitions and the eval scoring themselves** (with your guidance), since interviewers will ask about them. Do not just generate those silently.
- Prefer a working vertical slice over broad scaffolding. Phases 1 and 2 alone are a good portfolio piece; phase 3 is what makes it stand out.
- Be honest about failures and limits in the README (a "where the agent fails and why" section is a feature).
- Do not commit secrets. Set the API spend limit before any paid call.

## 11. First actions for the new session
1. Confirm the project folder is inside WSL (not `/mnt/c`), then `git init` and create the GitHub repo.
2. Run the environment checks in section 9 and report results to the user.
3. Propose the repo layout (`infra/`, `gitops/`, `agent/`, `evals/`, `chaos/`, `docs/`, `Makefile`) and get approval.
4. Start phase 1 only after the user confirms.

## 12. Definition of done
- `make up` brings the whole system up from a clean WSL on any machine.
- At least 10 fault scenarios with scored results for at least 2 local models.
- CI runs the replay-based eval gate and Terraform validation.
- The README has an architecture diagram, benchmark table, demo video link and an honest failure analysis.
