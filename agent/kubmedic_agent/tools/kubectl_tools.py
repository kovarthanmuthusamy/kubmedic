"""kubectl tools, hard-limited to read-only verbs.

The allowlist is enforced here, in code — not in the prompt and not in
the model's good behaviour. The agent's service account is also
read-only (see gitops/agent/), so this is defence in depth.
"""

from __future__ import annotations

import subprocess
from typing import Protocol

ALLOWED_VERBS = {"get", "describe", "logs", "top"}


class KubectlBackend(Protocol):
    def run(self, args: list[str]) -> str: ...


class SubprocessKubectl:
    def run(self, args: list[str]) -> str:
        if not args or args[0] not in ALLOWED_VERBS:
            raise PermissionError(f"kubectl verb not allowed: {args[:1]}")
        proc = subprocess.run(
            ["kubectl", *args], check=False, capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "kubectl failed")
        return proc.stdout


class FakeKubectl:
    """Serves canned outputs for tests and the replay eval gate.

    `responses` maps a command prefix (e.g. "get pods") to its stdout.
    """

    def __init__(self, responses: dict[str, str]):
        self.responses = responses

    def run(self, args: list[str]) -> str:
        if not args or args[0] not in ALLOWED_VERBS:
            raise PermissionError(f"kubectl verb not allowed: {args[:1]}")
        joined = " ".join(args)
        for prefix, output in self.responses.items():
            if joined.startswith(prefix):
                return output
        raise RuntimeError(f"FakeKubectl: no canned output for {joined!r}")


def _lines(text: str, limit: int = 60) -> list[str]:
    return text.strip().splitlines()[:limit]


def register_kubectl_tools(registry, backend: KubectlBackend, namespace: str) -> None:
    from kubmedic_agent.tools.base import Tool

    def get_pods() -> dict:
        out = backend.run(
            ["get", "pods", "-n", namespace, "-o", "wide", "--no-headers"]
        )
        pods = []
        for line in _lines(out):
            parts = line.split()
            if len(parts) >= 5:
                pods.append(
                    {
                        "name": parts[0],
                        "ready": parts[1],
                        "status": parts[2],
                        "restarts": parts[3],
                    }
                )
        return {"namespace": namespace, "pods": pods}

    def describe_pod(pod: str) -> dict:
        out = backend.run(["describe", "pod", pod, "-n", namespace])
        keep = [
            line
            for line in _lines(out, 120)
            if any(
                k in line
                for k in ("State:", "Reason:", "Exit Code:", "Last State:", "Warning", "Failed")
            )
        ]
        return {"pod": pod, "summary_lines": keep}

    def get_pod_logs(pod: str, tail: int = 40) -> dict:
        out = backend.run(
            ["logs", pod, "-n", namespace, "--tail", str(min(tail, 100)), "--timestamps"]
        )
        return {"pod": pod, "logs": _lines(out, 40)}

    def get_events() -> dict:
        out = backend.run(
            ["get", "events", "-n", namespace, "--sort-by=.lastTimestamp", "--no-headers"]
        )
        warnings = [line for line in _lines(out) if "Warning" in line]
        return {"namespace": namespace, "warning_events": warnings[-20:]}

    registry.add(
        Tool(
            "get_pods",
            "List pods in the boutique namespace with status and restart counts.",
            {"type": "object", "properties": {}},
            get_pods,
        )
    )
    registry.add(
        Tool(
            "describe_pod",
            "Describe one pod: state, reason, exit codes and warning events.",
            {
                "type": "object",
                "properties": {"pod": {"type": "string"}},
                "required": ["pod"],
            },
            describe_pod,
        )
    )
    registry.add(
        Tool(
            "get_pod_logs",
            "Read the last log lines of one pod (read-only, truncated).",
            {
                "type": "object",
                "properties": {
                    "pod": {"type": "string"},
                    "tail": {"type": "integer", "default": 40},
                },
                "required": ["pod"],
            },
            get_pod_logs,
        )
    )
    registry.add(
        Tool(
            "get_events",
            "List recent Warning events in the boutique namespace.",
            {"type": "object", "properties": {}},
            get_events,
        )
    )
