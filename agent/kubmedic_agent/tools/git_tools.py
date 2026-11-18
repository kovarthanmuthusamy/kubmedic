"""Git history of the GitOps values file — the agent's memory of what
changed. Faults in this system are faulty commits, so the most recent
values change is prime evidence in every investigation.

The parser understands the flat per-service values layout (see
kubmedic_agent.values): service names at 2-space indent, keys at
4-space indent. It pairs removed/added lines per commit into
structured {service, key, before, after} changes.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Protocol

from kubmedic_agent.values import VALUES_REL_PATH

_SERVICE_RE = re.compile(r"^  ([A-Za-z0-9._-]+):\s*$")
_KEY_RE = re.compile(r"^    ([A-Za-z0-9_]+):\s*(.*)$")


def parse_values_diff(diff_text: str) -> list[dict]:
    """Parse a unified diff of values.yaml into structured key changes."""
    removed: dict[tuple[str, str], str] = {}
    added: dict[tuple[str, str], str] = {}
    order: list[tuple[str, str]] = []
    service: str | None = None
    for raw in diff_text.splitlines():
        if raw.startswith(("diff ", "index ", "---", "+++", "@@")):
            continue
        sign = raw[:1]
        line = raw[1:] if sign in "+- " else raw
        svc = _SERVICE_RE.match(line)
        if svc and not line.startswith("    "):
            service = svc.group(1)
            continue
        key = _KEY_RE.match(line)
        if key and service:
            name, value = key.group(1), key.group(2).strip()
            pair = (service, name)
            if pair not in order:
                order.append(pair)
            if sign == "-":
                removed[pair] = value
            elif sign == "+":
                added[pair] = value
    changes = []
    for service_name, key_name in order:
        pair = (service_name, key_name)
        if pair in removed or pair in added:
            changes.append(
                {
                    "service": service_name,
                    "key": key_name,
                    "before": removed.get(pair),
                    "after": added.get(pair),
                }
            )
    return changes


class GitBackend(Protocol):
    def recent_changes(self, limit: int) -> dict: ...


class SubprocessGit:
    def __init__(self, repo_path: str | Path):
        self.repo = str(repo_path)

    def _git(self, *args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", self.repo, *args], check=False, capture_output=True, text=True, timeout=30
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "git failed")
        return proc.stdout

    def recent_changes(self, limit: int = 3) -> dict:
        log = self._git(
            "log",
            f"-{limit}",
            "--format=COMMIT %H %s",
            "-p",
            # Wide context: the parser needs the service header line that
            # introduces a changed key, and service blocks run ~15 lines.
            "-U40",
            "--",
            str(VALUES_REL_PATH),
        )
        commits: list[dict] = []
        current: dict | None = None
        diff_lines: list[str] = []
        for line in log.splitlines():
            if line.startswith("COMMIT "):
                if current is not None:
                    current["changes"] = parse_values_diff("\n".join(diff_lines))
                    commits.append(current)
                parts = line.split(" ", 2)
                current = {"commit": parts[1][:12], "subject": parts[2] if len(parts) > 2 else ""}
                diff_lines = []
            elif current is not None:
                diff_lines.append(line)
        if current is not None:
            current["changes"] = parse_values_diff("\n".join(diff_lines))
            commits.append(current)
        return {"commits": commits}


class FakeGit:
    """Serves a fixed commit list for tests and the replay eval gate."""

    def __init__(self, commits: list[dict]):
        self.commits = commits

    def recent_changes(self, limit: int = 3) -> dict:
        return {"commits": self.commits[:limit]}


def register_git_tools(registry, backend: GitBackend) -> None:
    from kubmedic_agent.tools.base import Tool

    def git_recent_changes(limit: int = 3) -> dict:
        return backend.recent_changes(limit)

    registry.add(
        Tool(
            "git_recent_changes",
            "Recent commits touching the boutique values file, as structured "
            "per-key changes {service, key, before, after}. Faults here are "
            "faulty commits, so check what changed most recently.",
            {
                "type": "object",
                "properties": {"limit": {"type": "integer", "default": 3}},
            },
            git_recent_changes,
        )
    )
