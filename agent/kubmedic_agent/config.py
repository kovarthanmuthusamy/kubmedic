"""Runtime configuration, all from the environment.

Model access goes through LiteLLM, so swapping the model (local Ollama
vs a paid API) is a config change, never a code change.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    # LiteLLM model string, e.g. "ollama/qwen2.5:7b-instruct-q4_K_M"
    # or "openai/gpt-4o-mini". "heuristic" selects the deterministic
    # built-in investigator used by the replay eval gate and tests.
    model: str = "ollama/qwen2.5:7b-instruct-q4_K_M"
    ollama_base_url: str = "http://127.0.0.1:11434"
    namespace: str = "boutique"
    prometheus_url: str = "http://127.0.0.1:9090"
    loki_url: str = "http://127.0.0.1:3100"
    # Path to a checkout of the GitOps repo (this repo). The agent reads
    # its history and opens fix branches in it; it never writes to main.
    gitops_path: str = "."
    # Per-incident guardrails.
    max_steps: int = 12
    max_tokens: int = 60_000
    max_cost_usd: float = 0.50
    # When true, `open_pr` shells out to `gh pr create`; otherwise it
    # leaves the branch + PR body on disk (used by the eval harness).
    create_github_pr: bool = False

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            model=os.environ.get("KUBMEDIC_MODEL", cls.model),
            ollama_base_url=os.environ.get("OLLAMA_HOST", cls.ollama_base_url),
            namespace=os.environ.get("KUBMEDIC_NAMESPACE", cls.namespace),
            prometheus_url=os.environ.get("PROMETHEUS_URL", cls.prometheus_url),
            loki_url=os.environ.get("LOKI_URL", cls.loki_url),
            gitops_path=os.environ.get("KUBMEDIC_GITOPS_PATH", cls.gitops_path),
            max_steps=int(os.environ.get("KUBMEDIC_MAX_STEPS", cls.max_steps)),
            max_tokens=int(os.environ.get("KUBMEDIC_MAX_TOKENS", cls.max_tokens)),
            max_cost_usd=float(os.environ.get("KUBMEDIC_MAX_COST_USD", cls.max_cost_usd)),
            create_github_pr=os.environ.get("KUBMEDIC_CREATE_PR", "") == "1",
        )
