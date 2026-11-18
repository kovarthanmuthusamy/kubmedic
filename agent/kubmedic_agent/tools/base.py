from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

MAX_STRING_CHARS = 1200
MAX_LIST_ITEMS = 60


def truncate(obj):
    """Bound a tool result while keeping it structured: cap long strings
    and long lists instead of cutting the serialized form (which would
    corrupt it). Tool output is untrusted and can be arbitrarily large;
    the model only ever sees this bounded version."""
    if isinstance(obj, str):
        if len(obj) <= MAX_STRING_CHARS:
            return obj
        return obj[:MAX_STRING_CHARS] + f"... [truncated {len(obj) - MAX_STRING_CHARS} chars]"
    if isinstance(obj, list):
        return [truncate(item) for item in obj[:MAX_LIST_ITEMS]]
    if isinstance(obj, dict):
        return {key: truncate(value) for key, value in obj.items()}
    return obj


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON schema for the arguments object
    fn: Callable[..., dict]

    def spec(self) -> dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, arguments: dict) -> dict:
        try:
            result = self.fn(**arguments)
        except Exception as exc:  # noqa: BLE001 - tool errors are evidence, returned not raised
            return {"error": f"{type(exc).__name__}: {exc}"}
        return truncate(result)


@dataclass
class ToolRegistry:
    tools: dict[str, Tool] = field(default_factory=dict)

    def add(self, tool: Tool) -> None:
        self.tools[tool.name] = tool

    def specs(self) -> list[dict]:
        return [tool.spec() for tool in self.tools.values()]

    def run(self, name: str, arguments: dict) -> dict:
        tool = self.tools.get(name)
        if tool is None:
            return {"error": f"unknown tool {name!r}"}
        return tool.run(arguments)
