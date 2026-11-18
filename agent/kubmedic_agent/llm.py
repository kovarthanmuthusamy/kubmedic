"""The model layer.

Two implementations behind one interface:

- LiteLLMModel: any real model via LiteLLM (local Ollama or a paid API).
  Swapping models is a config change.
- HeuristicModel: a deterministic investigator with no LLM at all. It
  follows the same evidence a good on-call engineer would — failing pod,
  its state and logs, then the most recent values change — and inverts
  that change as the fix. It exists for the replay eval gate and the
  unit tests: it proves the tool wiring, parsing, patching and scoring
  are correct, at zero cost. It does NOT measure model quality; only
  live runs do that.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import yaml


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ModelResponse:
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""
    tokens: int = 0
    cost_usd: float = 0.0


class LiteLLMModel:
    def __init__(self, model: str, ollama_base_url: str = "http://127.0.0.1:11434"):
        self.model = model
        self.ollama_base_url = ollama_base_url

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        import litellm

        kwargs: dict = {"model": self.model, "messages": messages, "tools": tools}
        if self.model.startswith("ollama/"):
            kwargs["api_base"] = self.ollama_base_url
        response = litellm.completion(**kwargs)
        message = response.choices[0].message
        calls = []
        for call in message.tool_calls or []:
            try:
                arguments = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            calls.append(ToolCall(id=call.id, name=call.function.name, arguments=arguments))
        usage = response.usage
        tokens = (usage.prompt_tokens or 0) + (usage.completion_tokens or 0) if usage else 0
        try:
            cost = float(litellm.completion_cost(completion_response=response) or 0.0)
        except Exception:  # noqa: BLE001 - cost reporting is best-effort
            cost = 0.0
        return ModelResponse(
            tool_calls=calls, text=message.content or "", tokens=tokens, cost_usd=cost
        )


def _tool_results(messages: list[dict]) -> dict[str, list[dict]]:
    """Collect parsed tool results by tool name, in order."""
    results: dict[str, list[dict]] = {}
    for msg in messages:
        if msg.get("role") == "tool" and msg.get("name"):
            try:
                payload = json.loads(msg.get("content") or "{}")
            except json.JSONDecodeError:
                payload = {}
            results.setdefault(msg["name"], []).append(payload)
    return results


def _parse_scalar(raw):
    if raw is None:
        return None
    if raw == "":
        return ""  # an emptied value is a real value, not a missing one
    try:
        return yaml.safe_load(str(raw))
    except yaml.YAMLError:
        return raw


BAD_STATUSES = {
    "CrashLoopBackOff",
    "ImagePullBackOff",
    "ErrImagePull",
    "CreateContainerConfigError",
    "Error",
    "Pending",
    "OOMKilled",
}


class HeuristicModel:
    """Deterministic investigator used by replay and tests (model='heuristic')."""

    def __init__(self):
        self._counter = 0

    def _call(self, name: str, arguments: dict) -> ModelResponse:
        self._counter += 1
        return ModelResponse(
            tool_calls=[ToolCall(id=f"heur-{self._counter}", name=name, arguments=arguments)]
        )

    def complete(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        results = _tool_results(messages)

        if "get_pods" not in results:
            return self._call("get_pods", {})

        pods = results["get_pods"][-1].get("pods", [])
        # A pod counts as evidence if it is in a bad state OR not ready
        # (a Running-but-never-ready pod is exactly the bad-probe case).
        bad = next(
            (
                p
                for p in pods
                if p.get("status") in BAD_STATUSES
                or p.get("ready", "1/1").split("/")[0] == "0"
            ),
            None,
        )

        if bad and "describe_pod" not in results:
            return self._call("describe_pod", {"pod": bad["name"]})
        if (
            bad
            and bad.get("status") not in ("Pending", "ImagePullBackOff", "ErrImagePull")
            and "get_pod_logs" not in results
        ):
            return self._call("get_pod_logs", {"pod": bad["name"]})
        if "git_recent_changes" not in results:
            return self._call("git_recent_changes", {"limit": 3})

        commits = results["git_recent_changes"][-1].get("commits", [])
        service = None
        if bad:
            # Boutique pods are named <service>-<replicaset-hash>-<suffix>.
            service = bad["name"].rsplit("-", 2)[0]
        changes: list[dict] = []
        commit_sha = ""
        for commit in commits:
            candidates = commit.get("changes", [])
            if service:
                scoped = [c for c in candidates if c.get("service") == service]
                if scoped:
                    candidates = scoped
            if candidates:
                changes = candidates
                commit_sha = commit.get("commit", "")
                break

        fix = [
            {
                "service": c["service"],
                "key": c["key"],
                "value": _parse_scalar(c.get("before")),
            }
            for c in changes
            if c.get("before") is not None
        ]
        if changes:
            detail = ", ".join(
                f"{c['key']} from {c.get('before')} to {c.get('after')}" for c in changes
            )
            if bad:
                root_cause = (
                    f"{changes[0]['service']}: commit {commit_sha} changed {detail}; "
                    f"pod {bad['name']} is {bad.get('status')}."
                )
            else:
                root_cause = (
                    f"{changes[0]['service']}: commit {commit_sha} changed {detail}; "
                    "pods look healthy, the values change itself is the fault."
                )
        elif bad:
            root_cause = (
                f"Pod {bad['name']} is {bad.get('status')} but no matching recent "
                "values change was found."
            )
        else:
            root_cause = "No failing pod found in the namespace."
        diagnosis = {
            "service": service or (changes[0]["service"] if changes else "unknown"),
            "root_cause": root_cause,
            "fix": fix,
        }
        return self._call("submit_diagnosis", diagnosis)
