"""Turn a diagnosis into a reviewable diff of the GitOps values file."""

from __future__ import annotations

import difflib
from pathlib import Path

from kubmedic_agent.values import VALUES_REL_PATH, apply_edits, dump_values, load_values


def build_fix_diff(gitops_path: str | Path, edits: list[dict]) -> tuple[str, dict]:
    """Validate edits against the current values and return (diff, new_values)."""
    values = load_values(gitops_path)
    new_values = apply_edits(values, edits)
    before = dump_values(values).splitlines(keepends=True)
    after = dump_values(new_values).splitlines(keepends=True)
    diff = "".join(
        difflib.unified_diff(
            before, after, fromfile=f"a/{VALUES_REL_PATH}", tofile=f"b/{VALUES_REL_PATH}"
        )
    )
    return diff, new_values
