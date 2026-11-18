"""Prometheus (PromQL) tool — read-only queries over HTTP."""

from __future__ import annotations

from typing import Protocol

import httpx


class PromBackend(Protocol):
    def query(self, promql: str) -> dict: ...


class HttpProm:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def query(self, promql: str) -> dict:
        resp = httpx.get(
            f"{self.base_url}/api/v1/query", params={"query": promql}, timeout=15
        )
        resp.raise_for_status()
        data = resp.json().get("data", {})
        return {"result_type": data.get("resultType"), "result": data.get("result", [])[:10]}


class FakeProm:
    def __init__(self, responses: dict[str, dict] | None = None):
        self.responses = responses or {}

    def query(self, promql: str) -> dict:
        for fragment, payload in self.responses.items():
            if fragment in promql:
                return payload
        return {"result_type": "vector", "result": []}


def register_prom_tools(registry, backend: PromBackend) -> None:
    from kubmedic_agent.tools.base import Tool

    def promql_query(query: str) -> dict:
        return backend.query(query)

    registry.add(
        Tool(
            "promql_query",
            "Run an instant PromQL query against Prometheus, e.g. "
            "kube_pod_container_status_restarts_total or "
            "container_memory_working_set_bytes. Returns at most 10 series.",
            {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
            promql_query,
        )
    )
