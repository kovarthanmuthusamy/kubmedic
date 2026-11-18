"""Assemble a tool registry from backends.

Live runs use the subprocess/HTTP backends; tests and the replay gate
inject the fakes. The agent code never knows which it is talking to.
"""

from __future__ import annotations

from kubmedic_agent.config import Config
from kubmedic_agent.tools.base import ToolRegistry
from kubmedic_agent.tools.git_tools import SubprocessGit, register_git_tools
from kubmedic_agent.tools.kubectl_tools import SubprocessKubectl, register_kubectl_tools
from kubmedic_agent.tools.loki_tools import HttpLoki, register_loki_tools
from kubmedic_agent.tools.prom_tools import HttpProm, register_prom_tools


def build_registry(
    config: Config,
    *,
    kubectl_backend=None,
    prom_backend=None,
    loki_backend=None,
    git_backend=None,
) -> ToolRegistry:
    registry = ToolRegistry()
    register_kubectl_tools(
        registry, kubectl_backend or SubprocessKubectl(), config.namespace
    )
    register_prom_tools(registry, prom_backend or HttpProm(config.prometheus_url))
    register_loki_tools(registry, loki_backend or HttpLoki(config.loki_url))
    register_git_tools(registry, git_backend or SubprocessGit(config.gitops_path))
    return registry
