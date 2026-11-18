"""The boutique's Helm values are the single source of truth for the
target system, and they are deliberately FLAT per service:

    services:
      frontend:
        image: gcr.io/google-samples/microservices-demo/frontend
        tag: v0.10.1
        replicas: 1
        resources_limits_memory: 256Mi
        env_PRODUCT_CATALOG_SERVICE_ADDR: productcatalogservice:3550

Flat keys make faults, fixes and scoring simple key/value operations:
a fault is a list of (service, key, bad value), a fix is a list of
(service, key, good value), and scoring compares the affected keys.
"""

from __future__ import annotations

from pathlib import Path

import yaml

VALUES_REL_PATH = Path("gitops/app/values.yaml")


def load_values(gitops_path: str | Path) -> dict:
    path = Path(gitops_path) / VALUES_REL_PATH
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def dump_values(values: dict) -> str:
    return yaml.safe_dump(values, sort_keys=False, default_flow_style=False)


def get_key(values: dict, service: str, key: str):
    try:
        return values["services"][service][key]
    except KeyError as exc:
        raise KeyError(f"values has no services.{service}.{key}") from exc


def set_key(values: dict, service: str, key: str, value) -> None:
    if service not in values.get("services", {}):
        raise KeyError(f"values has no service {service!r}")
    values["services"][service][key] = value


def apply_edits(values: dict, edits: list[dict]) -> dict:
    """Return a new values dict with edits applied.

    Each edit is {"service": ..., "key": ..., "value": ...}. The key must
    already exist — the agent may change configuration, never invent it.
    """
    import copy

    new_values = copy.deepcopy(values)
    for edit in edits:
        get_key(new_values, edit["service"], edit["key"])  # must exist
        set_key(new_values, edit["service"], edit["key"], edit["value"])
    return new_values
