"""Read-only investigation tools.

Every tool returns a small, structured, truncated dict: tool output is
untrusted input (logs are written by whatever runs in the cluster), so
it is never passed to the model raw or unbounded.
"""

from kubmedic_agent.tools.base import Tool, ToolRegistry, truncate

__all__ = ["Tool", "ToolRegistry", "truncate"]
